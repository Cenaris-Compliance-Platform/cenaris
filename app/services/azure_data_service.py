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
        self.container_name = "processed-doc-intel"
        self.results_path = "compliance-results"
        
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
    
    def get_compliance_files(self) -> List[Dict]:
        """Get list of compliance result files from ADLS."""
        try:
            if not self.service_client:
                logger.warning("No ADLS client available")
                return []
            
            # Connect to your actual ADLS
            file_system_client = self.service_client.get_file_system_client(self.container_name)
            
            # List files in compliance-results path
            files = []
            paths = file_system_client.get_paths(path=self.results_path)
            
            for path in paths:
                if not path.is_directory and (path.name.endswith('.csv') or path.name.endswith('.json')):
                    file_name = os.path.basename(path.name)
                    
                    # Try to determine framework from filename
                    framework = 'Unknown'
                    if 'sox' in file_name.lower():
                        framework = 'SOX'
                    elif 'gdpr' in file_name.lower():
                        framework = 'GDPR'
                    elif 'iso' in file_name.lower():
                        framework = 'ISO 27001'
                    elif 'pci' in file_name.lower():
                        framework = 'PCI DSS'
                    elif 'hipaa' in file_name.lower():
                        framework = 'HIPAA'
                    
                    files.append({
                        'file_name': file_name,
                        'file_path': path.name,
                        'last_modified': path.last_modified,
                        'file_size': path.content_length or 0,
                        'framework': framework
                    })
            
            logger.info(f"Found {len(files)} compliance files in ADLS")
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
                'requirements': raw_data  # Your actual ADLS data
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
                        # Handle different possible column name variations
                        clean_key = key.strip()
                        
                        # Map to standardized names
                        if clean_key in ['Best Match Page', 'Best_Match_Page']:
                            processed_row['Best_Match_Page'] = int(value) if value.isdigit() else 0
                        elif clean_key in ['Outcome Code', 'Outcome_Code']:
                            processed_row['Outcome_Code'] = value
                        elif clean_key == 'Requirement':
                            processed_row['Requirement'] = value
                        elif clean_key == 'Rule':
                            processed_row['Rule'] = value
                        elif clean_key in ['Rule Status', 'Rule_Status']:
                            processed_row['Rule_Status'] = value
                        elif clean_key == 'Similarity':
                            processed_row['Similarity'] = float(value) if value else 0.0
                        elif clean_key == 'Status':
                            processed_row['Status'] = value
                        elif clean_key in ['Status Score', 'Status_Score']:
                            processed_row['Status_Score'] = float(value) if value else 0.0
                        elif clean_key == 'Weight':
                            processed_row['Weight'] = float(value) if value else 0.0
                        elif clean_key in ['Weighted Score', 'Weighted_Score']:
                            processed_row['Weighted_Score'] = float(value) if value else 0.0
                    
                    data.append(processed_row)
                
                logger.info(f"Successfully read {len(data)} rows from {file_path}")
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
                'weighted_score': 0
            }
        
        # Count statuses from your ADLS data
        complete_count = len([r for r in raw_data if r.get('Status') == 'Complete'])
        needs_review_count = len([r for r in raw_data if r.get('Status') == 'Needs Review'])
        missing_count = len([r for r in raw_data if r.get('Status') == 'Missing'])
        total_requirements = len(raw_data)
        
        # Calculate compliance rate
        compliancy_rate = (complete_count / total_requirements * 100) if total_requirements > 0 else 0
        
        # Calculate weighted score
        total_weighted_score = sum([r.get('Weighted_Score', 0) for r in raw_data])
        
        # Determine overall status
        if compliancy_rate >= 90:
            overall_status = 'Excellent'
        elif compliancy_rate >= 70:
            overall_status = 'Good'
        elif compliancy_rate >= 50:
            overall_status = 'Needs Attention'
        else:
            overall_status = 'Critical'
        
        return {
            'total_requirements': total_requirements,
            'complete_count': complete_count,
            'needs_review_count': needs_review_count,
            'missing_count': missing_count,
            'overall_status': overall_status,
            'compliancy_rate': round(compliancy_rate, 1),
            'weighted_score': round(total_weighted_score, 1)
        }
    
    def get_dashboard_summary(self) -> Dict:
        """Get overall dashboard summary from ADLS compliance files."""
        try:
            files = self.get_compliance_files()
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
                    'last_updated': file_info['last_modified']
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