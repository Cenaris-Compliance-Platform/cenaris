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
        self.account_name = "cenarisblobstorage"
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
    
    def upload_blob(self, blob_name: str, data: bytes, content_type: str = None) -> bool:
        """
        Upload a blob to Azure Storage.
        
        Args:
            blob_name: Name of the blob
            data: Binary data to upload
            content_type: MIME type of the content
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.blob_service_client:
                logger.error("Blob service client not initialized")
                return False
            
            # Get blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
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
            
            logger.info(f"Successfully uploaded blob: {blob_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error uploading blob {blob_name}: {e}")
            return False
    
    def download_blob(self, blob_name: str) -> Optional[bytes]:
        """
        Download a blob from Azure Storage.
        
        Args:
            blob_name: Name of the blob to download
            
        Returns:
            Binary data if successful, None otherwise
        """
        try:
            if not self.blob_service_client:
                logger.error("Blob service client not initialized")
                return None
            
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
    
    def delete_blob(self, blob_name: str) -> bool:
        """
        Delete a blob from Azure Storage.
        
        Args:
            blob_name: Name of the blob to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.blob_service_client:
                logger.error("Blob service client not initialized")
                return False
            
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
    
    def blob_exists(self, blob_name: str) -> bool:
        """
        Check if a blob exists in Azure Storage.
        
        Args:
            blob_name: Name of the blob to check
            
        Returns:
            True if exists, False otherwise
        """
        try:
            if not self.blob_service_client:
                return False
            
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            return blob_client.exists()
            
        except Exception as e:
            logger.error(f"Error checking blob existence {blob_name}: {e}")
            return False
    
    def get_blob_url(self, blob_name: str) -> Optional[str]:
        """
        Get the URL of a blob.
        
        Args:
            blob_name: Name of the blob
            
        Returns:
            URL string if successful, None otherwise
        """
        try:
            if not self.blob_service_client:
                return None
            
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
