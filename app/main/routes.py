from flask import render_template, redirect, url_for, jsonify, request, make_response, flash, abort, current_app
from flask_login import login_required, current_user
from app.main import bp
from app.models import Document, Organization, OrganizationMembership, User
from app import db, mail
from app.services.azure_data_service import azure_data_service

from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer


_RESEND_ORG_INVITE_COOLDOWN_SECONDS = 60 * 5


@bp.route('/terms')
def terms():
    return render_template('legal/terms.html', title='Terms and Conditions')


@bp.route('/privacy')
def privacy():
    return render_template('legal/privacy.html', title='Privacy Policy')


@bp.route('/disclaimer')
def disclaimer():
    return render_template('legal/disclaimer.html', title='Disclaimer')


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


def _is_pending_org_invite(membership: OrganizationMembership, user: User) -> bool:
    # In this app, org "invites" create an inactive-password user and an org membership.
    # A "pending invite" is specifically a membership that was invited (invited_at set),
    # has not been accepted yet, and the user still has no password set.
    # OAuth users may not have a password_hash, so we must not treat them as pending unless
    # the membership is actually invite-tracked.
    return bool(
        membership
        and membership.is_active
        and user
        and membership.invited_at is not None
        and membership.invite_accepted_at is None
        and membership.invite_revoked_at is None
        and not bool(user.password_hash)
    )


