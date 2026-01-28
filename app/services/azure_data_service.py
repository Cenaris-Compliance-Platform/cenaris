"""
Azure Data Lake Storage service for ML results integration.
Connects to ADLS and processes compliance analysis results.
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
import time
try:
    from azure.storage.filedatalake import DataLakeServiceClient
    from azure.core.exceptions import ResourceNotFoundError
    from azure.core.exceptions import HttpResponseError
except ImportError:
    DataLakeServiceClient = None
    ResourceNotFoundError = Exception
    HttpResponseError = Exception

try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    BlobServiceClient = None
import json

logger = logging.getLogger(__name__)


# Very small in-memory cache to avoid hitting ADLS on every page load.
# This is safe for local/dev and also helpful in production (per-worker cache).
_DASHBOARD_SUMMARY_CACHE: dict[tuple[int | None, int | None], tuple[float, Dict]] = {}

# Cache for list operations (and recent failures) because ADLS list calls can be slow.
_COMPLIANCE_FILES_CACHE: dict[tuple[int | None, int | None], tuple[float, List[Dict]]] = {}
_COMPLIANCE_FILES_FAILURE_CACHE: dict[tuple[int | None, int | None], tuple[float, str]] = {}


def _safe_int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except Exception:
        return default

class AzureDataLakeService:
    """Service to interact with Azure Data Lake Storage for ML results."""
    
    def __init__(self):
        """Initialize the Azure Data Lake service."""
        self.account_name = "cenarisblobstorage"
        # Get container from env or use default
        self.container_name = os.getenv('AZURE_ML_CONTAINER', 'results')
        self.results_path = os.getenv('AZURE_ML_RESULTS_PATH', 'compliance-results')
        
        # Initialize client (you'll need to set up authentication)
        self.service_client = None
        self.blob_service_client = None
        self._initialize_client()

    @staticmethod
    def _is_endpoint_unsupported_account_features(exc: Exception) -> bool:
        # Azure sometimes returns this when using ADLS Gen2 path ops against accounts with
        # features like BlobStorageEvents/SoftDelete enabled.
        msg = str(exc) or ''
        return ('EndpointUnsupportedAccountFeatures' in msg) or ('does not support BlobStorageEvents' in msg)
    
    def _initialize_client(self):
        """Initialize the Data Lake service client."""
        try:
            # Get connection string from environment
            connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
            
            if connection_string and DataLakeServiceClient:
                # Use connection string directly
                self.service_client = DataLakeServiceClient.from_connection_string(connection_string)
                # Use print during startup to avoid threading issues
                print("[INFO] Azure Data Lake client initialized successfully")
            if connection_string and BlobServiceClient:
                self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
                print("[INFO] Azure Blob client (for fallback) initialized successfully")
            else:
                print("[WARNING] No Azure connection string found - using mock mode")
                self.service_client = None
        except Exception as e:
            # Use print during startup to avoid threading issues
            print(f"[WARNING] Failed to initialize Azure Data Lake client: {e}")
            self.service_client = None
            self.blob_service_client = None

    def _list_files_via_blob(self, search_path: str, timeout_seconds: int) -> List[Dict]:
        """Fallback: list files via Blob API when ADLS path operations are unsupported."""
        if not self.blob_service_client:
            return []

        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            prefix = (search_path or '').strip('/')
            if prefix:
                prefix = prefix + '/'

            max_blobs = _safe_int_env('AZURE_ADLS_LIST_MAX_BLOBS', 250)
            files: list[Dict] = []

            try:
                blobs = container_client.list_blobs(name_starts_with=prefix, timeout=timeout_seconds)
            except TypeError:
                blobs = container_client.list_blobs(name_starts_with=prefix)

            for blob in blobs:
                name = getattr(blob, 'name', '')
                if not name:
                    continue
                if not (name.endswith('.csv') or name.endswith('.json')):
                    continue

                file_name = os.path.basename(name)
                framework = 'Multiple Frameworks'
                if 'summary' in file_name.lower():
                    framework = 'Compliance Summary'

                files.append({
                    'file_name': file_name,
                    'file_path': name,
                    'last_modified': getattr(blob, 'last_modified', None),
                    'file_size': getattr(blob, 'size', 0) or 0,
                    'framework': framework,
                })

                if max_blobs > 0 and len(files) >= max_blobs:
                    break

            return files
        except Exception as e:
            logger.error(f"Blob fallback list failed for prefix '{search_path}': {e}")
            return []
    
    def get_compliance_files(self, user_id: int = None, organization_id: int = None) -> List[Dict]:
        """Get list of compliance result files from ADLS."""
        try:
            if not self.service_client and not self.blob_service_client:
                logger.warning("No ADLS/Blob client available")
                return []

            cache_key = (int(user_id) if user_id is not None else None, int(organization_id) if organization_id is not None else None)

            # If the endpoint is failing (auth/config/account features), don't block every page load.
            failure_ttl = _safe_int_env('AZURE_ADLS_FAILURE_CACHE_SECONDS', 120)
            if failure_ttl > 0:
                failure = _COMPLIANCE_FILES_FAILURE_CACHE.get(cache_key)
                if failure:
                    failed_at, _msg = failure
                    if (time.time() - failed_at) < failure_ttl:
                        return []

            # Successful list cache.
            # Default higher to avoid paying ADLS list latency on frequent dashboard refreshes.
            list_cache_ttl = _safe_int_env('AZURE_ADLS_LIST_CACHE_SECONDS', 300)
            if list_cache_ttl > 0:
                cached = _COMPLIANCE_FILES_CACHE.get(cache_key)
                if cached:
                    cached_at, cached_files = cached
                    if (time.time() - cached_at) < list_cache_ttl:
                        logger.info('ADLS list cache hit')
                        return cached_files

            # Best-effort timeout for ADLS list operations (seconds). Some SDK versions support it.
            timeout_seconds = _safe_int_env('AZURE_ADLS_TIMEOUT_SECONDS', 5)
            
            file_system_client = None
            if self.service_client:
                file_system_client = self.service_client.get_file_system_client(self.container_name)
            
            from datetime import datetime
            year = datetime.now().year
            month = datetime.now().month

            # Prefer org-scoped paths when org_id is known; fall back to legacy per-user path.
            search_paths: list[str] = []
            if user_id and organization_id:
                org_id_int = int(organization_id)
                user_id_int = int(user_id)
                search_paths.append(f"{self.results_path}/{year}/{month:02d}/org_{org_id_int}/user_{user_id_int}")
                search_paths.append(f"{self.results_path}/{year}/{month:02d}/organizations/{org_id_int}/user_{user_id_int}")

            if user_id:
                search_paths.append(f"{self.results_path}/{year}/{month:02d}/user_{int(user_id)}")
            else:
                search_paths.append(self.results_path)

            files_by_path: dict[str, Dict] = {}
            for search_path in search_paths:
                # Prefer ADLS path listing when available.
                if file_system_client:
                    try:
                        try:
                            paths = file_system_client.get_paths(path=search_path, timeout=timeout_seconds)
                        except TypeError:
                            paths = file_system_client.get_paths(path=search_path)

                        for path in paths:
                            if not path.is_directory and (path.name.endswith('.csv') or path.name.endswith('.json')):
                                file_name = os.path.basename(path.name)

                                framework = 'Multiple Frameworks'
                                if 'summary' in file_name.lower():
                                    framework = 'Compliance Summary'

                                files_by_path[path.name] = {
                                    'file_name': file_name,
                                    'file_path': path.name,
                                    'last_modified': path.last_modified,
                                    'file_size': path.content_length or 0,
                                    'framework': framework,
                                }
                    except Exception as e:
                        # If the account doesn't support ADLS path operations, fall back to Blob listing.
                        if self._is_endpoint_unsupported_account_features(e):
                            blob_files = self._list_files_via_blob(search_path, timeout_seconds=timeout_seconds)
                            for f in blob_files:
                                files_by_path[f['file_path']] = f
                        else:
                            continue
                else:
                    # No ADLS client: attempt Blob fallback.
                    blob_files = self._list_files_via_blob(search_path, timeout_seconds=timeout_seconds)
                    for f in blob_files:
                        files_by_path[f['file_path']] = f

                # If we found anything in the preferred path, stop early.
                if files_by_path and (user_id and organization_id):
                    break

            files = list(files_by_path.values())
            logger.info(f"Found {len(files)} compliance files in ADLS (searched: {search_paths})")

            if list_cache_ttl > 0:
                _COMPLIANCE_FILES_CACHE[cache_key] = (time.time(), files)
            return files
            
        except Exception as e:
            try:
                cache_key = (int(user_id) if user_id is not None else None, int(organization_id) if organization_id is not None else None)
                _COMPLIANCE_FILES_FAILURE_CACHE[cache_key] = (time.time(), str(e))
            except Exception:
                pass
            logger.error(f"Error getting compliance files: {e}")
            return []
    
    def get_file_analysis_summary(self, file_path: str) -> Dict:
        """Get analysis summary for a specific file from ADLS."""
        try:
            file_name = os.path.basename(file_path)
            
            # Read actual data from ADLS
            raw_data = self.read_adls_file(file_path)
            
            if not raw_data:
                return {
                    'file_name': file_name,
                    'total_requirements': 0,
                    'complete_count': 0,
                    'needs_review_count': 0,
                    'missing_count': 0,
                    'overall_status': 'No Data',
                    'compliancy_rate': 0,
                    'weighted_score': 0,
                    'last_updated': datetime.now(),
                    'requirements': []
                }
            
            # Process the real ADLS data
            summary = self.process_adls_data(raw_data)
            
            return {
                'file_name': file_name,
                'total_requirements': summary['total_requirements'],
                'complete_count': summary['complete_count'],
                'needs_review_count': summary['needs_review_count'],
                'missing_count': summary['missing_count'],
                'overall_status': summary['overall_status'],
                'compliancy_rate': summary['compliancy_rate'],
                'weighted_score': summary['weighted_score'],
                'last_updated': datetime.now(),
                'requirements': raw_data,  # Your actual ADLS data
                'frameworks': summary.get('frameworks', [])  # ADD THIS!
            }
                
        except Exception as e:
            logger.error(f"Error getting file analysis: {e}")
            return {
                'file_name': 'error.csv',
                'total_requirements': 0,
                'complete_count': 0,
                'needs_review_count': 0,
                'missing_count': 0,
                'overall_status': 'Error',
                'compliancy_rate': 0,
                'weighted_score': 0,
                'last_updated': datetime.now(),
                'requirements': []
            }
    
    def read_adls_file(self, file_path: str) -> List[Dict]:
        """Read and parse a CSV/JSON file from ADLS."""
        try:
            if not self.service_client and not self.blob_service_client:
                logger.warning("No ADLS/Blob client available")
                return []

            # Best-effort timeout for ADLS download operations (seconds). Some SDK versions support it.
            timeout_seconds = _safe_int_env('AZURE_ADLS_TIMEOUT_SECONDS', 10)
            
            content = None

            # Prefer ADLS file client when available.
            if self.service_client:
                try:
                    file_client = self.service_client.get_file_client(self.container_name, file_path)
                    try:
                        download = file_client.download_file(timeout=timeout_seconds)
                    except TypeError:
                        download = file_client.download_file()
                    content = download.readall().decode('utf-8')
                except Exception as e:
                    # Fallback to blob if ADLS path ops are unsupported.
                    if not self._is_endpoint_unsupported_account_features(e):
                        raise

            if content is None:
                if not self.blob_service_client:
                    return []
                blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=file_path)
                try:
                    download = blob_client.download_blob(timeout=timeout_seconds)
                except TypeError:
                    download = blob_client.download_blob()
                content = download.readall().decode('utf-8')
            
            # Parse CSV content
            if file_path.endswith('.csv'):
                import csv
                import io
                
                csv_reader = csv.DictReader(io.StringIO(content))
                data = []
                
                for row in csv_reader:
                    # Convert your exact column names to the expected format
                    processed_row = {}
                    for key, value in row.items():
                        clean_key = key.strip()
                        
                        # Map your actual columns: Framework, Compliance_Score, Status
                        if clean_key == 'Framework':
                            processed_row['Framework'] = value.strip() if value else ''
                        elif clean_key == 'Compliance_Score':
                            processed_row['Compliance_Score'] = float(value) if value else 0.0
                        elif clean_key == 'Status':
                            processed_row['Status'] = value.strip() if value else ''
                    
                    # Only add if we have data
                    if processed_row:
                        data.append(processed_row)
                        logger.debug(f"Parsed row: {processed_row}")
                
                logger.info(f"Successfully read {len(data)} rows from {file_path}")
                logger.debug(f"Data: {data}")
                return data
            
            elif file_path.endswith('.json'):
                import json
                data = json.loads(content)
                return data if isinstance(data, list) else [data]
            
            return []
            
        except Exception as e:
            logger.error(f"Error reading ADLS file {file_path}: {e}")
            return []
    
    def process_adls_data(self, raw_data: List[Dict]) -> Dict:
        """Process raw ADLS data into summary format."""
        if not raw_data:
            return {
                'total_requirements': 0,
                'complete_count': 0,
                'needs_review_count': 0,
                'missing_count': 0,
                'overall_status': 'No Data',
                'compliancy_rate': 0,
                'weighted_score': 0,
                'frameworks': []
            }
        
        # Filter out "Overall" row for counting
        framework_data = [r for r in raw_data if r.get('Framework', '').lower() != 'overall']
        
        # Count statuses from your ADLS data
        complete_count = len([r for r in framework_data if r.get('Status', '').lower() == 'complete'])
        needs_review_count = len([r for r in framework_data if r.get('Status', '').lower() == 'needs review'])
        missing_count = len([r for r in framework_data if r.get('Status', '').lower() == 'missing'])
        total_requirements = len(framework_data)
        
        # Get overall score if present
        overall_row = next((r for r in raw_data if r.get('Framework', '').lower() == 'overall'), None)
        overall_score = overall_row.get('Compliance_Score', 0) if overall_row else 0
        
        # Calculate compliance rate (convert score to percentage if needed)
        compliancy_rate = float(overall_score) if overall_score else 0
        
        # Determine overall status based on score
        if compliancy_rate >= 9:
            overall_status = 'Excellent'
        elif compliancy_rate >= 7:
            overall_status = 'Good'
        elif compliancy_rate >= 5:
            overall_status = 'Needs Attention'
        else:
            overall_status = 'Critical'
        
        # Extract framework details
        frameworks = []
        for row in framework_data:
            frameworks.append({
                'name': row.get('Framework', 'Unknown'),
                'score': float(row.get('Compliance_Score', 0)),
                'status': row.get('Status', 'Unknown')
            })
        
        return {
            'total_requirements': total_requirements,
            'complete_count': complete_count,
            'needs_review_count': needs_review_count,
            'missing_count': missing_count,
            'overall_status': overall_status,
            'compliancy_rate': round(compliancy_rate, 2),
            'weighted_score': round(compliancy_rate, 2),
            'frameworks': frameworks
        }
    
    def get_dashboard_summary(self, user_id: int = None, organization_id: int = None) -> Dict:
        """Get overall dashboard summary from ADLS compliance files."""
        try:
            # Default higher: ADLS calls are high-latency and make the UI feel broken.
            cache_seconds = _safe_int_env('AZURE_DASHBOARD_CACHE_SECONDS', 300)
            max_files = _safe_int_env('AZURE_DASHBOARD_MAX_FILES', 4)
            cache_key = (int(user_id) if user_id is not None else None, int(organization_id) if organization_id is not None else None)
            cached = _DASHBOARD_SUMMARY_CACHE.get(cache_key) if cache_seconds > 0 else None

            # Serve cached results even if slightly stale to keep navigation fast,
            # but bound staleness so we eventually refresh.
            stale_max_seconds = _safe_int_env('AZURE_DASHBOARD_STALE_MAX_SECONDS', 3600)
            if cached:
                cached_at, cached_value = cached
                age = time.time() - cached_at
                if age < cache_seconds:
                    logger.info('Dashboard summary cache hit')
                    return cached_value
                if stale_max_seconds > 0 and age < stale_max_seconds:
                    logger.info('Dashboard summary serving stale cache')
                    return cached_value

            files = self.get_compliance_files(user_id, organization_id)
            total_files = len(files)
            
            if total_files == 0:
                connection_status = 'Connected - No Files Found' if self.service_client else 'Not Connected to ADLS'
                result = {
                    'total_files': 0,
                    'avg_compliancy_rate': 0,
                    'total_requirements': 0,
                    'total_complete': 0,
                    'total_needs_review': 0,
                    'total_missing': 0,
                    'last_updated': datetime.now(),
                    'file_summaries': [],
                    'connection_status': connection_status,
                    'adls_path': f'abfss://{self.container_name}@{self.account_name}.dfs.core.windows.net/{self.results_path}/'
                }

                # Cache the empty result too; otherwise we retry the ADLS list operation on every request.
                if cache_seconds > 0:
                    _DASHBOARD_SUMMARY_CACHE[cache_key] = (time.time(), result)

                return result
            
            # Dashboard optimization:
            # Prefer a single precomputed summary file when present to avoid downloading/parsing many files.
            # Fallback: limit the number of files processed to keep the dashboard responsive.
            files_sorted = sorted(
                files,
                key=lambda f: (str(f.get('file_name') or '').lower(), f.get('last_modified') or datetime.min),
                reverse=True,
            )
            lower_name = lambda f: str(f.get('file_name') or '').lower()
            summary_candidates = [f for f in files_sorted if 'compliance_summary' in lower_name(f)]
            if not summary_candidates:
                summary_candidates = [f for f in files_sorted if 'summary' in lower_name(f)]

            files_to_process = summary_candidates[:1] if summary_candidates else files_sorted[: max(1, max_files)]

            # Process selected files
            file_summaries = []
            total_requirements = 0
            total_complete = 0
            total_needs_review = 0
            total_missing = 0
            compliancy_rates = []
            
            for file_info in files_to_process:
                summary = self.get_file_analysis_summary(file_info['file_path'])
                file_summaries.append({
                    'file_name': summary['file_name'],
                    'framework': file_info.get('framework', 'Unknown'),
                    'compliancy_rate': summary['compliancy_rate'],
                    'overall_status': summary['overall_status'],
                    'total_requirements': summary['total_requirements'],
                    'complete_count': summary['complete_count'],
                    'needs_review_count': summary['needs_review_count'],
                    'missing_count': summary['missing_count'],
                    'last_updated': file_info['last_modified'],
                    'frameworks': summary.get('frameworks', [])
                })
                
                total_requirements += summary['total_requirements']
                total_complete += summary['complete_count']
                total_needs_review += summary['needs_review_count']
                total_missing += summary['missing_count']
                compliancy_rates.append(summary['compliancy_rate'])
            
            avg_compliancy_rate = sum(compliancy_rates) / len(compliancy_rates) if compliancy_rates else 0
            
            result = {
                'total_files': total_files,
                'avg_compliancy_rate': round(avg_compliancy_rate, 1),
                'total_requirements': total_requirements,
                'total_complete': total_complete,
                'total_needs_review': total_needs_review,
                'total_missing': total_missing,
                'last_updated': max([f['last_updated'] for f in file_summaries]) if file_summaries else datetime.now(),
                'file_summaries': file_summaries,
                'connection_status': 'Connected - Files Found',
                'adls_path': f'abfss://{self.container_name}@{self.account_name}.dfs.core.windows.net/{self.results_path}/'
            }

            if cache_seconds > 0:
                _DASHBOARD_SUMMARY_CACHE[cache_key] = (time.time(), result)

            return result
            
        except Exception as e:
            logger.error(f"Error getting dashboard summary: {e}")
            return {
                'total_files': 0,
                'avg_compliancy_rate': 0,
                'total_requirements': 0,
                'total_complete': 0,
                'total_needs_review': 0,
                'total_missing': 0,
                'last_updated': datetime.now(),
                'file_summaries': [],
                'connection_status': 'ADLS Connection Error',
                'adls_path': f'abfss://{self.container_name}@{self.account_name}.dfs.core.windows.net/{self.results_path}/'
            }

# Global service instance
azure_data_service = AzureDataLakeService()