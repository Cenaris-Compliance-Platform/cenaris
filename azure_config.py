"""
Azure configuration for ML results integration.
Configure your Azure Data Lake Storage connection here.
"""

import os
from dotenv import load_dotenv

load_dotenv()

class AzureConfig:
    """Azure Data Lake Storage configuration."""
    
    # Azure Storage Account Details
    STORAGE_ACCOUNT_NAME = "cenarisblobstorage"
    CONTAINER_NAME = "processed-doc-intel"
    RESULTS_PATH = "compliance-results"
    
    # Azure Data Lake Storage URL
    ACCOUNT_URL = f"https://{STORAGE_ACCOUNT_NAME}.dfs.core.windows.net"
    
    # Authentication (choose one method)
    
    # Method 1: Connection String (easiest for development)
    CONNECTION_STRING = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
    
    # Method 2: Account Key
    ACCOUNT_KEY = os.getenv('AZURE_STORAGE_ACCOUNT_KEY')
    
    # Method 3: SAS Token
    SAS_TOKEN = os.getenv('AZURE_STORAGE_SAS_TOKEN')
    
    # Method 4: Azure AD (for production)
    TENANT_ID = os.getenv('AZURE_TENANT_ID')
    CLIENT_ID = os.getenv('AZURE_CLIENT_ID')
    CLIENT_SECRET = os.getenv('AZURE_CLIENT_SECRET')
    
    # ML Results Configuration
    AUTO_REFRESH_INTERVAL = 120  # seconds (2 minutes)
    MAX_FILES_TO_PROCESS = 50
    SUPPORTED_FILE_FORMATS = ['.csv', '.json', '.parquet']
    
    # Status Mapping
    STATUS_MAPPING = {
        'Complete': 'Met',
        'Needs Review': 'Pending',
        'Missing': 'Not Met'
    }
    
    # Color Coding for UI
    STATUS_COLORS = {
        'Excellent': 'success',
        'Good': 'info', 
        'Needs Attention': 'warning',
        'Critical': 'danger'
    }

# Environment-specific configurations
class DevelopmentConfig(AzureConfig):
    """Development configuration with mock data."""
    USE_MOCK_DATA = True
    DEBUG = True

class ProductionConfig(AzureConfig):
    """Production configuration with real Azure connection."""
    USE_MOCK_DATA = False
    DEBUG = False

# Select configuration based on environment
config = DevelopmentConfig() if os.getenv('FLASK_ENV') == 'development' else ProductionConfig()