def _update_organization_logo(organization: Organization, logo_file) -> tuple[bool, str]:
    """
    Unified logo upload handler for both onboarding and settings.
    Deletes old logo before uploading new one to prevent orphaned files.
    
    Args:
        organization: Organization object to update
        logo_file: FileStorage object from form
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    import uuid
    from app.services.azure_storage_service import azure_storage_service
    
    if not logo_file or not getattr(logo_file, 'filename', ''):
        return False, 'No logo file selected'
    
    # Validate file extension
    ext = (logo_file.filename.rsplit('.', 1)[-1] or '').lower()
    safe_ext = ext if ext in {'png', 'jpg', 'jpeg', 'webp'} else 'png'
    
    # Generate new blob name
    unique = uuid.uuid4().hex
    new_blob_name = f"organizations/{organization.id}/branding/logo_{unique}.{safe_ext}"
    content_type = getattr(logo_file, 'mimetype', None)
    
    # Delete old logo if exists (prevents orphaned files)
    if organization.logo_blob_name:
        try:
            old_blob = organization.logo_blob_name
            # Remove org prefix if it's already in the blob name
            if old_blob.startswith('org_'):
                old_blob = old_blob[len(f'org_{organization.id}/'):]
            azure_storage_service.delete_blob(old_blob, organization_id=int(organization.id))
            current_app.logger.info(f'Deleted old logo: {organization.logo_blob_name}')
        except Exception as e:
            current_app.logger.warning(f'Could not delete old logo {organization.logo_blob_name}: {e}')
            # Continue anyway - old logo deletion failure shouldn't block new upload
    
    # Upload new logo
    data = logo_file.read()
    if not azure_storage_service.upload_blob(new_blob_name, data, content_type=content_type, organization_id=int(organization.id)):
        return False, 'Logo upload failed. Check Azure Storage configuration.'
    
    # Update organization record
    organization.logo_blob_name = new_blob_name
    organization.logo_content_type = content_type
    
    return True, 'Logo uploaded successfully'


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

    # Query the actual user object from the database to ensure changes persist
    user = User.query.get(int(current_user.id))
    user.organization_id = org_id
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

    from app.main.forms import InviteMemberForm, MembershipActionForm, PendingInviteResendForm, PendingInviteRevokeForm
    from app.models import Department

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

    pending_invites = [m for m in members if _is_pending_org_invite(m, m.user)]

    # Used to determine whether the current user (if admin) can remove their own membership.
    active_admin_count = sum(
        1
        for m in members
        if bool(m.is_active) and ((m.role or '').strip().lower() == 'admin')
    )
    current_membership = next((m for m in members if int(m.user_id) == int(current_user.id)), None)
    current_is_active_admin = bool(
        current_membership
        and current_membership.is_active
        and ((current_membership.role or '').strip().lower() == 'admin')
    )
    can_current_user_leave_org = (not current_is_active_admin) or (active_admin_count > 1)

    user_count = sum(1 for m in members if bool(m.is_active))
    document_count = Document.query.filter_by(organization_id=int(org_id), is_active=True).count()

    invite_form = InviteMemberForm()
    departments = (
        Department.query
        .filter_by(organization_id=int(org_id))
        .order_by(Department.name.asc())
        .all()
    )
    invite_form.department_id.choices = [('', 'Select department')] + [
        (str(d.id), d.name) for d in departments
    ]
    member_action_form = MembershipActionForm()
    pending_invite_resend_form = PendingInviteResendForm()
    pending_invite_revoke_form = PendingInviteRevokeForm()

    return render_template(
        'main/org_admin_dashboard.html',
        title='Team Management',
        organization=organization,
        members=members,
        pending_invites=pending_invites,
        active_admin_count=active_admin_count,
        can_current_user_leave_org=can_current_user_leave_org,
        user_count=user_count,
        document_count=document_count,
        invite_form=invite_form,
        member_action_form=member_action_form,
        pending_invite_resend_form=pending_invite_resend_form,
        pending_invite_revoke_form=pending_invite_revoke_form,
        departments=departments,
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
    from sqlalchemy import func
    from app.models import Department

    org_id = _active_org_id()
    organization = Organization.query.get(int(org_id))
    if not organization:
        abort(404)

    form = InviteMemberForm()
    # Populate department choices (so WTForms validates select value).
    departments = (
        Department.query
        .filter_by(organization_id=int(org_id))
        .order_by(Department.name.asc())
        .all()
    )
    form.department_id.choices = [('', 'Select department')] + [(str(d.id), d.name) for d in departments]
    if not form.validate_on_submit():
        if getattr(form, 'department_id', None) is not None and getattr(form.department_id, 'errors', None):
            flash(form.department_id.errors[0], 'error')
        else:
            flash('Please correct the invite form errors and try again.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    email = (form.email.data or '').strip().lower()
    role = (form.role.data or 'User').strip()
    if role not in {'User', 'Admin'}:
        role = 'User'

    # Department: either select existing OR create new.
    department = None
    new_dept_name = (form.new_department_name.data or '').strip()
    new_dept_color = (form.new_department_color.data or 'primary').strip() or 'primary'
    allowed_colors = {'primary', 'secondary', 'success', 'info', 'warning', 'danger', 'dark'}
    if new_dept_color not in allowed_colors:
        new_dept_color = 'primary'

    if new_dept_name:
        # Try to find existing (case-insensitive) department in this org.
        department = (
            Department.query
            .filter(Department.organization_id == int(org_id))
            .filter(func.lower(Department.name) == func.lower(new_dept_name))
            .first()
        )
        if not department:
            department = Department(
                organization_id=int(org_id),
                name=new_dept_name,
                color=new_dept_color,
            )
            db.session.add(department)
            db.session.flush()
    else:
        dept_id_raw = (form.department_id.data or '').strip()
        if dept_id_raw.isdigit():
            department = Department.query.get(int(dept_id_raw))
            if department and int(department.organization_id) != int(org_id):
                department = None

    # Check if user already has an active membership in this org
    user = User.query.filter_by(email=email).first()
    if user:
        existing_membership = (
            OrganizationMembership.query
            .filter_by(organization_id=int(org_id), user_id=int(user.id))
            .first()
        )
        if existing_membership and existing_membership.is_active:
            if not bool(user.password_hash):
                flash(f'An invitation has already been sent to {email}. You can resend it from the pending invites section below.', 'warning')
            else:
                flash(f'{email} is already a member of this organization.', 'warning')
            return redirect(url_for('main.org_admin_dashboard'))

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
            membership.department_id = int(department.id) if department else None
        else:
            membership = OrganizationMembership(
                organization_id=int(org_id),
                user_id=int(user.id),
                role=role,
                is_active=True,
                department_id=(int(department.id) if department else None),
            )
            db.session.add(membership)

        # Track invites only for "pending" invited users (no password set yet).
        if not bool(user.password_hash):
            now = datetime.now(timezone.utc)
            membership.invited_at = membership.invited_at or now
            membership.invited_by_user_id = int(getattr(current_user, 'id', 0) or 0) or None
            membership.invite_last_sent_at = now
            membership.invite_send_count = int(membership.invite_send_count or 0) + 1
            membership.invite_revoked_at = None

        # Only set a default active org for the user if they don't have one.
        if not getattr(user, 'organization_id', None):
            user.organization_id = int(org_id)

        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('Failed to invite member. Please try again.', 'error')
        current_app.logger.exception('Failed inviting member')
        return redirect(url_for('main.org_admin_dashboard'))

    # Send invite email with password-set link (only meaningful for "pending" invited users).
    email_sent = False
    if not bool(user.password_hash):
        try:
            token = _password_reset_token(user)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            _send_invite_email(user, reset_url, organization)
            email_sent = True
        except Exception as e:
            current_app.logger.exception('Failed to send invite email')
            flash(f'User invited but email could not be sent. Error: {str(e)}. Please configure email settings.', 'warning')

    if created_user:
        if email_sent:
            flash(f'Invitation sent to {email}! They will receive an email to set their password and join.', 'success')
        else:
            flash(f'User created but email not configured. Share this invite link manually with {email}.', 'warning')
    else:
        if email_sent:
            flash(f'User re-invited to the organization. Invitation email sent to {email}.', 'success')
        else:
            flash('User added to the organization.', 'success')
    return redirect(url_for('main.org_admin_dashboard'))


@bp.route('/org/admin/departments/create', methods=['POST'])
@login_required
def org_admin_create_department():
    """Create a department for the active organization (AJAX helper)."""
    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

    from app.main.forms import CreateDepartmentForm
    from app.models import Department
    from sqlalchemy import func

    org_id = _active_org_id()
    if not org_id:
        return jsonify({'success': False, 'error': 'No active organization'}), 400

    form = CreateDepartmentForm()
    if not form.validate_on_submit():
        # Keep response simple for UI.
        msg = 'Invalid department details.'
        if form.name.errors:
            msg = form.name.errors[0]
        elif form.color.errors:
            msg = form.color.errors[0]
        return jsonify({'success': False, 'error': msg}), 400

    name = (form.name.data or '').strip()
    color = (form.color.data or 'primary').strip() or 'primary'
    allowed_colors = {'primary', 'secondary', 'success', 'info', 'warning', 'danger', 'dark'}
    if color not in allowed_colors:
        color = 'primary'

    # Case-insensitive de-dupe by name within org.
    existing = (
        Department.query
        .filter(Department.organization_id == int(org_id))
        .filter(func.lower(Department.name) == func.lower(name))
        .first()
    )
    if existing:
        return jsonify({
            'success': True,
            'created': False,
            'department': {'id': int(existing.id), 'name': existing.name, 'color': existing.color},
        })

    try:
        dept = Department(organization_id=int(org_id), name=name, color=color)
        db.session.add(dept)
        db.session.commit()
        return jsonify({
            'success': True,
            'created': True,
            'department': {'id': int(dept.id), 'name': dept.name, 'color': dept.color},
        })
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed creating department')
        return jsonify({'success': False, 'error': 'Failed to create department.'}), 500


@bp.route('/org/admin/departments/<int:dept_id>/edit', methods=['POST'])
@login_required
def org_admin_edit_department(dept_id):
    """Edit a department (AJAX helper)."""
    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

    from app.main.forms import EditDepartmentForm
    from app.models import Department
    from sqlalchemy import func

    org_id = _active_org_id()
    if not org_id:
        return jsonify({'success': False, 'error': 'No active organization'}), 400

    dept = Department.query.filter_by(id=dept_id, organization_id=int(org_id)).first()
    if not dept:
        return jsonify({'success': False, 'error': 'Department not found'}), 404

    form = EditDepartmentForm()
    if not form.validate_on_submit():
        msg = 'Invalid department details.'
        if form.name.errors:
            msg = form.name.errors[0]
        elif form.color.errors:
            msg = form.color.errors[0]
        return jsonify({'success': False, 'error': msg}), 400

    name = (form.name.data or '').strip()
    color = (form.color.data or 'primary').strip() or 'primary'
    allowed_colors = {'primary', 'secondary', 'success', 'info', 'warning', 'danger', 'dark'}
    if color not in allowed_colors:
        color = 'primary'

    # Check for name conflict (case-insensitive, excluding current dept).
    conflict = (
        Department.query
        .filter(Department.organization_id == int(org_id))
        .filter(Department.id != dept_id)
        .filter(func.lower(Department.name) == func.lower(name))
        .first()
    )
    if conflict:
        return jsonify({'success': False, 'error': 'A department with this name already exists'}), 400

    try:
        dept.name = name
        dept.color = color
        db.session.commit()
        return jsonify({
            'success': True,
            'department': {'id': int(dept.id), 'name': dept.name, 'color': dept.color},
        })
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed editing department')
        return jsonify({'success': False, 'error': 'Failed to edit department.'}), 500


@bp.route('/org/admin/departments/<int:dept_id>/delete', methods=['POST'])
@login_required
def org_admin_delete_department(dept_id):
    """Delete a department (AJAX helper). Members assigned to this department will have it set to NULL."""
    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

    from app.main.forms import DeleteDepartmentForm
    from app.models import Department, OrganizationMembership

    org_id = _active_org_id()
    if not org_id:
        return jsonify({'success': False, 'error': 'No active organization'}), 400

    form = DeleteDepartmentForm()
    if not form.validate_on_submit():
        return jsonify({'success': False, 'error': 'Invalid request'}), 400

    dept = Department.query.filter_by(id=dept_id, organization_id=int(org_id)).first()
    if not dept:
        return jsonify({'success': False, 'error': 'Department not found'}), 404

    try:
        # Unassign members from this department.
        OrganizationMembership.query.filter_by(department_id=dept_id).update({'department_id': None})
        db.session.delete(dept)
        db.session.commit()
        return jsonify({'success': True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed deleting department')
        return jsonify({'success': False, 'error': 'Failed to delete department.'}), 500


@bp.route('/org/admin/invite/resend', methods=['POST'])
@login_required
def org_admin_resend_invite():
    """Resend an invite email to a pending invited user (cooldown enforced)."""
    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

    from app.main.forms import PendingInviteResendForm
    from datetime import datetime, timezone

    org_id = _active_org_id()
    organization = Organization.query.get(int(org_id))
    if not organization:
        abort(404)

    form = PendingInviteResendForm()
    if not form.validate_on_submit():
        flash('Invalid request.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    membership_id_raw = (form.membership_id.data or '').strip()
    if not membership_id_raw.isdigit():
        flash('Invalid request.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    membership = OrganizationMembership.query.get(int(membership_id_raw))
    if not membership or int(membership.organization_id) != int(org_id):
        flash('Invite not found.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    user = User.query.get(int(membership.user_id)) if membership else None
    if not _is_pending_org_invite(membership, user):
        flash('That invite is no longer pending.', 'info')
        return redirect(url_for('main.org_admin_dashboard'))

    now = datetime.now(timezone.utc)
    last_sent = membership.invite_last_sent_at
    if last_sent:
        # SQLite can return naive datetimes; normalize to UTC-aware for arithmetic.
        if getattr(last_sent, 'tzinfo', None) is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        wait_seconds = _RESEND_ORG_INVITE_COOLDOWN_SECONDS - int((now - last_sent).total_seconds())
        if wait_seconds > 0:
            flash(f'Please wait {wait_seconds} seconds before resending this invite.', 'warning')
            return redirect(url_for('main.org_admin_dashboard'))

    try:
        membership.invite_last_sent_at = now
        membership.invite_send_count = int(membership.invite_send_count or 0) + 1
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed updating invite tracking')
        flash('Failed to resend invite. Please try again.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    try:
        token = _password_reset_token(user)
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        _send_invite_email(user, reset_url, organization)
    except Exception:
        current_app.logger.exception('Failed to send invite email')

    flash('Invite resent (or logged if mail not configured).', 'success')
    return redirect(url_for('main.org_admin_dashboard'))


@bp.route('/org/admin/invite/revoke', methods=['POST'])
@login_required
def org_admin_revoke_invite():
    """Revoke a pending invite by disabling the membership."""
    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

    from app.main.forms import PendingInviteRevokeForm
    from datetime import datetime, timezone

    org_id = _active_org_id()

    form = PendingInviteRevokeForm()
    if not form.validate_on_submit():
        flash('Invalid request.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    membership_id_raw = (form.membership_id.data or '').strip()
    if not membership_id_raw.isdigit():
        flash('Invalid request.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    membership = OrganizationMembership.query.get(int(membership_id_raw))
    if not membership or int(membership.organization_id) != int(org_id):
        flash('Invite not found.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    # Guard: never allow an admin to revoke themselves via the invite flow.
    if int(membership.user_id) == int(current_user.id):
        flash('You cannot revoke your own access.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    user = User.query.get(int(membership.user_id)) if membership else None
    if not _is_pending_org_invite(membership, user):
        flash('That invite is no longer pending.', 'info')
        return redirect(url_for('main.org_admin_dashboard'))

    try:
        membership.is_active = False
        membership.invite_revoked_at = datetime.now(timezone.utc)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed revoking invite')
        flash('Failed to revoke invite. Please try again.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    flash('Invite revoked.', 'success')
    return redirect(url_for('main.org_admin_dashboard'))


@bp.route('/org/admin/members/remove', methods=['POST'])
@login_required
def org_admin_remove_member():
    """Remove a user's membership from the active organization."""
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

    # Guard: do not remove the last active admin.
    is_admin = (membership.role or '').strip().lower() == 'admin'
    if is_admin and membership.is_active:
        active_admins = (
            OrganizationMembership.query
            .filter_by(organization_id=int(org_id), is_active=True)
            .filter(OrganizationMembership.role.ilike('admin'))
            .count()
        )
        if active_admins <= 1:
            flash('Cannot remove the last admin. Promote another member to admin first.', 'error')
            return redirect(url_for('main.org_admin_dashboard'))

    # Allow self-removal only when there is another active admin (if the user is an admin).
    if int(membership.user_id) == int(current_user.id):
        if is_admin and membership.is_active:
            active_admins = (
                OrganizationMembership.query
                .filter_by(organization_id=int(org_id), is_active=True)
                .filter(OrganizationMembership.role.ilike('admin'))
                .count()
            )
            if active_admins <= 1:
                flash('You are the only admin. Promote another admin before leaving the organization.', 'error')
                return redirect(url_for('main.org_admin_dashboard'))

    try:
        membership.is_active = False
        db.session.commit()
        flash('Member removed from the organization.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to remove member. Please try again.', 'error')
        current_app.logger.exception('Failed removing member')

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
    # If user is logged in and explicitly wants to switch accounts, show option
    if current_user.is_authenticated:
        # Check if user wants to see login/signup options (for account switching)
        if request.args.get('switch_account') == '1':
            flash('You are currently logged in. To switch accounts, please logout first.', 'info')
            # Don't auto-redirect, show home page with logout option
            return render_template('main/index.html', title='Home', show_logout=True)
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
    
    # Get real ADLS data (skip external calls during tests)
    if current_app.config.get('TESTING'):
        ml_summary = {
            'avg_compliancy_rate': 0,
            'total_files': 0,
            'total_complete': 0,
            'total_needs_review': 0,
            'total_missing': 0,
            'file_summaries': [],
        }
    else:
        ml_summary = azure_data_service.get_dashboard_summary(user_id=current_user.id, organization_id=org_id)
    
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
def download_document(doc_id):
    """Download a document."""
    from flask import send_file, abort
    from app.services.azure_storage import AzureBlobStorageService
    import io

    # For document downloads, do not leak existence via redirects.
    # Return 404 for any unauthenticated/unauthorized access.
    if not getattr(current_user, 'is_authenticated', False):
        abort(404)

    org_id = _active_org_id()
    if not org_id:
        abort(404)

    membership = (
        OrganizationMembership.query
        .filter_by(user_id=int(current_user.id), organization_id=int(org_id), is_active=True)
        .first()
    )
    if not membership:
        abort(404)
    
    # Get document from database
    document = Document.query.get(doc_id)
    
    # Check if document exists and belongs to active org
    if not document or not getattr(document, 'is_active', True):
        abort(404)
    if int(document.organization_id) != int(org_id):
        abort(404)
    
    try:
        storage_service = AzureBlobStorageService()
        result = storage_service.download_file(document.blob_name)
        if not result.get('success'):
            if result.get('error_code') == 'FILE_NOT_FOUND':
                abort(404)
            abort(500)

        blob_data = result.get('data')
        if not blob_data:
            abort(404)
        
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
    from app.services.azure_storage import AzureBlobStorageService
    
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
        if getattr(document, 'blob_name', None):
            storage_service = AzureBlobStorageService()
            delete_result = storage_service.delete_file(document.blob_name)
            if not delete_result.get('success'):
                raise Exception(delete_result.get('error') or 'Delete failed')
        else:
            current_app.logger.warning('Document %s has no blob_name; skipping Azure deletion', document.id)
        
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
    # Get real ADLS data (org-scoped)
    summary = azure_data_service.get_dashboard_summary(
        user_id=current_user.id,
        organization_id=getattr(current_user, 'organization_id', None),
    )
    
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
                    success, message = _update_organization_logo(organization, logo_file)
                    if not success:
                        flash(message, 'error')
                        return render_template(
                            'main/organization_settings.html',
                            title='Organization Settings',
                            profile_form=profile_form,
                            billing_form=billing_form,
                            organization=organization,
                        )

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
        title='Organization Profile',
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
    # Pass org_id to ensure correct path (org_X/ prefix)
    blob_data = azure_storage_service.download_blob(organization.logo_blob_name, organization_id=int(org_id))
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

