import os
import uuid
from datetime import datetime, timezone
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.storage.filedatalake import DataLakeServiceClient, DataLakeFileClient
from azure.core.exceptions import AzureError, ResourceNotFoundError
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class AzureBlobStorageService:
    """Service class for Azure Data Lake Storage Gen2 operations."""
    
    def __init__(self):
        self.connection_string = None
        self.container_name = None
        self.blob_service_client = None
        self.datalake_service_client = None
        self._initialize()
    
    def _initialize(self):
        """Initialize Azure Data Lake Storage Gen2 client."""
        try:
            self.connection_string = current_app.config.get('AZURE_STORAGE_CONNECTION_STRING')
            self.container_name = current_app.config.get('AZURE_CONTAINER_NAME', 'compliance-documents')
            
            if not self.connection_string:
                logger.warning("Azure Storage connection string not configured")
                return
            
            # Initialize both Blob and Data Lake clients for compatibility
            self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
            self.datalake_service_client = DataLakeServiceClient.from_connection_string(self.connection_string)
            
            # Ensure container/file system exists
            self._ensure_container_exists()
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure Data Lake Storage: {e}")
            raise
    
    def _ensure_container_exists(self):
        """Ensure the container/file system exists, create if it doesn't."""
        try:
            # Try to get file system properties (ADLS Gen2)
            file_system_client = self.datalake_service_client.get_file_system_client(self.container_name)
            file_system_client.get_file_system_properties()
            logger.info(f"Using existing ADLS file system: {self.container_name}")
        except ResourceNotFoundError:
            try:
                # Create file system (ADLS Gen2)
                file_system_client = self.datalake_service_client.create_file_system(self.container_name)
                logger.info(f"Created ADLS file system: {self.container_name}")
            except Exception as e:
                # Fallback to blob container creation
                try:
                    container_client = self.blob_service_client.create_container(self.container_name)
                    logger.info(f"Created blob container: {self.container_name}")
                except Exception as blob_error:
                    logger.error(f"Failed to create container/file system {self.container_name}: {e}, {blob_error}")
                    raise
        except Exception as e:
            logger.error(f"Error checking container/file system {self.container_name}: {e}")
            raise
    
    def is_configured(self):
        """Check if Azure Data Lake Storage is properly configured."""
        return (self.connection_string is not None and 
                self.blob_service_client is not None and 
                self.datalake_service_client is not None)
    
    def generate_blob_name(self, original_filename, user_id, organization_id=None):
        """Generate a unique file path for ADLS Gen2."""
        # Get file extension
        file_ext = os.path.splitext(original_filename)[1].lower()
        
        # Generate unique identifier
        unique_id = str(uuid.uuid4())
        
        # Create timestamp
        now = datetime.now(timezone.utc)
        timestamp = now.strftime('%Y%m%d_%H%M%S')
        
        # Create organized folder structure for ADLS
        year = now.strftime('%Y')
        month = now.strftime('%m')
        
        # Combine to create unique file path with organized structure
        if organization_id:
            file_path = (
                f"organizations/{organization_id}/documents/{year}/{month}/"
                f"user_{user_id}/{timestamp}_{unique_id}{file_ext}"
            )
        else:
            file_path = f"compliance-docs/{year}/{month}/user_{user_id}/{timestamp}_{unique_id}{file_ext}"
        
        return file_path
    
    def upload_file(self, file_stream, file_path, content_type=None, metadata=None):
        """
        Upload a file to Azure Data Lake Storage Gen2.
        
        Args:
            file_stream: File stream to upload
            file_path: Path for the file in ADLS
            content_type: MIME type of the file
            metadata: Dictionary of metadata to store with the file
        
        Returns:
            dict: Upload result with success status and file info
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'Azure Data Lake Storage not configured',
                'error_code': 'STORAGE_NOT_CONFIGURED'
            }
        
        try:
            # Try ADLS Gen2 upload first
            try:
                file_system_client = self.datalake_service_client.get_file_system_client(self.container_name)
                file_client = file_system_client.get_file_client(file_path)
                
                # Upload file data
                file_client.upload_data(
                    data=file_stream.read(),
                    overwrite=True,
                    content_settings={'content_type': content_type} if content_type else None,
                    metadata=metadata
                )
                
                # Get file properties
                file_properties = file_client.get_file_properties()
                
                return {
                    'success': True,
                    'file_path': file_path,
                    'size': file_properties.size,
                    'last_modified': file_properties.last_modified,
                    'etag': file_properties.etag,
                    'url': file_client.url,
                    'storage_type': 'ADLS_Gen2'
                }
                
            except Exception as adls_error:
                logger.warning(f"ADLS Gen2 upload failed, falling back to Blob Storage: {adls_error}")
                
                # Fallback to Blob Storage
                file_stream.seek(0)  # Reset stream position
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.container_name,
                    blob=file_path
                )
                
                # Prepare upload parameters
                upload_params = {
                    'data': file_stream,
                    'overwrite': True
                }
                
                if content_type:
                    from azure.storage.blob import ContentSettings
                    upload_params['content_settings'] = ContentSettings(content_type=content_type)
                
                if metadata:
                    upload_params['metadata'] = metadata
                
                # Upload the file
                blob_client.upload_blob(**upload_params)
                
                # Get blob properties to confirm upload
                blob_properties = blob_client.get_blob_properties()
                
                return {
                    'success': True,
                    'file_path': file_path,
                    'size': blob_properties.size,
                    'last_modified': blob_properties.last_modified,
                    'etag': blob_properties.etag,
                    'url': blob_client.url,
                    'storage_type': 'Blob_Storage'
                }
            
        except AzureError as e:
            logger.error(f"Azure error uploading file {file_path}: {e}")
            return {
                'success': False,
                'error': f'Azure storage error: {str(e)}',
                'error_code': 'AZURE_ERROR'
            }
        except Exception as e:
            logger.error(f"Unexpected error uploading file {file_path}: {e}")
            return {
                'success': False,
                'error': f'Upload failed: {str(e)}',
                'error_code': 'UPLOAD_ERROR'
            }
    
    def download_file(self, blob_name):
        """
        Download a file from Azure Blob Storage.
        
        Args:
            blob_name: Name of the blob to download
        
        Returns:
            dict: Download result with success status and file data
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'Azure Storage not configured',
                'error_code': 'STORAGE_NOT_CONFIGURED'
            }
        
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Download the blob
            blob_data = blob_client.download_blob()
            
            # Get blob properties
            blob_properties = blob_client.get_blob_properties()
            
            return {
                'success': True,
                'data': blob_data.readall(),
                'content_type': blob_properties.content_settings.content_type,
                'size': blob_properties.size,
                'last_modified': blob_properties.last_modified
            }
            
        except ResourceNotFoundError:
            logger.error(f"Blob not found: {blob_name}")
            return {
                'success': False,
                'error': 'File not found',
                'error_code': 'FILE_NOT_FOUND'
            }
        except AzureError as e:
            logger.error(f"Azure error downloading file {blob_name}: {e}")
            return {
                'success': False,
                'error': f'Azure storage error: {str(e)}',
                'error_code': 'AZURE_ERROR'
            }
        except Exception as e:
            logger.error(f"Unexpected error downloading file {blob_name}: {e}")
            return {
                'success': False,
                'error': f'Download failed: {str(e)}',
                'error_code': 'DOWNLOAD_ERROR'
            }
    
    def delete_file(self, blob_name):
        """
        Delete a file from Azure Blob Storage.
        
        Args:
            blob_name: Name of the blob to delete
        
        Returns:
            dict: Delete result with success status
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'Azure Storage not configured',
                'error_code': 'STORAGE_NOT_CONFIGURED'
            }
        
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Delete the blob
            blob_client.delete_blob()
            
            return {
                'success': True,
                'message': f'File {blob_name} deleted successfully'
            }
            
        except ResourceNotFoundError:
            logger.warning(f"Attempted to delete non-existent blob: {blob_name}")
            return {
                'success': True,  # Consider it successful if file doesn't exist
                'message': 'File already deleted or does not exist'
            }
        except AzureError as e:
            logger.error(f"Azure error deleting file {blob_name}: {e}")
            return {
                'success': False,
                'error': f'Azure storage error: {str(e)}',
                'error_code': 'AZURE_ERROR'
            }
        except Exception as e:
            logger.error(f"Unexpected error deleting file {blob_name}: {e}")
            return {
                'success': False,
                'error': f'Delete failed: {str(e)}',
                'error_code': 'DELETE_ERROR'
            }
    
    def get_file_url(self, blob_name, expiry_hours=1):
        """
        Generate a signed URL for accessing a blob.
        
        Args:
            blob_name: Name of the blob
            expiry_hours: Hours until the URL expires
        
        Returns:
            dict: Result with success status and URL
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'Azure Storage not configured',
                'error_code': 'STORAGE_NOT_CONFIGURED'
            }
        
        try:
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
            from datetime import timedelta
            
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_name
            )
            
            # Generate SAS token
            sas_token = generate_blob_sas(
                account_name=blob_client.account_name,
                container_name=self.container_name,
                blob_name=blob_name,
                account_key=blob_client.credential.account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
            )
            
            # Construct the full URL
            url = f"{blob_client.url}?{sas_token}"
            
            return {
                'success': True,
                'url': url,
                'expires_in_hours': expiry_hours
            }
            
        except Exception as e:
            logger.error(f"Error generating URL for {blob_name}: {e}")
            return {
                'success': False,
                'error': f'URL generation failed: {str(e)}',
                'error_code': 'URL_ERROR'
            }
    
    def list_files(self, prefix=None):
        """
        List files in the container.
        
        Args:
            prefix: Optional prefix to filter blobs
        
        Returns:
            dict: Result with success status and list of files
        """
        if not self.is_configured():
            return {
                'success': False,
                'error': 'Azure Storage not configured',
                'error_code': 'STORAGE_NOT_CONFIGURED'
            }
        
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            
            blobs = container_client.list_blobs(name_starts_with=prefix)
            
            file_list = []
            for blob in blobs:
                file_list.append({
                    'name': blob.name,
                    'size': blob.size,
                    'last_modified': blob.last_modified,
                    'content_type': blob.content_settings.content_type if blob.content_settings else None
                })
            
            return {
                'success': True,
                'files': file_list,
                'count': len(file_list)
            }
            
        except AzureError as e:
            logger.error(f"Azure error listing files: {e}")
            return {
                'success': False,
                'error': f'Azure storage error: {str(e)}',
                'error_code': 'AZURE_ERROR'
            }
        except Exception as e:
            logger.error(f"Unexpected error listing files: {e}")
            return {
                'success': False,
                'error': f'List operation failed: {str(e)}',
                'error_code': 'LIST_ERROR'
            }