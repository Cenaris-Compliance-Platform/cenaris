"""
Azure Data Lake Storage service for ML results integration.
Connects to ADLS and processes compliance analysis results.
"""

import pandas as pd
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
try:
    from azure.storage.filedatalake import DataLakeServiceClient
    from azure.core.exceptions import ResourceNotFoundError
except ImportError:
    DataLakeServiceClient = None
    ResourceNotFoundError = Exception
import json

logger = logging.getLogger(__name__)

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
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Data Lake service client."""
        try:
            # Get connection string from environment
            connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
            
            if connection_string and DataLakeServiceClient:
                # Use connection string directly
                self.service_client = DataLakeServiceClient.from_connection_string(connection_string)
                logger.info("Azure Data Lake client initialized successfully")
            else:
                logger.warning("No Azure connection string found - using mock mode")
                self.service_client = None
        except Exception as e:
            logger.error(f"Failed to initialize Azure Data Lake client: {e}")
            self.service_client = None
    
    def get_compliance_files(self, user_id: int = None) -> List[Dict]:
        """Get list of compliance result files from ADLS."""
        try:
            if not self.service_client:
                logger.warning("No ADLS client available")
                return []
            
            # Connect to your actual ADLS
            file_system_client = self.service_client.get_file_system_client(self.container_name)
            
            # Build path for specific user if provided
            search_path = self.results_path
            if user_id:
                # Search in user-specific path: compliance-results/2025/11/user_X/
                from datetime import datetime
                year = datetime.now().year
                month = datetime.now().month
                search_path = f"{self.results_path}/{year}/{month:02d}/user_{user_id}"
            
            # List files in compliance-results path
            files = []
            paths = file_system_client.get_paths(path=search_path)
            
            for path in paths:
                if not path.is_directory and (path.name.endswith('.csv') or path.name.endswith('.json')):
                    file_name = os.path.basename(path.name)
                    
                    # Determine framework from filename
                    framework = 'Multiple Frameworks'
                    if 'summary' in file_name.lower():
                        framework = 'Compliance Summary'
                    
                    files.append({
                        'file_name': file_name,
                        'file_path': path.name,
                        'last_modified': path.last_modified,
                        'file_size': path.content_length or 0,
                        'framework': framework
                    })
            
            logger.info(f"Found {len(files)} compliance files in ADLS at {search_path}")
            return files
            
        except Exception as e:
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
            if not self.service_client:
                logger.warning("No ADLS client available")
                return []
            
            # Read from actual ADLS
            file_client = self.service_client.get_file_client(self.container_name, file_path)
            download = file_client.download_file()
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
                        logger.info(f"Parsed row: {processed_row}")
                
                logger.info(f"Successfully read {len(data)} rows from {file_path}")
                logger.info(f"Data: {data}")
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
    
    def get_dashboard_summary(self, user_id: int = None) -> Dict:
        """Get overall dashboard summary from ADLS compliance files."""
        try:
            files = self.get_compliance_files(user_id)
            total_files = len(files)
            
            if total_files == 0:
                connection_status = 'Connected - No Files Found' if self.service_client else 'Not Connected to ADLS'
                return {
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
            
            # Process all files
            file_summaries = []
            total_requirements = 0
            total_complete = 0
            total_needs_review = 0
            total_missing = 0
            compliancy_rates = []
            
            for file_info in files:
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
            
            return {
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