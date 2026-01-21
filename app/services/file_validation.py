import os
import mimetypes
from werkzeug.utils import secure_filename
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class FileValidationService:
    """Service class for file validation and processing."""
    
    # Allowed file extensions and their corresponding MIME types
    ALLOWED_EXTENSIONS = {
        '.pdf': 'application/pdf',
        '.doc': 'application/msword',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
    }
    
    # Maximum file size (16MB)
    MAX_FILE_SIZE = 16 * 1024 * 1024
    
    @classmethod
    def is_allowed_file(cls, filename):
        """
        Check if the file has an allowed extension.
        
        Args:
            filename: Name of the file to check
        
        Returns:
            bool: True if file extension is allowed, False otherwise
        """
        if not filename:
            return False
        
        # Get file extension
        _, ext = os.path.splitext(filename.lower())
        return ext in cls.ALLOWED_EXTENSIONS
    
    @classmethod
    def get_content_type(cls, filename):
        """
        Get the content type for a file based on its extension.
        
        Args:
            filename: Name of the file
        
        Returns:
            str: MIME type of the file, or None if not supported
        """
        if not filename:
            return None
        
        _, ext = os.path.splitext(filename.lower())
        return cls.ALLOWED_EXTENSIONS.get(ext)
    
    @classmethod
    def validate_file_size(cls, file_stream):
        """
        Validate file size without loading entire file into memory.
        
        Args:
            file_stream: File stream to validate
        
        Returns:
            dict: Validation result with success status and file size
        """
        try:
            # Get current position
            current_pos = file_stream.tell()
            
            # Seek to end to get file size
            file_stream.seek(0, 2)  # Seek to end
            file_size = file_stream.tell()
            
            # Reset to original position
            file_stream.seek(current_pos)
            
            if file_size > cls.MAX_FILE_SIZE:
                return {
                    'success': False,
                    'error': f'File size ({cls._format_file_size(file_size)}) exceeds maximum allowed size ({cls._format_file_size(cls.MAX_FILE_SIZE)})',
                    'error_code': 'FILE_TOO_LARGE',
                    'file_size': file_size,
                    'max_size': cls.MAX_FILE_SIZE
                }
            
            return {
                'success': True,
                'file_size': file_size
            }
            
        except Exception as e:
            logger.error(f"Error validating file size: {e}")
            return {
                'success': False,
                'error': 'Unable to determine file size',
                'error_code': 'SIZE_CHECK_ERROR'
            }
    
    @classmethod
    def validate_file_content(cls, file_stream, filename):
        """
        Validate file content by checking file headers/magic numbers.
        
        Args:
            file_stream: File stream to validate
            filename: Original filename
        
        Returns:
            dict: Validation result with success status
        """
        try:
            # Get current position
            current_pos = file_stream.tell()
            
            # Read first few bytes to check file signature
            file_stream.seek(0)
            header = file_stream.read(8)
            
            # Reset to original position
            file_stream.seek(current_pos)
            
            # Get expected content type based on filename
            expected_content_type = cls.get_content_type(filename)
            
            if not expected_content_type:
                return {
                    'success': False,
                    'error': 'Unsupported file type',
                    'error_code': 'UNSUPPORTED_TYPE'
                }
            
            # Check file signatures
            if expected_content_type == 'application/pdf':
                # PDF files start with %PDF
                if not header.startswith(b'%PDF'):
                    return {
                        'success': False,
                        'error': 'File does not appear to be a valid PDF',
                        'error_code': 'INVALID_PDF'
                    }
            
            elif expected_content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
                # DOCX files are ZIP archives, check for ZIP signature
                if not header.startswith(b'PK'):
                    return {
                        'success': False,
                        'error': 'File does not appear to be a valid DOCX document',
                        'error_code': 'INVALID_DOCX'
                    }

            elif expected_content_type == 'application/msword':
                # Legacy .doc files are typically OLE Compound File Binary Format.
                # Check for OLE signature: D0 CF 11 E0 A1 B1 1A E1
                if not header.startswith(b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1'):
                    return {
                        'success': False,
                        'error': 'File does not appear to be a valid DOC document',
                        'error_code': 'INVALID_DOC'
                    }

            elif expected_content_type == 'image/png':
                # PNG signature: 89 50 4E 47 0D 0A 1A 0A
                if header[:8] != b'\x89PNG\r\n\x1a\n':
                    return {
                        'success': False,
                        'error': 'File does not appear to be a valid PNG image',
                        'error_code': 'INVALID_PNG'
                    }

            elif expected_content_type == 'image/jpeg':
                # JPEG files start with FF D8 FF
                if header[:3] != b'\xFF\xD8\xFF':
                    return {
                        'success': False,
                        'error': 'File does not appear to be a valid JPEG image',
                        'error_code': 'INVALID_JPEG'
                    }
            
            return {
                'success': True,
                'content_type': expected_content_type
            }
            
        except Exception as e:
            logger.error(f"Error validating file content: {e}")
            return {
                'success': False,
                'error': 'Unable to validate file content',
                'error_code': 'CONTENT_CHECK_ERROR'
            }
    
    @classmethod
    def sanitize_filename(cls, filename):
        """
        Sanitize filename for safe storage.
        
        Args:
            filename: Original filename
        
        Returns:
            str: Sanitized filename
        """
        if not filename:
            return 'unnamed_file'
        
        # Use werkzeug's secure_filename to sanitize
        safe_filename = secure_filename(filename)
        
        # If secure_filename returns empty string, provide a default
        if not safe_filename:
            _, ext = os.path.splitext(filename)
            safe_filename = f'unnamed_file{ext.lower()}'
        
        # Ensure filename is not too long (limit to 255 characters)
        if len(safe_filename) > 255:
            name, ext = os.path.splitext(safe_filename)
            max_name_length = 255 - len(ext)
            safe_filename = name[:max_name_length] + ext
        
        return safe_filename
    
    @classmethod
    def validate_file(cls, file_stream, filename):
        """
        Comprehensive file validation.
        
        Args:
            file_stream: File stream to validate
            filename: Original filename
        
        Returns:
            dict: Comprehensive validation result
        """
        # Check if file extension is allowed
        if not cls.is_allowed_file(filename):
            return {
                'success': False,
                'error': f'File type not allowed. Supported formats: {", ".join(cls.ALLOWED_EXTENSIONS.keys())}',
                'error_code': 'INVALID_EXTENSION'
            }
        
        # Validate file size
        size_result = cls.validate_file_size(file_stream)
        if not size_result['success']:
            return size_result
        
        # Validate file content
        content_result = cls.validate_file_content(file_stream, filename)
        if not content_result['success']:
            return content_result
        
        # Sanitize filename
        safe_filename = cls.sanitize_filename(filename)
        
        return {
            'success': True,
            'file_size': size_result['file_size'],
            'content_type': content_result['content_type'],
            'safe_filename': safe_filename,
            'original_filename': filename
        }
    
    @classmethod
    def _format_file_size(cls, size_bytes):
        """
        Format file size in human-readable format.
        
        Args:
            size_bytes: Size in bytes
        
        Returns:
            str: Formatted file size
        """
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    @classmethod
    def get_allowed_extensions_list(cls):
        """
        Get list of allowed file extensions for display.
        
        Returns:
            list: List of allowed extensions
        """
        return list(cls.ALLOWED_EXTENSIONS.keys())
    
    @classmethod
    def get_max_file_size_formatted(cls):
        """
        Get maximum file size in formatted string.
        
        Returns:
            str: Formatted maximum file size
        """
        return cls._format_file_size(cls.MAX_FILE_SIZE)