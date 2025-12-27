"""
Azure Blob Storage service for document management.
Handles upload, download, and deletion of documents in Azure Blob Storage.
"""

import os
import logging
from typing import Optional

try:
    from azure.storage.blob import BlobServiceClient
    from azure.core.exceptions import ResourceNotFoundError
except ImportError:
    BlobServiceClient = None
    ResourceNotFoundError = Exception

logger = logging.getLogger(__name__)


class AzureStorageService:
    """Service to interact with Azure Blob Storage for document management."""
    
    def __init__(self):
        """Initialize the Azure Blob Storage service."""
        self.account_name = os.getenv('AZURE_STORAGE_ACCOUNT_NAME', 'cenarisprodsa')
        self.container_name = os.getenv('AZURE_CONTAINER_NAME', 'user-uploads')
        
        # Initialize client
        self.blob_service_client = None
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the Blob Service client."""
        try:
            # Get connection string from environment
            connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
            
            if connection_string and BlobServiceClient:
                self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
                logger.info("Azure Blob Storage client initialized successfully")
            else:
                logger.warning("No Azure connection string found - blob operations will fail")
                self.blob_service_client = None
        except Exception as e:
            logger.error(f"Failed to initialize Azure Blob Storage client: {e}")
            self.blob_service_client = None
    
    def _get_org_folder(self, organization_id: int) -> str:
        """
        Get the organization-specific folder path.
        
        Args:
            organization_id: ID of the organization
            
        Returns:
            Folder path string (e.g., "org_123/")
        """
        return f"org_{organization_id}/"
    
    def upload_blob(self, blob_name: str, data: bytes, content_type: str = None, organization_id: int = None) -> bool:
        """
        Upload a blob to Azure Storage in organization-specific folder.
        
        Args:
            blob_name: Name of the blob (without organization prefix)
            data: Binary data to upload
            content_type: MIME type of the content
            organization_id: Organization ID for folder isolation (required)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.blob_service_client:
                logger.error("Blob service client not initialized")
                return False
            
            if organization_id is None:
                logger.error("organization_id is required for upload")
                return False
            
            # Prepend organization folder to blob name
            full_blob_name = self._get_org_folder(organization_id) + blob_name
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=full_blob_name
            )
            
            # Upload with content type
            content_settings = None
            if content_type:
                from azure.storage.blob import ContentSettings
                content_settings = ContentSettings(content_type=content_type)
            
            blob_client.upload_blob(
                data,
                overwrite=True,
                content_settings=content_settings
            )
            
            logger.info(f"Successfully uploaded blob: {full_blob_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading blob {blob_name}: {e}")
            return False
    
    def download_blob(self, blob_name: str, organization_id: int = None) -> Optional[bytes]:
        """
        Download a blob from Azure Storage.
        
        Args:
            blob_name: Name of the blob to download (with or without org prefix)
            organization_id: Organization ID (if provided, prepends org folder)
            
        Returns:
            Binary data if successful, None otherwise
        """
        try:
            if not self.blob_service_client:
                logger.error("Blob service client not initialized")
                return None
            
            # If organization_id provided and blob_name doesn't start with "org_", prepend it
            if organization_id and not blob_name.startswith('org_'):
                blob_name = self._get_org_folder(organization_id) + blob_name
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Download blob
            download_stream = blob_client.download_blob()
            data = download_stream.readall()
            
            logger.info(f"Successfully downloaded blob: {blob_name}")
            return data
            
        except ResourceNotFoundError:
            logger.error(f"Blob not found: {blob_name}")
            return None
        except Exception as e:
            logger.error(f"Error downloading blob {blob_name}: {e}")
            return None
    
    def delete_blob(self, blob_name: str, organization_id: int = None) -> bool:
        """
        Delete a blob from Azure Storage.
        
        Args:
            blob_name: Name of the blob to delete (with or without org prefix)
            organization_id: Organization ID (if provided, prepends org folder)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.blob_service_client:
                logger.error("Blob service client not initialized")
                return False
            
            # If organization_id provided and blob_name doesn't start with "org_", prepend it
            if organization_id and not blob_name.startswith('org_'):
                blob_name = self._get_org_folder(organization_id) + blob_name
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Delete blob
            blob_client.delete_blob()
            
            logger.info(f"Successfully deleted blob: {blob_name}")
            return True
            
        except ResourceNotFoundError:
            logger.warning(f"Blob not found (already deleted?): {blob_name}")
            return True  # Consider it successful if already gone
        except Exception as e:
            logger.error(f"Error deleting blob {blob_name}: {e}")
            return False
    
    def blob_exists(self, blob_name: str, organization_id: int = None) -> bool:
        """
        Check if a blob exists in Azure Storage.
        
        Args:
            blob_name: Name of the blob to check (with or without org prefix)
            organization_id: Organization ID (if provided, prepends org folder)
            
        Returns:
            True if exists, False otherwise
        """
        try:
            if not self.blob_service_client:
                return False
            
            # If organization_id provided and blob_name doesn't start with "org_", prepend it
            if organization_id and not blob_name.startswith('org_'):
                blob_name = self._get_org_folder(organization_id) + blob_name
            
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            return blob_client.exists()
            
        except Exception as e:
            logger.error(f"Error checking blob existence {blob_name}: {e}")
            return False
    
    def get_blob_url(self, blob_name: str, organization_id: int = None) -> Optional[str]:
        """
        Get the URL of a blob.
        
        Args:
            blob_name: Name of the blob (with or without org prefix)
            organization_id: Organization ID (if provided, prepends org folder)
            
        Returns:
            URL string if successful, None otherwise
        """
        try:
            if not self.blob_service_client:
                return None
            
            # If organization_id provided and blob_name doesn't start with "org_", prepend it
            if organization_id and not blob_name.startswith('org_'):
                blob_name = self._get_org_folder(organization_id) + blob_name
            
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            return blob_client.url
            
        except Exception as e:
            logger.error(f"Error getting blob URL {blob_name}: {e}")
            return None


# Global service instance
azure_storage_service = AzureStorageService()