@bp.route('/organization/<int:org_id>/logo')
@login_required
def organization_logo_by_id(org_id):
    """Serve logo for any organization the user is a member of."""
    from flask import abort, send_file
    import io

    # Check user has access to this org
    membership = (
        OrganizationMembership.query
        .filter_by(user_id=int(current_user.id), organization_id=int(org_id), is_active=True)
        .first()
    )
    if not membership:
        abort(404)

    organization = Organization.query.get(int(org_id))
    if not organization or not organization.logo_blob_name:
        abort(404)

    from app.services.azure_storage_service import azure_storage_service
    # Pass org_id to ensure correct path (org_X/ prefix)
    blob_data = azure_storage_service.download_blob(organization.logo_blob_name, organization_id=int(org_id))
    if not blob_data:
        abort(404)

    file_stream = io.BytesIO(blob_data)
    file_stream.seek(0)
    return send_file(
        file_stream,
        mimetype=organization.logo_content_type or 'application/octet-stream',
        as_attachment=False,
        download_name=f'{organization.name}_logo'
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
    if request.method == 'POST':
        # User avatars are intentionally disabled; org logo is the single branding image.
        flash('Profile photos are disabled. Use the organization logo instead.', 'info')
        return redirect(url_for('main.profile'))

    return render_template('main/profile.html', title='My Profile')


@bp.route('/profile/avatar')
@login_required
def profile_avatar():
    """Serve the current user's avatar image."""
    from flask import abort, send_file
    from app.services.azure_storage import AzureBlobStorageService
    import io

    if not getattr(current_user, 'avatar_blob_name', None):
        abort(404)

    storage_service = AzureBlobStorageService()
    result = storage_service.download_file(current_user.avatar_blob_name)
    if not result.get('success'):
        abort(404)

    blob_data = result.get('data')
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

# User roles route removed - functionality moved to Org Admin Dashboard

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
