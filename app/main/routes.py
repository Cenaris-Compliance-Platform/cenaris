from flask import render_template, redirect, url_for, jsonify, request, make_response, flash, abort, current_app
from flask_login import login_required, current_user
from app.main import bp
from app.models import Document, Organization, OrganizationMembership, User
from app import db, mail
from app.services.azure_data_service import azure_data_service

from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer


def _active_org_id() -> int | None:
    org_id = getattr(current_user, 'organization_id', None)
    return int(org_id) if org_id else None


def _require_active_org():
    org_id = _active_org_id()
    if not org_id:
        flash('Please select an organization to continue.', 'info')
        return redirect(url_for('onboarding.organization'))

    membership = (
        OrganizationMembership.query
        .filter_by(user_id=int(current_user.id), organization_id=int(org_id), is_active=True)
        .first()
    )
    if not membership:
        flash('You do not have access to that organization.', 'error')
        return redirect(url_for('onboarding.organization'))
    return None


def _require_org_admin():
    maybe = _require_active_org()
    if maybe is not None:
        return maybe
    if not current_user.is_org_admin(_active_org_id()):
        abort(403)
    return None


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _mail_configured() -> bool:
    return bool(current_app.config.get('MAIL_SERVER') and current_app.config.get('MAIL_DEFAULT_SENDER'))


def _password_reset_token(user: User) -> str:
    # Must match the implementation in auth/routes.py
    return _serializer().dumps({'user_id': user.id, 'email': user.email}, salt='password-reset')


def _send_invite_email(user: User, reset_url: str, organization: Organization) -> None:
    if not _mail_configured():
        current_app.logger.warning('MAIL not configured; invite reset URL: %s', reset_url)
        return

    msg = Message(
        subject=f"You're invited to {organization.name}",
        recipients=[user.email],
        body=(
            f"You've been invited to join {organization.name} on Cenaris.\n\n"
            f"Set your password here: {reset_url}\n\n"
            "If you weren't expecting this invite, you can ignore this email."
        ),
    )
    mail.send(msg)


@bp.route('/org/switch', methods=['POST'])
@login_required
def switch_organization():
    """Switch the active organization for the current user."""
    org_id_raw = (request.form.get('organization_id') or '').strip()
    if not org_id_raw.isdigit():
        flash('Invalid organization.', 'error')
        return redirect(url_for('main.dashboard'))

    org_id = int(org_id_raw)
    membership = (
        OrganizationMembership.query
        .filter_by(user_id=int(current_user.id), organization_id=org_id, is_active=True)
        .first()
    )
    if not membership:
        flash('You do not have access to that organization.', 'error')
        return redirect(url_for('main.dashboard'))

    current_user.organization_id = org_id
    db.session.commit()
    flash('Organization switched.', 'success')
    return redirect(request.referrer or url_for('main.dashboard'))


@bp.route('/org/admin')
@login_required
def org_admin_dashboard():
    """Organization admin overview."""
    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

    from app.main.forms import InviteMemberForm, MembershipActionForm

    org_id = _active_org_id()
    organization = Organization.query.get(org_id)
    if not organization:
        abort(404)

    members = (
        OrganizationMembership.query
        .filter_by(organization_id=int(org_id))
        .join(User, User.id == OrganizationMembership.user_id)
        .order_by(OrganizationMembership.is_active.desc(), User.email.asc())
        .all()
    )

    user_count = sum(1 for m in members if bool(m.is_active))
    document_count = Document.query.filter_by(organization_id=int(org_id), is_active=True).count()

    invite_form = InviteMemberForm()
    member_action_form = MembershipActionForm()

    return render_template(
        'main/org_admin_dashboard.html',
        title='Org Admin Dashboard',
        organization=organization,
        members=members,
        user_count=user_count,
        document_count=document_count,
        invite_form=invite_form,
        member_action_form=member_action_form,
    )


