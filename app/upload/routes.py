from flask import request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.upload import bp
from app.services.azure_storage import AzureBlobStorageService
from app.services.file_validation import FileValidationService
from app.models import Document
from app import db
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

@bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """Handle file upload to Azure Blob Storage."""
    try:
        # Check if file is present in request
        if 'file' not in request.files:
            flash('No file selected. Please choose a file to upload.', 'error')
            return redirect(url_for('main.dashboard'))
        
        file = request.files['file']
        
        # Check if file was actually selected
        if file.filename == '':
            flash('No file selected. Please choose a file to upload.', 'error')
            return redirect(url_for('main.dashboard'))
        
        # Validate the file
        validation_result = FileValidationService.validate_file(file.stream, file.filename)
        
        if not validation_result['success']:
            flash(f"File validation failed: {validation_result['error']}", 'error')
            return redirect(url_for('main.dashboard'))
        
        # Initialize Azure Storage service
        storage_service = AzureBlobStorageService()
        
        if not storage_service.is_configured():
            flash('File upload is currently unavailable. Azure Storage is not configured.', 'error')
            logger.error("Azure Storage not configured for file upload")
            return redirect(url_for('main.dashboard'))
        
        # Generate unique file path for ADLS
        file_path = storage_service.generate_blob_name(
            validation_result['original_filename'], 
            current_user.id,
            organization_id=getattr(current_user, 'organization_id', None)
        )
        
        # Prepare metadata
        metadata = {
            'uploaded_by': str(current_user.id),
            'uploaded_by_email': current_user.email,
            'original_filename': validation_result['original_filename'],
            'upload_timestamp': str(int(datetime.now(timezone.utc).timestamp()))
        }
        
        # Reset file stream position
        file.stream.seek(0)
        
        # Upload to Azure Data Lake Storage
        upload_result = storage_service.upload_file(
            file_stream=file.stream,
            file_path=file_path,
            content_type=validation_result['content_type'],
            metadata=metadata
        )
        
        if not upload_result['success']:
            flash(f"Upload failed: {upload_result['error']}", 'error')
            logger.error(f"Azure upload failed for user {current_user.id}: {upload_result['error']}")
            return redirect(url_for('main.dashboard'))
        
        # Save document metadata to database
        try:
            document = Document(
                filename=validation_result['original_filename'],
                blob_name=file_path,
                file_size=validation_result['file_size'],
                content_type=validation_result['content_type'],
                uploaded_by=current_user.id,
                organization_id=getattr(current_user, 'organization_id', None)
            )
            db.session.add(document)
            db.session.commit()

            storage_type = upload_result.get('storage_type', 'ADLS_Gen2')
            flash(f'File "{validation_result["original_filename"]}" uploaded successfully to {storage_type}!', 'success')
            logger.info(f"File uploaded successfully: {file_path} by user {current_user.id} to {storage_type}")
        
        except Exception as e:
            db.session.rollback()
            # If database save failed, try to clean up the uploaded file
            storage_service.delete_file(file_path)
            flash('Upload failed: Database error occurred.', 'error')
            logger.error(f"Database error during file upload: {e}")
        
        return redirect(url_for('main.dashboard'))
    
    except Exception as e:
        flash('An unexpected error occurred during upload. Please try again.', 'error')
        logger.error(f"Unexpected error in file upload: {e}")
        return redirect(url_for('main.dashboard'))

@bp.route('/upload/validate', methods=['POST'])
@login_required
def validate_file_ajax():
    """AJAX endpoint for client-side file validation."""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided',
                'error_code': 'NO_FILE'
            })
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected',
                'error_code': 'NO_FILE_SELECTED'
            })
        
        # Validate the file
        validation_result = FileValidationService.validate_file(file.stream, file.filename)
        
        if validation_result['success']:
            return jsonify({
                'success': True,
                'file_size': validation_result['file_size'],
                'file_size_formatted': FileValidationService._format_file_size(validation_result['file_size']),
                'content_type': validation_result['content_type'],
                'safe_filename': validation_result['safe_filename']
            })
        else:
            return jsonify(validation_result)
    
    except Exception as e:
        logger.error(f"Error in AJAX file validation: {e}")
        return jsonify({
            'success': False,
            'error': 'Validation error occurred',
            'error_code': 'VALIDATION_ERROR'
        })

@bp.route('/upload/progress/<upload_id>')
@login_required
def upload_progress(upload_id):
    """Get upload progress (placeholder for future implementation)."""
    # This is a placeholder for future upload progress tracking
    return jsonify({
        'success': True,
        'progress': 100,
        'status': 'completed'
    })

@bp.route('/upload/info')
@login_required
def upload_info():
    """Get upload configuration information."""
    return jsonify({
        'success': True,
        'max_file_size': FileValidationService.MAX_FILE_SIZE,
        'max_file_size_formatted': FileValidationService.get_max_file_size_formatted(),
        'allowed_extensions': FileValidationService.get_allowed_extensions_list(),
        'azure_configured': AzureBlobStorageService().is_configured()
    })