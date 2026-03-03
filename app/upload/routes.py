from flask import request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.upload import bp
from app.services.azure_storage import AzureBlobStorageService
from app.services.file_validation import FileValidationService
from app.services.notification_service import notification_service
from app.models import Document, Organization, OrganizationMembership
from app import db, invalidate_org_switcher_context_cache
from datetime import datetime, timezone
import logging
import re
import os

logger = logging.getLogger(__name__)

def get_versioned_filename(original_filename, organization_id):
    """
    Check if filename exists in the organization and return a versioned name if needed.
    E.g., policy.pdf -> policy (1).pdf -> policy (2).pdf
    """
    # Check if the exact filename already exists
    existing = Document.query.filter_by(
        filename=original_filename,
        organization_id=organization_id
    ).first()
    
    if not existing:
        # Filename doesn't exist, use original
        return original_filename
    
    # Parse filename and extension
    name, ext = os.path.splitext(original_filename)
    
    # Find all files with similar names (e.g., "policy.pdf", "policy (1).pdf", "policy (2).pdf")
    # Pattern: "name (number).ext"
    pattern = re.escape(name) + r'(?: \((\d+)\))?' + re.escape(ext)
    
    all_docs = Document.query.filter_by(organization_id=organization_id).all()
    
    version_numbers = []
    for doc in all_docs:
        match = re.fullmatch(pattern, doc.filename)
        if match:
            version_str = match.group(1)
            if version_str:
                version_numbers.append(int(version_str))
            else:
                version_numbers.append(0)  # Original file without version number
    
    if not version_numbers:
        return original_filename
    
    # Find the next available version number
    next_version = max(version_numbers) + 1
    return f"{name} ({next_version}){ext}"

@bp.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """Handle single or bulk file upload to Azure Blob Storage."""
    try:
        # Remember where user came from to redirect back after upload
        referrer = request.referrer or url_for('main.dashboard')
        
        org_id = getattr(current_user, 'organization_id', None)
        if not org_id:
            flash('Please select an organisation before uploading.', 'info')
            return redirect(url_for('onboarding.organization'))

        if not current_user.has_permission('documents.upload', org_id=int(org_id)):
            flash('You do not have permission to upload documents.', 'error')
            return redirect(referrer)

        membership = (
            OrganizationMembership.query
            .filter_by(user_id=int(current_user.id), organization_id=int(org_id), is_active=True)
            .first()
        )
        if not membership:
            flash('You do not have access to that organisation.', 'error')
            return redirect(url_for('onboarding.organization'))

        organization = db.session.get(Organization, int(org_id))
        if not organization:
            flash('Organisation not found.', 'error')
            return redirect(url_for('onboarding.organization'))

        # Billing can be deferred; do not block document uploads.
        # (Billing gating is applied for reports/exports elsewhere.)
        if not organization.billing_complete():
            flash('Billing details are incomplete. You can still upload documents.', 'warning')

        incoming_files = []
        if 'files' in request.files:
            incoming_files.extend([f for f in request.files.getlist('files') if f and (f.filename or '').strip()])
        if 'file' in request.files:
            single = request.files['file']
            if single and (single.filename or '').strip():
                incoming_files.append(single)

        if not incoming_files:
            flash('No file selected. Please choose a file to upload.', 'error')
            return redirect(referrer)
        
        # Initialize Azure Storage service
        storage_service = AzureBlobStorageService()
        
        if not storage_service.is_configured():
            flash('File upload is currently unavailable. Azure Storage is not configured.', 'error')
            logger.error("Azure Storage not configured for file upload")
            return redirect(referrer)
        
        success_count = 0
        failed_count = 0

        for file in incoming_files:
            validation_result = FileValidationService.validate_file(file.stream, file.filename)
            if not validation_result['success']:
                failed_count += 1
                flash(f"{file.filename}: {validation_result['error']}", 'error')
                continue

            versioned_filename = get_versioned_filename(validation_result['original_filename'], int(org_id))

            file_path = storage_service.generate_blob_name(
                validation_result['original_filename'],
                current_user.id,
                organization_id=int(org_id),
            )

            metadata = {
                'uploaded_by': str(current_user.id),
                'uploaded_by_email': current_user.email,
                'original_filename': versioned_filename,
                'upload_timestamp': str(int(datetime.now(timezone.utc).timestamp())),
            }

            file.stream.seek(0)
            upload_result = storage_service.upload_file(
                file_stream=file.stream,
                file_path=file_path,
                content_type=validation_result['content_type'],
                metadata=metadata,
            )

            if not upload_result['success']:
                failed_count += 1
                flash(f"{file.filename}: {upload_result['error']}", 'error')
                logger.error(f"Azure upload failed for user {current_user.id}: {upload_result['error']}")
                continue

            try:
                db_content_type = (validation_result.get('content_type') or '').strip() or None
                if db_content_type and len(db_content_type) > 50:
                    db_content_type = db_content_type[:50]

                document = Document(
                    filename=versioned_filename,
                    blob_name=file_path,
                    file_size=validation_result['file_size'],
                    content_type=db_content_type,
                    search_text=f"{versioned_filename} {db_content_type or ''}".strip(),
                    uploaded_by=current_user.id,
                    organization_id=int(org_id),
                )
                db.session.add(document)
                db.session.commit()
                success_count += 1

                try:
                    notification_service.create_admin_notification(
                        organization_id=int(org_id),
                        actor_user_id=int(current_user.id),
                        event_type='document_uploaded',
                        title='Document uploaded',
                        message=f'{current_user.display_name()} uploaded "{versioned_filename}".',
                        severity='info',
                        link_url=url_for('main.evidence_repository'),
                        payload={
                            'document_id': int(document.id),
                            'filename': versioned_filename,
                            'file_size': int(validation_result.get('file_size') or 0),
                        },
                        send_email=False,
                    )
                    invalidate_org_switcher_context_cache(int(current_user.id), int(org_id))
                except Exception:
                    logger.exception('Failed to create upload notification for org %s', org_id)

            except Exception as e:
                db.session.rollback()
                storage_service.delete_file(file_path)
                failed_count += 1
                logger.error(f"Database error during file upload: {e}")

        if success_count > 0:
            flash(f'Uploaded {success_count} file(s) successfully.', 'success')
        if failed_count > 0:
            flash(f'{failed_count} file(s) failed to upload.', 'warning')
        if success_count == 0 and failed_count > 0:
            flash('Upload failed. Please review errors and try again.', 'error')
        
        return redirect(referrer)
    
    except Exception as e:
        flash('An unexpected error occurred during upload. Please try again.', 'error')
        logger.error(f"Unexpected error in file upload: {e}")
        return redirect(referrer if 'referrer' in locals() else url_for('main.dashboard'))

@bp.route('/upload/validate', methods=['POST'])
@login_required
def validate_file_ajax():
    """AJAX endpoint for client-side file validation."""
    try:
        org_id = getattr(current_user, 'organization_id', None)
        if not org_id or not current_user.has_permission('documents.upload', org_id=int(org_id)):
            return jsonify({'success': False, 'error': 'Not authorized', 'error_code': 'NOT_AUTHORIZED'}), 403

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