@bp.route('/org/admin/invite', methods=['POST'])
@login_required
def org_admin_invite_member():
    """Invite/add a user to the active organization by email."""
    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

    from app.main.forms import InviteMemberForm
    from datetime import datetime, timezone

    org_id = _active_org_id()
    organization = Organization.query.get(int(org_id))
    if not organization:
        abort(404)

    form = InviteMemberForm()
    if not form.validate_on_submit():
        flash('Please correct the invite form errors and try again.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    email = (form.email.data or '').strip().lower()
    role = (form.role.data or 'User').strip()
    if role not in {'User', 'Admin'}:
        role = 'User'

    user = User.query.filter_by(email=email).first()
    created_user = False
    try:
        if not user:
            user = User(
                email=email,
                role='User',
                email_verified=False,
                is_active=True,
                created_at=datetime.now(timezone.utc),
                organization_id=int(org_id),
            )
            db.session.add(user)
            db.session.flush()
            created_user = True

        membership = (
            OrganizationMembership.query
            .filter_by(organization_id=int(org_id), user_id=int(user.id))
            .first()
        )
        if membership:
            membership.is_active = True
            membership.role = role
        else:
            membership = OrganizationMembership(
                organization_id=int(org_id),
                user_id=int(user.id),
                role=role,
                is_active=True,
            )
            db.session.add(membership)

        # Only set a default active org for the user if they don't have one.
        if not getattr(user, 'organization_id', None):
            user.organization_id = int(org_id)

        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('Failed to invite member. Please try again.', 'error')
        current_app.logger.exception('Failed inviting member')
        return redirect(url_for('main.org_admin_dashboard'))

    # Send invite email with password-set link (works for both existing + new users).
    try:
        token = _password_reset_token(user)
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        _send_invite_email(user, reset_url, organization)
    except Exception:
        current_app.logger.exception('Failed to send invite email')

    if created_user:
        flash('User created and added to the organization. Invite email sent (or logged if mail not configured).', 'success')
    else:
        flash('User added to the organization. Invite email sent (or logged if mail not configured).', 'success')
    return redirect(url_for('main.org_admin_dashboard'))


@bp.route('/org/admin/members/disable', methods=['POST'])
@login_required
def org_admin_disable_member():
    """Disable a user's membership in the active organization."""
    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

    from app.main.forms import MembershipActionForm

    org_id = _active_org_id()
    form = MembershipActionForm()
    if not form.validate_on_submit():
        flash('Invalid request.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    membership_id_raw = (form.membership_id.data or '').strip()
    if not membership_id_raw.isdigit():
        flash('Invalid membership.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    membership_id = int(membership_id_raw)
    membership = OrganizationMembership.query.get(membership_id)
    if not membership or int(membership.organization_id) != int(org_id):
        flash('Membership not found.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    if int(membership.user_id) == int(current_user.id):
        flash('You cannot disable your own access.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    # Guard: do not disable the last active admin.
    is_admin = (membership.role or '').strip().lower() == 'admin'
    if is_admin and membership.is_active:
        active_admins = (
            OrganizationMembership.query
            .filter_by(organization_id=int(org_id), is_active=True)
            .filter(OrganizationMembership.role.ilike('admin'))
            .count()
        )
        if active_admins <= 1:
            flash('You cannot disable the last admin for this organization.', 'error')
            return redirect(url_for('main.org_admin_dashboard'))

    try:
        membership.is_active = False
        db.session.commit()
        flash('Member disabled.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to disable member. Please try again.', 'error')
        current_app.logger.exception('Failed disabling member')

    return redirect(url_for('main.org_admin_dashboard'))


@bp.route('/theme', methods=['POST'])
def set_theme():
    """Persist theme preference in a cookie (light/dark)."""
    theme = (request.form.get('theme') or '').strip().lower()
    if theme not in {'light', 'dark'}:
        theme = 'light'

    # Redirect back to the originating page when possible.
    next_url = (request.form.get('next') or '').strip()
    if next_url and next_url.startswith('/'):
        redirect_target = next_url
    elif request.referrer:
        redirect_target = request.referrer
    else:
        redirect_target = url_for('main.dashboard') if current_user.is_authenticated else url_for('main.index')

    resp = make_response(redirect(redirect_target))
    resp.set_cookie(
        'theme',
        theme,
        max_age=60 * 60 * 24 * 365,  # 1 year
        samesite='Lax',
        secure=bool(request.is_secure),
    )
    return resp

def get_mock_ml_summary():
    """Get mock ML summary data"""
    from datetime import datetime
    
    class FileSummary:
        def __init__(self, data):
            self.file_name = data['file_name']
            self.overall_status = data['overall_status']
            self.compliance_score = data['compliance_score']
            self.compliancy_rate = data['compliance_score']  # Add this for templates
            self.requirements_met = data['requirements_met']
            self.requirements_total = data['requirements_total']
            self.total_requirements = data['requirements_total']  # Add this for templates
            self.last_analyzed = data['last_analyzed']
    
    class MLSummary:
        def __init__(self):
            self.total_files = (
                Document.query.filter_by(uploaded_by=current_user.id, is_active=True).count()
                if current_user.is_authenticated
                else 3
            )
            self.avg_compliancy_rate = 85.5
            self.total_complete = 3
            self.total_needs_review = 1
            self.total_missing = 1
            self.last_updated = datetime.now()
            self.connection_status = 'Connected'
            self.adls_path = 'abfss://processed-doc-intel@cenarisblobstorage.dfs.core.windows.net/compliance-results'
            self.file_summaries = [
                FileSummary({
                    'file_name': 'policy_document.csv',
                    'overall_status': 'Complete',
                    'compliance_score': 92,
                    'requirements_met': 15,
                    'requirements_total': 18,
                    'last_analyzed': '2025-11-02'
                }),
                FileSummary({
                    'file_name': 'access_control.csv',
                    'overall_status': 'Needs Review',
                    'compliance_score': 78,
                    'requirements_met': 12,
                    'requirements_total': 16,
                    'last_analyzed': '2025-11-01'
                })
            ]
    
    return MLSummary()

@bp.route('/')
def index():
    """Home page route."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('main/index.html', title='Home')

@bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard route for authenticated users."""
    maybe = _require_active_org()
    if maybe is not None:
        return maybe

    org_id = _active_org_id()
    recent_documents = (
        Document.query.filter_by(organization_id=org_id, is_active=True)
        .order_by(Document.uploaded_at.desc())
        .limit(5)
        .all()
    )
    total_documents = Document.query.filter_by(organization_id=org_id, is_active=True).count()
    
    # Get real ADLS data
    ml_summary = azure_data_service.get_dashboard_summary(user_id=current_user.id)
    
    return render_template('main/dashboard.html', 
                         title='Dashboard',
                         recent_documents=recent_documents,
                         total_documents=total_documents,
                         ml_summary=ml_summary)

@bp.route('/upload')
@login_required
def upload():
    """Upload page route."""
    maybe = _require_active_org()
    if maybe is not None:
        return maybe
    return render_template('main/upload.html', title='Upload Document')

@bp.route('/documents')
@login_required
def documents():
    """Documents listing route."""
    maybe = _require_active_org()
    if maybe is not None:
        return maybe

    org_id = _active_org_id()
    query = Document.query.filter_by(organization_id=org_id, is_active=True)
    user_documents = query.order_by(Document.uploaded_at.desc()).all()
    return render_template('main/documents.html', 
                         title='My Documents',
                         documents=user_documents)

@bp.route('/evidence-repository')
@login_required
def evidence_repository():
    """Evidence repository route to display all documents."""
    maybe = _require_active_org()
    if maybe is not None:
        return maybe

    org_id = _active_org_id()
    query = Document.query.filter_by(organization_id=org_id, is_active=True)
    documents = query.order_by(Document.uploaded_at.desc()).all()
    return render_template('main/evidence_repository.html', 
                         title='Evidence Repository',
                         documents=documents)

@bp.route('/document/<int:doc_id>/download')
@login_required
def download_document(doc_id):
    """Download a document."""
    maybe = _require_active_org()
    if maybe is not None:
        return maybe

    from flask import send_file, abort
    from app.services.azure_storage_service import azure_storage_service
    import io
    
    # Get document from database
    document = Document.query.get(doc_id)
    
    # Check if document exists and belongs to user
    org_id = _active_org_id()
    if not document:
        abort(404)
    if document.organization_id != org_id:
        abort(404)
    
    try:
        # Download from Azure Blob Storage
        blob_data = azure_storage_service.download_blob(document.blob_name)
        
        # Create file-like object
        file_stream = io.BytesIO(blob_data)
        file_stream.seek(0)
        
        # Send file to user
        return send_file(
            file_stream,
            mimetype=document.content_type,
            as_attachment=True,
            download_name=document.filename
        )
    except Exception as e:
        print(f"Error downloading document: {e}")
        abort(500)

@bp.route('/document/<int:doc_id>/delete', methods=['POST'])
@login_required
def delete_document(doc_id):
    """Delete a document."""
    maybe = _require_active_org()
    if maybe is not None:
        return maybe

    from flask import flash, redirect
    from app.services.azure_storage_service import azure_storage_service
    
    # Get document from database
    document = Document.query.get(doc_id)
    
    # Check if document exists and belongs to user
    org_id = _active_org_id()
    if not document:
        flash('Document not found or access denied.', 'error')
        return redirect(url_for('main.evidence_repository'))
    if document.organization_id != org_id:
        flash('Document not found or access denied.', 'error')
        return redirect(url_for('main.evidence_repository'))
    
    try:
        # Delete from Azure Blob Storage
        azure_storage_service.delete_blob(document.blob_name)
        
        # Soft delete from database
        document.is_active = False
        db.session.commit()
        
        flash(f'Document "{document.filename}" deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting document: {e}")
        flash('Error deleting document. Please try again.', 'error')
    
    return redirect(url_for('main.evidence_repository'))

@bp.route('/document/<int:doc_id>/details')
@login_required
def document_details(doc_id):
    """View document details."""
    maybe = _require_active_org()
    if maybe is not None:
        return maybe

    from flask import abort
    
    # Get document from database
    document = Document.query.get(doc_id)
    
    # Check if document exists and belongs to user
    org_id = _active_org_id()
    if not document:
        abort(404)
    if document.organization_id != org_id:
        abort(404)
    
    return render_template('main/document_details.html',
                         title=f'Document: {document.filename}',
                         document=document)

@bp.route('/ai-evidence')
@login_required
def ai_evidence():
    """AI Evidence route to display AI-generated evidence entries."""
    # Get real ADLS data
    summary = azure_data_service.get_dashboard_summary(user_id=current_user.id)
    
    # Transform ADLS data into AI evidence entries
    ai_evidence_entries = []
    
    if summary.get('file_summaries'):
        for idx, file_summary in enumerate(summary['file_summaries'], 1):
            # Get framework details from the file
            frameworks_data = file_summary.get('frameworks', [])
            
            for framework_data in frameworks_data:
                ai_evidence_entries.append({
                    'id': idx,
                    'document_title': f"{framework_data['name']} Compliance Analysis",
                    'framework': framework_data['name'],
                    'source': 'ADLS',
                    'document_type': 'Compliance Summary',
                    'confidence_score': round(framework_data['score'], 1),  # Score is already a percentage
                    'status': framework_data['status'],
                    'upload_date': file_summary.get('last_updated'),
                    'summary': f"Compliance score: {framework_data['score']}% - Status: {framework_data['status']}"
                })
    
    return render_template('main/ai_evidence.html', 
                         title='AI Evidence',
                         ai_evidence_entries=ai_evidence_entries)


@bp.route('/organization/settings', methods=['GET', 'POST'])
@login_required
def organization_settings():
    from flask import abort, flash, make_response, request
    from app.main.forms import OrganizationBillingForm, OrganizationProfileSettingsForm
    import uuid

    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

    if not getattr(current_user, 'organization_id', None):
        flash('No organization is associated with this account.', 'error')
        return redirect(url_for('main.dashboard'))

    organization = Organization.query.get(current_user.organization_id)
    if not organization:
        abort(404)

    profile_form = OrganizationProfileSettingsForm(obj=organization)
    billing_form = OrganizationBillingForm(obj=organization)

    if request.method == 'POST':
        submitted = (request.form.get('form_name') or '').strip()

        if submitted == 'profile':
            if profile_form.validate_on_submit():
                organization.name = profile_form.name.data.strip()
                organization.abn = (profile_form.abn.data or '').strip() or None
                organization.address = (profile_form.address.data or '').strip() or None
                organization.contact_email = (profile_form.contact_email.data or '').strip().lower() or None

                logo_file = profile_form.logo.data
                if logo_file and getattr(logo_file, 'filename', ''):
                    ext = (logo_file.filename.rsplit('.', 1)[-1] or '').lower()
                    safe_ext = ext if ext in {'png', 'jpg', 'jpeg', 'webp'} else 'png'
                    unique = uuid.uuid4().hex
                    blob_name = f"organizations/{organization.id}/branding/logo_{unique}.{safe_ext}"
                    content_type = getattr(logo_file, 'mimetype', None)

                    from app.services.azure_storage_service import azure_storage_service
                    data = logo_file.read()
                    if not azure_storage_service.upload_blob(blob_name, data, content_type=content_type):
                        flash('Logo upload failed. Check Azure Storage configuration.', 'error')
                        return render_template(
                            'main/organization_settings.html',
                            title='Organization Settings',
                            profile_form=profile_form,
                            billing_form=billing_form,
                            organization=organization,
                        )

                    organization.logo_blob_name = blob_name
                    organization.logo_content_type = content_type

                try:
                    db.session.commit()
                    flash('Organization profile saved.', 'success')
                    return redirect(url_for('main.organization_settings'))
                except Exception:
                    db.session.rollback()
                    flash('Failed to save organization profile. Please try again.', 'error')

        elif submitted == 'billing':
            if billing_form.validate_on_submit():
                organization.billing_email = (billing_form.billing_email.data or '').strip().lower() or None
                organization.billing_address = (billing_form.billing_address.data or '').strip() or None

                try:
                    db.session.commit()
                    flash('Billing details saved.', 'success')
                    return redirect(url_for('main.organization_settings'))
                except Exception:
                    db.session.rollback()
                    flash('Failed to save billing details. Please try again.', 'error')
        else:
            flash('Invalid form submission.', 'error')

    return render_template(
        'main/organization_settings.html',
        title='Organization Settings',
        profile_form=profile_form,
        billing_form=billing_form,
        organization=organization,
    )


@bp.route('/organization/logo')
@login_required
def organization_logo():
    from flask import abort, send_file
    import io
    org_id = getattr(current_user, 'organization_id', None)
    if not org_id:
        abort(404)

    organization = Organization.query.get(org_id)
    if not organization or not organization.logo_blob_name:
        abort(404)

    from app.services.azure_storage_service import azure_storage_service
    blob_data = azure_storage_service.download_blob(organization.logo_blob_name)
    if not blob_data:
        abort(404)

    file_stream = io.BytesIO(blob_data)
    file_stream.seek(0)
    return send_file(
        file_stream,
        mimetype=organization.logo_content_type or 'application/octet-stream',
        as_attachment=False,
        download_name='logo'
    )

@bp.route('/ai-evidence/<int:entry_id>')
@login_required
def ai_evidence_detail(entry_id):
    """AI Evidence detail view."""
    # Mock detailed data
    ai_evidence_detail = {
        'id': entry_id,
        'document_title': 'SOX Compliance Report Q3 2025',
        'framework': 'SOX',
        'requirement': 'Section 404 - Internal Controls',
        'confidence_score': 92,
        'status': 'Complete',
        'date_analyzed': '2025-11-01',
        'evidence_type': 'Policy Document',
        'key_findings': 'Strong internal control framework documented',
        'summary': 'Comprehensive SOX compliance documentation covering internal control requirements and audit procedures.',
        'detailed_analysis': 'The document provides comprehensive coverage of internal control requirements...',
        'recommendations': ['Continue monitoring', 'Update quarterly']
    }
    
    return render_template('main/ai_evidence_detail.html', 
                         title='AI Evidence Detail',
                         entry=ai_evidence_detail)

@bp.route('/document/<int:doc_id>')
@login_required
def document_detail(doc_id):
    """Document detail route."""
    document = Document.query.get(doc_id)
    if not document or document.uploaded_by != current_user.id:
        return redirect(url_for('main.documents'))
    
    return render_template('main/document_detail.html',
                         title=f'Document: {document.filename}',
                         document=document)

@bp.route('/gap-analysis')
@login_required
def gap_analysis():
    """Gap Analysis route."""
    import logging
    logger = logging.getLogger(__name__)
    
    # Get real ADLS data
    print("\n" + "="*60)
    print("GAP ANALYSIS - Starting data fetch")
    print("="*60)
    
    summary = azure_data_service.get_dashboard_summary(user_id=current_user.id)
    
    print(f"Connection Status: {summary.get('connection_status')}")
    print(f"Total Files: {summary.get('total_files')}")
    print(f"File Summaries: {len(summary.get('file_summaries', []))}")
    
    logger.info(f"Gap Analysis - Summary: {summary}")
    logger.info(f"Gap Analysis - File summaries count: {len(summary.get('file_summaries', []))}")
    
    # Build gap analysis data from ADLS
    gap_data = []
    
    if summary.get('file_summaries'):
        print(f"\nProcessing {len(summary['file_summaries'])} file summaries...")
        for file_summary in summary['file_summaries']:
            frameworks_data = file_summary.get('frameworks', [])
            print(f"  File: {file_summary.get('file_name')}")
            print(f"  Frameworks: {frameworks_data}")
            logger.info(f"Gap Analysis - Frameworks in {file_summary.get('file_name')}: {frameworks_data}")
            
            for framework_data in frameworks_data:
                # Map status from ADLS to display format
                status = framework_data.get('status', '').strip()
                if status.lower() == 'complete':
                    display_status = 'Complete'
                elif status.lower() == 'needs review':
                    display_status = 'Needs Review'
                elif status.lower() == 'missing':
                    display_status = 'Missing'
                else:
                    display_status = status
                
                item = {
                    'requirement_name': framework_data['name'],
                    'status': display_status,
                    'completion_percentage': round(framework_data['score'], 1),  # Score is already a percentage
                    'supporting_evidence': file_summary.get('file_name', 'compliance_summary.csv'),
                    'last_updated': file_summary.get('last_updated')
                }
                print(f"    Adding: {item['requirement_name']} - {item['completion_percentage']}% - {item['status']}")
                gap_data.append(item)
    else:
        print("  No file summaries found!")
    
    print(f"\nTotal gap_data items: {len(gap_data)}")
    logger.info(f"Gap Analysis - Total gap_data items: {len(gap_data)}")
    
    # Log if no data found
    if not gap_data:
        logger.warning("No data from ADLS - showing empty state")
    
    # Calculate summary stats from gap_data
    total = len(gap_data)
    met = len([g for g in gap_data if g['status'] == 'Complete'])
    pending = len([g for g in gap_data if g['status'] == 'Needs Review'])
    not_met = len([g for g in gap_data if g['status'] == 'Missing'])
    
    # Calculate overall compliance percentage from average of all framework scores
    if gap_data:
        avg_percentage = sum([g['completion_percentage'] for g in gap_data]) / len(gap_data)
    else:
        avg_percentage = 0
    
    summary_stats = {
        'total': total,
        'met': met,
        'pending': pending,
        'not_met': not_met,
        'compliance_percentage': int(avg_percentage)
    }
    
    logger.info(f"Gap Analysis - Summary stats: {summary_stats}")
    logger.info(f"Gap Analysis - Rendering with {len(gap_data)} items")
    
    return render_template('main/gap_analysis.html',
                         title='Gap Analysis',
                         gaps=[],  # Keep for backward compatibility
                         gap_data=gap_data,
                         summary_stats=summary_stats,
                         ml_summary=summary)

@bp.route('/reports')
@login_required
def reports():
    """Reports route."""
    reports = [
        {
            'id': 1,
            'name': 'ISO 27001 Compliance Report',
            'description': 'Comprehensive assessment of ISO 27001 compliance status',
            'type': 'Compliance Assessment',
            'generated_date': '2024-10-13',
            'status': 'Complete',
            'download_url': '#'
        }
    ]
    
    return render_template('main/reports.html', 
                         title='Compliance Reports',
                         reports=reports)

@bp.route('/settings')
@login_required
def settings():
    """Settings route."""
    return render_template('main/settings.html', title='Settings')

@bp.route('/help')
@login_required
def help():
    """Help route."""
    return render_template('main/help.html', title='Help & Documentation')

@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """User profile route."""
    from flask import flash
    from app.main.forms import UserAvatarForm

    form = UserAvatarForm()
    if form.validate_on_submit():
        avatar_file = form.avatar.data
        if avatar_file and getattr(avatar_file, 'filename', ''):
            from uuid import uuid4
            ext = (avatar_file.filename.rsplit('.', 1)[-1] or '').lower()
            safe_ext = ext if ext in {'png', 'jpg', 'jpeg', 'webp'} else 'png'
            unique = uuid4().hex
            blob_name = f"users/{current_user.id}/avatar_{unique}.{safe_ext}"
            content_type = getattr(avatar_file, 'mimetype', None)
            data = avatar_file.read()

            from app.services.azure_storage_service import azure_storage_service
            if not azure_storage_service.upload_blob(blob_name, data, content_type=content_type):
                flash('Profile photo upload failed. Check Azure Storage configuration.', 'error')
            else:
                current_user.avatar_blob_name = blob_name
                current_user.avatar_content_type = content_type
                db.session.commit()
                flash('Profile photo updated.', 'success')
                return redirect(url_for('main.profile'))

    return render_template('main/profile.html', title='My Profile', form=form)


@bp.route('/profile/avatar')
@login_required
def profile_avatar():
    """Serve the current user's avatar image."""
    from flask import abort, send_file
    import io

    if not getattr(current_user, 'avatar_blob_name', None):
        abort(404)

    from app.services.azure_storage_service import azure_storage_service
    blob_data = azure_storage_service.download_blob(current_user.avatar_blob_name)
    if not blob_data:
        abort(404)

    file_stream = io.BytesIO(blob_data)
    file_stream.seek(0)
    return send_file(
        file_stream,
        mimetype=getattr(current_user, 'avatar_content_type', None) or 'application/octet-stream',
        as_attachment=False,
        download_name='avatar'
    )

@bp.route('/notifications')
@login_required
def notifications():
    """Notifications route."""
    notifications = [
        {
            'id': 1,
            'title': 'New compliance requirement detected',
            'message': 'ISO 27001:2022 update requires additional documentation',
            'type': 'warning',
            'timestamp': '2024-10-13 14:30:00',
            'read': False
        }
    ]
    
    return render_template('main/notifications.html', 
                         title='Notifications',
                         notifications=notifications)

@bp.route('/ml-results')
@login_required
def ml_results():
    """ML Results dashboard."""
    compliance_files = [
        {
            'file_name': 'policy_document.pdf',
            'compliance_score': 85,
            'status': 'Complete',
            'last_analyzed': '2025-11-02'
        }
    ]
    
    return render_template('main/ml_results.html',
                         title='ML Analysis Results',
                         ml_summary=get_mock_ml_summary(),
                         compliance_files=compliance_files)

@bp.route('/ml-file-detail/<path:file_path>')
@login_required
def ml_file_detail(file_path):
    """Detailed view of ML analysis file."""
    file_analysis = {
        'file_name': file_path,
        'compliance_score': 85,
        'compliancy_rate': 85,  # Add this for templates
        'requirements': [
            {'name': 'Access Control', 'status': 'Met', 'confidence': 0.9}
        ]
    }
    
    return render_template('main/ml_file_detail.html',
                         title=f'Analysis: {file_path}',
                         file_analysis=file_analysis)

@bp.route('/api/ml-summary')
@login_required
def api_ml_summary():
    """API endpoint for ML summary data."""
    return jsonify(get_mock_ml_summary())

@bp.route('/adls-raw-data')
@login_required
def adls_raw_data():
    """Show raw ADLS data."""
    return render_template('main/adls_raw_data.html',
                         title='ADLS Raw Data',
                         ml_summary=get_mock_ml_summary())

@bp.route('/adls-connection')
@login_required
def adls_connection():
    """Show ADLS connection status."""
    return render_template('main/adls_connection.html',
                         title='ADLS Connection',
                         ml_summary=get_mock_ml_summary())

@bp.route('/audit-export')
@login_required
def audit_export():
    """Audit export route for generating compliance reports."""
    export_stats = {
        'total_reports': 12,
        'ready_reports': 8,
        'recent_exports': 5,
        'total_size': '45.2 MB'
    }
    
    return render_template('main/audit_export.html',
                         title='Audit Export',
                         export_stats=export_stats)

@bp.route('/user-roles')
@login_required
def user_roles():
    """User roles management route."""
    return render_template('main/user_roles.html',
                         title='User Roles')

@bp.route('/debug-adls')
@login_required
def debug_adls():
    """Debug ADLS connection and data."""
    import os
    from datetime import datetime
    
    debug_info = {
        'timestamp': datetime.now().isoformat(),
        'connection_string_set': bool(os.getenv('AZURE_STORAGE_CONNECTION_STRING')),
        'user_id': current_user.id,
        'service_client_initialized': azure_data_service.service_client is not None,
    }
    
    # Try to get files
    try:
        files = azure_data_service.get_compliance_files(user_id=current_user.id)
        debug_info['files_found'] = len(files)
        debug_info['files'] = files
    except Exception as e:
        debug_info['files_error'] = str(e)
    
    # Try to get summary
    try:
        summary = azure_data_service.get_dashboard_summary(user_id=current_user.id)
        debug_info['summary'] = summary
        
        # Show raw data from files
        if summary.get('file_summaries'):
            debug_info['raw_frameworks'] = []
            for fs in summary['file_summaries']:
                debug_info['raw_frameworks'].extend(fs.get('frameworks', []))
    except Exception as e:
        debug_info['summary_error'] = str(e)
    
    return jsonify(debug_info)

@bp.route('/reports/generate/<report_type>')
@login_required
def generate_report(report_type):
    """Generate and download compliance reports."""
    maybe = _require_active_org()
    if maybe is not None:
        return maybe

    from flask import send_file
    from app.services.report_generator import report_generator
    from datetime import datetime

    org_id = _active_org_id()
    organization = Organization.query.get(org_id)
    if not organization:
        abort(404)

    if not organization.billing_complete():
        flash('Add billing details to generate reports.', 'warning')
        return redirect(url_for('onboarding.billing'))
    
    # Get organization data (you can customize this)
    org_data = {
        'name': organization.name,
        'abn': organization.abn or '',
        'address': organization.address or '',
        'contact_name': current_user.display_name(),
        'email': organization.contact_email or current_user.email,
        'framework': organization.industry or '',
        'audit_type': 'Initial'
    }
    
    # Get gap analysis data
    summary = azure_data_service.get_dashboard_summary(user_id=current_user.id)
    gap_data = []
    
    if summary.get('file_summaries'):
        for file_summary in summary['file_summaries']:
            frameworks_data = file_summary.get('frameworks', [])
            for framework_data in frameworks_data:
                status = framework_data.get('status', '').strip()
                if status.lower() == 'complete':
                    display_status = 'Complete'
                elif status.lower() == 'needs review':
                    display_status = 'Needs Review'
                elif status.lower() == 'missing':
                    display_status = 'Missing'
                else:
                    display_status = status
                
                gap_data.append({
                    'requirement_name': framework_data['name'],
                    'status': display_status,
                    'completion_percentage': round(framework_data['score'], 1),  # Score is already a percentage
                    'supporting_evidence': file_summary.get('file_name', 'compliance_summary.csv'),
                    'last_updated': file_summary.get('last_updated')
                })
    
    # Calculate summary stats
    total = len(gap_data)
    met = len([g for g in gap_data if g['status'] == 'Complete'])
    pending = len([g for g in gap_data if g['status'] == 'Needs Review'])
    not_met = len([g for g in gap_data if g['status'] == 'Missing'])
    
    if gap_data:
        avg_percentage = sum([g['completion_percentage'] for g in gap_data]) / len(gap_data)
    else:
        avg_percentage = 0
    
    summary_stats = {
        'total': total,
        'met': met,
        'pending': pending,
        'not_met': not_met,
        'compliance_percentage': int(avg_percentage)
    }
    
    # Get documents for audit pack
    documents = (
        Document.query.filter_by(organization_id=int(org_id), is_active=True)
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    
    # Generate appropriate report
    try:
        if report_type == 'gap-analysis':
            pdf_buffer = report_generator.generate_gap_analysis_report(org_data, gap_data, summary_stats)
            filename = f'Gap_Analysis_Report_{datetime.now().strftime("%Y%m%d")}.pdf'
        elif report_type == 'accreditation-plan':
            pdf_buffer = report_generator.generate_accreditation_plan(org_data, gap_data, summary_stats)
            filename = f'Accreditation_Plan_{datetime.now().strftime("%Y%m%d")}.pdf'
        elif report_type == 'audit-pack':
            pdf_buffer = report_generator.generate_audit_pack(org_data, gap_data, summary_stats, documents)
            filename = f'Audit_Pack_Export_{datetime.now().strftime("%Y%m%d")}.pdf'
        else:
            return "Invalid report type", 400
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        print(f"Error generating report: {e}")
        import traceback
        traceback.print_exc()
        return f"Error generating report: {str(e)}", 500
