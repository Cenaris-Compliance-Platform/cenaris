from flask import render_template, redirect, url_for, jsonify, request, make_response, flash, abort, current_app
from flask_login import login_required, current_user
from app.main import bp
from app.models import Document, Organization, OrganizationMembership, User
from app import db, mail
from app.services.azure_data_service import azure_data_service

import threading
import time

from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer

import os
import hashlib
import json


_RESEND_ORG_INVITE_COOLDOWN_SECONDS = 60 * 5

_ORG_INVITE_TOKEN_SALT = 'org-invite'


_ORG_LOGO_CACHE: dict[tuple[int, str], tuple[float, bytes, str | None]] = {}
_ORG_LOGO_CACHE_LOCK = threading.Lock()


def _safe_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except Exception:
        return default


def _org_invite_token_ttl_seconds() -> int:
    # Keep in sync with auth.routes._org_invite_token_ttl_seconds
    return max(60, _safe_int_env('ORG_INVITE_TOKEN_TTL_SECONDS', 60 * 60 * 24))


def _format_duration_seconds(seconds: int) -> str:
    seconds = int(seconds or 0)
    if seconds <= 0:
        return 'a short time'
    if seconds % (60 * 60 * 24) == 0:
        days = seconds // (60 * 60 * 24)
        return f'{days} day' if days == 1 else f'{days} days'
    if seconds % (60 * 60) == 0:
        hours = seconds // (60 * 60)
        return f'{hours} hour' if hours == 1 else f'{hours} hours'
    minutes = max(1, seconds // 60)
    return f'{minutes} minute' if minutes == 1 else f'{minutes} minutes'


def _etag_matches_if_none_match(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    value = if_none_match.strip()
    if value == '*':
        return True
    candidates = [part.strip() for part in value.split(',') if part.strip()]
    strong_etag = etag[2:] if etag.startswith('W/') else etag
    return (etag in candidates) or (strong_etag in candidates)


def _get_cached_org_logo(org_id: int, blob_name: str) -> tuple[bytes, str | None] | None:
    now = time.monotonic()
    with _ORG_LOGO_CACHE_LOCK:
        cached = _ORG_LOGO_CACHE.get((org_id, blob_name))
        if not cached:
            return None
        expires_at, data, content_type = cached
        if now >= expires_at:
            try:
                del _ORG_LOGO_CACHE[(org_id, blob_name)]
            except KeyError:
                pass
            return None
        return data, content_type


def _set_cached_org_logo(org_id: int, blob_name: str, data: bytes, content_type: str | None, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return
    expires_at = time.monotonic() + ttl_seconds
    with _ORG_LOGO_CACHE_LOCK:
        _ORG_LOGO_CACHE[(org_id, blob_name)] = (expires_at, data, content_type)


def _org_logo_disk_cache_paths(org_id: int, blob_name: str) -> tuple[str, str]:
    digest = hashlib.sha256(blob_name.encode('utf-8')).hexdigest()
    base_dir = os.path.join(current_app.instance_path, 'cache', 'org_logos')
    return (
        os.path.join(base_dir, f'{org_id}_{digest}.bin'),
        os.path.join(base_dir, f'{org_id}_{digest}.json'),
    )


def _get_disk_cached_org_logo(org_id: int, blob_name: str) -> tuple[bytes, str | None] | None:
    try:
        ttl_seconds = int(current_app.config.get('ORG_LOGO_DISK_CACHE_SECONDS') or 86400)
    except Exception:
        ttl_seconds = 86400
    if ttl_seconds <= 0:
        return None

    data_path, meta_path = _org_logo_disk_cache_paths(org_id, blob_name)
    try:
        if not os.path.exists(data_path) or not os.path.exists(meta_path):
            return None
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f) or {}
        created_at = float(meta.get('created_at') or 0)
        if (time.time() - created_at) > ttl_seconds:
            return None
        with open(data_path, 'rb') as f:
            data = f.read()
        if not data:
            return None
        return data, (meta.get('content_type') or None)
    except Exception:
        return None


def _set_disk_cached_org_logo(org_id: int, blob_name: str, data: bytes, content_type: str | None) -> None:
    try:
        ttl_seconds = int(current_app.config.get('ORG_LOGO_DISK_CACHE_SECONDS') or 86400)
    except Exception:
        ttl_seconds = 86400
    if ttl_seconds <= 0:
        return
    try:
        data_path, meta_path = _org_logo_disk_cache_paths(org_id, blob_name)
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        tmp_data = data_path + '.tmp'
        tmp_meta = meta_path + '.tmp'
        with open(tmp_data, 'wb') as f:
            f.write(data)
        with open(tmp_meta, 'w', encoding='utf-8') as f:
            json.dump({'created_at': time.time(), 'content_type': content_type}, f)
        os.replace(tmp_data, data_path)
        os.replace(tmp_meta, meta_path)
    except Exception:
        return


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
        flash('Please select an organisation to continue.', 'info')
        return redirect(url_for('onboarding.organization'))

    membership = (
        OrganizationMembership.query
        .filter_by(user_id=int(current_user.id), organization_id=int(org_id), is_active=True)
        .first()
    )
    if not membership:
        flash('You do not have access to that organisation.', 'error')
        return redirect(url_for('onboarding.organization'))
    return None


def _require_org_admin():
    maybe = _require_active_org()
    if maybe is not None:
        return maybe
    if not current_user.has_permission('users.manage', org_id=_active_org_id()):
        abort(403)
    return None


def _require_org_permission(permission_code: str):
    maybe = _require_active_org()
    if maybe is not None:
        return maybe
    if not current_user.has_permission(permission_code, org_id=_active_org_id()):
        abort(403)
    return None


def _membership_has_permission(membership: OrganizationMembership, code: str) -> bool:
    if not membership or not membership.is_active:
        return False

    if membership.rbac_role:
        try:
            return code in membership.rbac_role.effective_permission_codes()
        except Exception:
            return False

    # Legacy fallback: only supports basic admin mapping.
    if code == 'users.manage':
        return (membership.role or '').strip().lower() in {
            'admin',
            'organisation administrator',
            'organization administrator',
        }

    return False


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _mail_configured() -> bool:
    return bool(current_app.config.get('MAIL_SERVER') and current_app.config.get('MAIL_DEFAULT_SENDER'))


def _password_reset_token(user: User) -> str:
    # Must match the implementation in auth/routes.py
    return _serializer().dumps({'user_id': user.id, 'email': user.email}, salt='password-reset')


def _org_invite_token(user: User) -> str:
    # Must match the implementation in auth/routes.py
    return _serializer().dumps({'user_id': user.id, 'email': user.email}, salt=_ORG_INVITE_TOKEN_SALT)


def _send_invite_email(user: User, reset_url: str, organization: Organization) -> None:
    if not _mail_configured():
        current_app.logger.warning('MAIL not configured; invite reset URL: %s', reset_url)
        return

    subject = f"You're invited to {organization.name}"
    body = (
        f"You've been invited to join {organization.name} on Cenaris.\n\n"
        f"Set your password here: {reset_url}\n\n"
        f"This link expires in {_format_duration_seconds(_org_invite_token_ttl_seconds())}.\n\n"
        "If you weren't expecting this invite, you can ignore this email."
    )
    try:
        from app.auth.routes import _send_email
        _send_email(user.email, subject, body)
    except Exception:
        current_app.logger.exception('Failed to send invite email to %s (org_id=%s)', user.email, getattr(organization, 'id', None))
        raise


def _is_pending_org_invite(membership: OrganizationMembership, user: User) -> bool:
    # In this app, org "invites" create an inactive-password user and an org membership.
    # A "pending invite" is specifically a membership that was invited (invited_at set),
    # has not been accepted yet, and the user still has no password set.
    # OAuth users may not have a password_hash, so we must not treat them as pending unless
    # the membership is actually invite-tracked.
    return bool(
        membership
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
        flash('Invalid organisation.', 'error')
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
    user = db.session.get(User, int(current_user.id))
    user.organization_id = org_id
    db.session.commit()
    flash('Organisation switched.', 'success')
    return redirect(request.referrer or url_for('main.dashboard'))


@bp.route('/org/admin')
@login_required
def org_admin_dashboard():
    """Organisation admin overview."""
    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

    from app.main.forms import InviteMemberForm, MembershipActionForm, PendingInviteResendForm, PendingInviteRevokeForm, UpdateMemberRoleForm, UpdateMemberDepartmentForm
    from app.models import Department

    org_id = _active_org_id()
    organization = db.session.get(Organization, int(org_id))
    if not organization:
        abort(404)

    # Ensure RBAC defaults exist so UI can show role names reliably.
    try:
        from app.services.rbac import ensure_rbac_seeded_for_org

        ensure_rbac_seeded_for_org(int(org_id))
        db.session.commit()
    except Exception:
        db.session.rollback()

    members = (
        OrganizationMembership.query
        .filter_by(organization_id=int(org_id))
        .join(User, User.id == OrganizationMembership.user_id)
        .order_by(OrganizationMembership.is_active.desc(), User.email.asc())
        .all()
    )

    pending_invites = [m for m in members if _is_pending_org_invite(m, m.user)]

    # Used to determine whether the current user (if admin) can remove their own membership.
    def _can_manage_users(m: OrganizationMembership) -> bool:
        return _membership_has_permission(m, 'users.manage')

    active_admin_count = sum(1 for m in members if _can_manage_users(m))
    current_membership = next((m for m in members if int(m.user_id) == int(current_user.id)), None)
    current_is_active_admin = bool(current_membership and _can_manage_users(current_membership))
    can_current_user_leave_org = (not current_is_active_admin) or (active_admin_count > 1)

    user_count = sum(1 for m in members if bool(m.is_active))
    document_count = Document.query.filter_by(organization_id=int(org_id), is_active=True).count()

    invite_form = InviteMemberForm()
    try:
        from app.models import RBACRole

        roles = (
            RBACRole.query
            .filter_by(organization_id=int(org_id))
            .order_by(RBACRole.name.asc())
            .all()
        )
        invite_form.role.choices = [(str(r.id), r.name) for r in roles]
    except Exception:
        invite_form.role.choices = []
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
    update_role_form = UpdateMemberRoleForm()
    update_department_form = UpdateMemberDepartmentForm()
    pending_invite_resend_form = PendingInviteResendForm()
    pending_invite_revoke_form = PendingInviteRevokeForm()

    # Populate role choices for role-update form.
    available_roles = []
    try:
        from app.models import RBACRole

        roles = (
            RBACRole.query
            .filter_by(organization_id=int(org_id))
            .order_by(RBACRole.name.asc())
            .all()
        )
        available_roles = roles
        update_role_form.role_id.choices = [(str(r.id), r.name) for r in roles]
    except Exception:
        update_role_form.role_id.choices = []

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
        invite_expires_in=_format_duration_seconds(_org_invite_token_ttl_seconds()),
        invite_form=invite_form,
        member_action_form=member_action_form,
        update_role_form=update_role_form,
        update_department_form=update_department_form,
        pending_invite_resend_form=pending_invite_resend_form,
        pending_invite_revoke_form=pending_invite_revoke_form,
        departments=departments,
        available_roles=available_roles,
    )


@bp.route('/org/admin/members/department', methods=['POST'])
@login_required
def org_admin_update_member_department():
    """Update a member's department assignment."""
    maybe = _require_org_permission('users.manage')
    if maybe is not None:
        return maybe

    from flask import request, jsonify
    from app.main.forms import UpdateMemberDepartmentForm
    from app.models import Department

    def _wants_json() -> bool:
        return (request.headers.get('X-Requested-With') == 'fetch') or (request.accept_mimetypes.best == 'application/json')

    org_id = _active_org_id()
    organization = db.session.get(Organization, int(org_id))
    if not organization:
        if _wants_json():
            return jsonify(success=False, error='Organisation not found.'), 404
        flash('Organisation not found.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    form = UpdateMemberDepartmentForm()

    # Populate choices so WTForms validates the selection.
    departments = (
        Department.query
        .filter_by(organization_id=int(org_id))
        .order_by(Department.name.asc())
        .all()
    )
    form.department_id.choices = [('', 'Unassigned')] + [(str(d.id), d.name) for d in departments]

    if not form.validate_on_submit():
        if _wants_json():
            return jsonify(success=False, error='Invalid request.'), 400
        flash('Invalid request.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    membership_id_raw = (form.membership_id.data or '').strip()
    dept_id_raw = (form.department_id.data or '').strip()

    if not membership_id_raw.isdigit():
        if _wants_json():
            return jsonify(success=False, error='Invalid request.'), 400
        flash('Invalid request.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    membership = db.session.get(OrganizationMembership, int(membership_id_raw))
    if not membership or int(membership.organization_id) != int(org_id):
        if _wants_json():
            return jsonify(success=False, error='Membership not found.'), 404
        flash('Membership not found.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    new_dept = None
    if dept_id_raw:
        if not dept_id_raw.isdigit():
            if _wants_json():
                return jsonify(success=False, error='Invalid department.'), 400
            flash('Invalid department.', 'error')
            return redirect(url_for('main.org_admin_dashboard'))

        new_dept = db.session.get(Department, int(dept_id_raw))
        if not new_dept or int(new_dept.organization_id) != int(org_id):
            if _wants_json():
                return jsonify(success=False, error='Department not found.'), 404
            flash('Department not found.', 'error')
            return redirect(url_for('main.org_admin_dashboard'))

    try:
        membership.department_id = int(new_dept.id) if new_dept else None
        db.session.commit()

        if _wants_json():
            return jsonify(
                success=True,
                membership_id=int(membership.id),
                department={
                    'id': int(new_dept.id),
                    'name': new_dept.name,
                    'color': new_dept.color,
                } if new_dept else None,
            )

        flash('Department updated.', 'success')
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed updating member department')
        if _wants_json():
            return jsonify(success=False, error='Failed to update department. Please try again.'), 500
        flash('Failed to update department. Please try again.', 'error')

    return redirect(url_for('main.org_admin_dashboard'))


@bp.route('/org/admin/members/role', methods=['POST'])
@login_required
def org_admin_update_member_role():
    """Update a member's org-scoped RBAC role."""
    maybe = _require_org_permission('roles.manage')
    if maybe is not None:
        return maybe

    from flask import request, jsonify

    def _wants_json() -> bool:
        return (request.headers.get('X-Requested-With') == 'fetch') or (request.accept_mimetypes.best == 'application/json')

    from app.main.forms import UpdateMemberRoleForm
    from app.models import RBACRole

    org_id = _active_org_id()
    organization = db.session.get(Organization, int(org_id))
    if not organization:
        if _wants_json():
            return jsonify(success=False, error='Organisation not found.'), 404
        flash('Organisation not found.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    form = UpdateMemberRoleForm()

    # Populate role choices so WTForms validates the selection.
    try:
        roles = (
            RBACRole.query
            .filter_by(organization_id=int(org_id))
            .order_by(RBACRole.name.asc())
            .all()
        )
        form.role_id.choices = [(str(r.id), r.name) for r in roles]
    except Exception:
        form.role_id.choices = []

    if not form.validate_on_submit():
        if _wants_json():
            return jsonify(success=False, error='Invalid request.'), 400
        flash('Invalid request.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    membership_id_raw = (form.membership_id.data or '').strip()
    role_id_raw = (form.role_id.data or '').strip()

    if not membership_id_raw.isdigit() or not role_id_raw.isdigit():
        if _wants_json():
            return jsonify(success=False, error='Invalid request.'), 400
        flash('Invalid request.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    membership = db.session.get(OrganizationMembership, int(membership_id_raw))
    if not membership or int(membership.organization_id) != int(org_id):
        if _wants_json():
            return jsonify(success=False, error='Membership not found.'), 404
        flash('Membership not found.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    target_role = db.session.get(RBACRole, int(role_id_raw))
    if not target_role or int(target_role.organization_id) != int(org_id):
        if _wants_json():
            return jsonify(success=False, error='Role not found.'), 404
        flash('Role not found.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    currently_admin = _membership_has_permission(membership, 'users.manage')
    try:
        new_admin = 'users.manage' in target_role.effective_permission_codes()
    except Exception:
        new_admin = False

    # Guard: never demote the last active admin.
    if membership.is_active and currently_admin and not new_admin:
        active_memberships = (
            OrganizationMembership.query
            .filter_by(organization_id=int(org_id), is_active=True)
            .all()
        )
        active_admins = sum(1 for m in active_memberships if _membership_has_permission(m, 'users.manage'))
        if active_admins <= 1:
            if _wants_json():
                return jsonify(success=False, error='Cannot change role: you would remove the last admin.'), 400
            flash('Cannot change role: you would remove the last admin.', 'error')
            return redirect(url_for('main.org_admin_dashboard'))

    try:
        membership.role_id = int(target_role.id)
        # Keep legacy string role in sync during transition.
        membership.role = 'Admin' if new_admin else 'User'
        db.session.commit()

        # Invalidate cached navigation context (role badge/permissions) so the
        # change is reflected immediately for the affected user.
        try:
            from app import invalidate_org_switcher_context_cache
            invalidate_org_switcher_context_cache(membership.user_id, membership.organization_id)
            invalidate_org_switcher_context_cache(current_user.id, membership.organization_id)
        except Exception:
            pass
        
        # Force SQLAlchemy to reload the rbac_role relationship from database
        # This ensures display_role_name shows the correct new role
        db.session.expire(membership, ['rbac_role'])
        db.session.refresh(membership)
        role_name = target_role.name
        if _wants_json():
            return jsonify(
                success=True,
                membership_id=int(membership.id),
                user_id=int(membership.user_id),
                new_role_name=role_name,
                is_current_user=(int(membership.user_id) == int(current_user.id)),
            )

        flash('Role updated.', 'success')
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed updating member role')
        if _wants_json():
            return jsonify(success=False, error='Failed to update role. Please try again.'), 500

        flash('Failed to update role. Please try again.', 'error')

    return redirect(url_for('main.org_admin_dashboard'))


@bp.route('/org/admin/invite', methods=['POST'])
@login_required
def org_admin_invite_member():
    """Invite/add a user to the active organization by email."""
    maybe = _require_org_permission('users.invite')
    if maybe is not None:
        return maybe

    from app.main.forms import InviteMemberForm
    from datetime import datetime, timezone
    from sqlalchemy import func
    from app.models import Department

    org_id = _active_org_id()
    organization = db.session.get(Organization, int(org_id))
    if not organization:
        abort(404)

    form = InviteMemberForm()

    # Seed RBAC so role selection works.
    try:
        from app.services.rbac import ensure_rbac_seeded_for_org

        ensure_rbac_seeded_for_org(int(org_id))
        db.session.flush()
    except Exception:
        db.session.rollback()
    # Populate department choices (so WTForms validates select value).
    departments = (
        Department.query
        .filter_by(organization_id=int(org_id))
        .order_by(Department.name.asc())
        .all()
    )
    form.department_id.choices = [('', 'Select department')] + [(str(d.id), d.name) for d in departments]

    # Populate role choices from RBAC roles.
    try:
        from app.models import RBACRole

        roles = (
            RBACRole.query
            .filter_by(organization_id=int(org_id))
            .order_by(RBACRole.name.asc())
            .all()
        )
        form.role.choices = [(str(r.id), r.name) for r in roles]
    except Exception:
        form.role.choices = []
    if not form.validate_on_submit():
        if getattr(form, 'department_id', None) is not None and getattr(form.department_id, 'errors', None):
            flash(form.department_id.errors[0], 'error')
        else:
            flash('Please correct the invite form errors and try again.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    email = (form.email.data or '').strip().lower()

    role_id = None
    selected_role = None
    role_raw = (form.role.data or '').strip()
    if role_raw.isdigit():
        role_id = int(role_raw)
        try:
            from app.models import RBACRole

            selected_role = db.session.get(RBACRole, int(role_id))
            if not selected_role or int(selected_role.organization_id) != int(org_id):
                selected_role = None
        except Exception:
            selected_role = None

    if not selected_role:
        try:
            from app.models import RBACRole
            from app.services.rbac import BUILTIN_ROLE_KEYS

            selected_role = (
                RBACRole.query
                .filter_by(organization_id=int(org_id), name=BUILTIN_ROLE_KEYS.MEMBER)
                .first()
            )
        except Exception:
            selected_role = None

    selected_role_id = int(selected_role.id) if selected_role else None

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
            department = db.session.get(Department, int(dept_id_raw))
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
            # Re-adding a previously removed member - treat as new invite
            membership.is_active = True
            membership.role_id = selected_role_id
            membership.department_id = int(department.id) if department else None
            # Reset invite acceptance tracking
            membership.invite_accepted_at = None
        else:
            membership = OrganizationMembership(
                organization_id=int(org_id),
                user_id=int(user.id),
                role_id=selected_role_id,
                is_active=True,
                department_id=(int(department.id) if department else None),
            )
            db.session.add(membership)

        # Keep legacy role string compatible with existing admin checks.
        try:
            from app.services.rbac import BUILTIN_ROLE_KEYS

            if selected_role and (selected_role.name or '').strip() == BUILTIN_ROLE_KEYS.ORG_ADMIN:
                membership.role = 'Admin'
            else:
                membership.role = 'User'
        except Exception:
            membership.role = membership.role or 'User'

        # Track invite details - send to all newly added/re-added members
        now = datetime.now(timezone.utc)
        membership.invited_at = membership.invited_at or now
        membership.invited_by_user_id = int(getattr(current_user, 'id', 0) or 0) or None
        membership.invite_last_sent_at = now
        membership.invite_send_count = int(membership.invite_send_count or 0) + 1
        membership.invite_revoked_at = None

        # Set the user's active organization to the one they're being invited to
        user.organization_id = int(org_id)

        db.session.commit()
    except Exception:
        db.session.rollback()
        flash('Failed to invite member. Please try again.', 'error')
        current_app.logger.exception('Failed inviting member')
        return redirect(url_for('main.org_admin_dashboard'))

    # Send invite email - for users without password, they set it via reset link
    # For users with existing password, they can use their existing password to login
    email_sent = False
    try:
        token = _org_invite_token(user)
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        _send_invite_email(user, reset_url, organization)
        email_sent = True
    except Exception as e:
        current_app.logger.exception('Failed to send invite email')
        flash(f'User invited but email could not be sent. Error: {str(e)}. Please configure email settings.', 'warning')

    if created_user:
        if email_sent:
            flash(
                f'Invitation sent to {email}! The link expires in {_format_duration_seconds(_org_invite_token_ttl_seconds())}.',
                'success',
            )
        else:
            flash(f'User created but email not configured. Share this invite link manually with {email}.', 'warning')
    else:
        if email_sent:
            flash(
                f'User re-invited. The link expires in {_format_duration_seconds(_org_invite_token_ttl_seconds())}.',
                'success',
            )
        else:
            flash('User added to the organisation.', 'success')
    return redirect(url_for('main.org_admin_dashboard'))


@bp.route('/org/admin/departments/create', methods=['POST'])
@login_required
def org_admin_create_department():
    """Create a department for the active organization (AJAX helper)."""
    maybe = _require_org_permission('departments.manage')
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
    maybe = _require_org_permission('departments.manage')
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
    maybe = _require_org_permission('departments.manage')
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
    maybe = _require_org_permission('users.invite')
    if maybe is not None:
        return maybe

    from app.main.forms import PendingInviteResendForm
    from datetime import datetime, timezone

    org_id = _active_org_id()
    organization = db.session.get(Organization, int(org_id))
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

    membership = db.session.get(OrganizationMembership, int(membership_id_raw))
    if not membership or int(membership.organization_id) != int(org_id):
        flash('Invite not found.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    # Ensure we are reading the latest invite tracking fields in case this row
    # was updated in another session/process (or earlier request).
    try:
        db.session.refresh(membership)
    except Exception:
        pass

    user = db.session.get(User, int(membership.user_id)) if membership else None
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
        token = _org_invite_token(user)
        reset_url = url_for('auth.reset_password', token=token, _external=True)
        _send_invite_email(user, reset_url, organization)
    except Exception:
        current_app.logger.exception('Failed to send invite email')

    flash(f'Invite resent. The link expires in {_format_duration_seconds(_org_invite_token_ttl_seconds())}.', 'success')
    return redirect(url_for('main.org_admin_dashboard'))


@bp.route('/org/admin/invite/revoke', methods=['POST'])
@login_required
def org_admin_revoke_invite():
    """Revoke a pending invite by disabling the membership."""
    maybe = _require_org_permission('users.invite')
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

    membership = db.session.get(OrganizationMembership, int(membership_id_raw))
    if not membership or int(membership.organization_id) != int(org_id):
        flash('Invite not found.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    # Guard: never allow an admin to revoke themselves via the invite flow.
    if int(membership.user_id) == int(current_user.id):
        flash('You cannot revoke your own access.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    user = db.session.get(User, int(membership.user_id)) if membership else None
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
    """Remove or disable a user's membership from the active organization."""
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
    action = (form.action.data or '').strip().lower()
    
    if not membership_id_raw.isdigit():
        flash('Invalid membership.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))
    
    if action not in ('disable', 'delete'):
        flash('Invalid action.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    membership_id = int(membership_id_raw)
    membership = db.session.get(OrganizationMembership, membership_id)
    if not membership or int(membership.organization_id) != int(org_id):
        flash('Membership not found.', 'error')
        return redirect(url_for('main.org_admin_dashboard'))

    # Guard: do not remove/disable the last active user-manager.
    is_admin = _membership_has_permission(membership, 'users.manage')
    if is_admin and membership.is_active:
        active_memberships = (
            OrganizationMembership.query
            .filter_by(organization_id=int(org_id), is_active=True)
            .all()
        )
        active_admins = sum(1 for m in active_memberships if _membership_has_permission(m, 'users.manage'))
        if active_admins <= 1:
            flash('Cannot remove the last admin. Promote another member to admin first.', 'error')
            return redirect(url_for('main.org_admin_dashboard'))

    # Allow self-removal only when there is another active admin (if the user is an admin).
    if int(membership.user_id) == int(current_user.id):
        if is_admin and membership.is_active:
            active_memberships = (
                OrganizationMembership.query
                .filter_by(organization_id=int(org_id), is_active=True)
                .all()
            )
            active_admins = sum(1 for m in active_memberships if _membership_has_permission(m, 'users.manage'))
            if active_admins <= 1:
                flash('You are the only admin. Promote another admin before leaving the organisation.', 'error')
                return redirect(url_for('main.org_admin_dashboard'))

    try:
        if action == 'delete':
            # Completely delete the membership
            db.session.delete(membership)
            db.session.commit()
            flash('Member permanently removed from the organisation.', 'success')
        else:  # disable
            # Just deactivate
            membership.is_active = False
            db.session.commit()
            flash('Member disabled. You can re-enable them later if needed.', 'success')
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
    if not current_user.has_permission('documents.view', org_id=int(org_id)):
        abort(403)
    
    # Progressive loading: render the page immediately and fetch ML/ADLS data via AJAX.
    # `defer_ml=1` (default) prevents slow external calls from blocking the HTML response.
    defer_ml = (request.args.get('defer_ml', '1') or '1') != '0'
    ml_enabled = bool(current_app.config.get('ML_SUMMARY_ENABLED', False))
    skip_adls = (not ml_enabled) or defer_ml or (request.args.get('quick') == '1')
    
    # Parallel non-blocking queries: recent docs + count.
    from sqlalchemy.orm import joinedload
    recent_documents = (
        Document.query
        .options(joinedload(Document.uploader))
        .filter_by(organization_id=org_id, is_active=True)
        .order_by(Document.uploaded_at.desc())
        .limit(5)
        .all()
    )
    # Avoid full table scan for count; use an approximate or limit scope.
    total_documents = Document.query.filter_by(organization_id=org_id, is_active=True).limit(1000).count()
    
    # ML/ADLS data is deferred by default; provide a lightweight placeholder for the template.
    if current_app.config.get('TESTING') or skip_adls:
        ml_summary = {
            'avg_compliancy_rate': 0,
            'total_files': 0,
            'total_complete': 0,
            'total_needs_review': 0,
            'total_missing': 0,
            'file_summaries': [],
            'connection_status': 'Loading…',
        }
    else:
        ml_summary = azure_data_service.get_dashboard_summary(user_id=current_user.id, organization_id=org_id)
    
    return render_template('main/dashboard.html', 
                         title='Dashboard',
                         recent_documents=recent_documents,
                         total_documents=total_documents,
                         ml_summary=ml_summary,
                         skip_adls=skip_adls,
                         ml_enabled=ml_enabled)

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
    if not current_user.has_permission('documents.view', org_id=int(org_id)):
        abort(403)
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
    if not current_user.has_permission('documents.view', org_id=int(org_id)):
        abort(403)
    
    # Pagination to avoid loading thousands of documents at once.
    page = request.args.get('page', 1, type=int)
    per_page = int(request.args.get('per_page', '50') or 50)
    per_page = min(max(per_page, 10), 200)  # clamp between 10-200
    
    # Use options to eager-load relationships and avoid N+1 queries
    from sqlalchemy.orm import joinedload
    query = (
        Document.query
        .options(joinedload(Document.uploader))
        .filter_by(organization_id=org_id, is_active=True)
    )
    pagination = query.order_by(Document.uploaded_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    documents = pagination.items
    return render_template('main/evidence_repository.html', 
                         title='Evidence Repository',
                         documents=documents,
                         pagination=pagination)

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

    if not current_user.has_permission('documents.view', org_id=int(org_id)):
        abort(404)
    
    # Get document from database
    document = db.session.get(Document, int(doc_id))
    
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
    
    org_id = _active_org_id()
    if not current_user.has_permission('documents.delete', org_id=int(org_id)):
        abort(403)

    # Get document from database
    document = db.session.get(Document, int(doc_id))

    # Check if document exists and belongs to user
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
    document = db.session.get(Document, int(doc_id))
    
    # Check if document exists and belongs to user
    org_id = _active_org_id()
    if not current_user.has_permission('documents.view', org_id=int(org_id)):
        abort(403)
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
    maybe = _require_active_org()
    if maybe is not None:
        return maybe

    org_id = _active_org_id()
    if not current_user.has_permission('documents.view', org_id=int(org_id)):
        abort(403)

    # Get real ADLS data (org-scoped) — reuses cached result from dashboard if recent
    summary = azure_data_service.get_dashboard_summary(
        user_id=current_user.id,
        organization_id=org_id,
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
    
    return render_template(
        'main/ai_evidence.html',
        title='Upload Evidence',
        ai_evidence_entries=ai_evidence_entries,
    )


@bp.route('/organization/settings', methods=['GET', 'POST'])
@login_required
def organization_settings():
    from flask import abort, flash, make_response, request
    from app.main.forms import OrganizationBillingForm, OrganizationProfileSettingsForm

    maybe = _require_org_permission('org.manage')
    if maybe is not None:
        return maybe

    if not getattr(current_user, 'organization_id', None):
        flash('No organisation is associated with this account.', 'error')
        return redirect(url_for('main.dashboard'))

    organization = db.session.get(Organization, int(current_user.organization_id))
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
                organization.acn = (profile_form.acn.data or '').strip() or None
                organization.contact_number = (profile_form.contact_number.data or '').strip() or None
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

    organization = db.session.get(Organization, int(org_id))
    if not organization or not organization.logo_blob_name:
        abort(404)

    # Strong cache validators based on blob name (changes on upload).
    etag = f'W/"orglogo-{int(org_id)}-{organization.logo_blob_name}"'
    req_version = (request.args.get('v') or '').strip()
    inm = request.headers.get('If-None-Match')
    if _etag_matches_if_none_match(inm, etag):
        resp = make_response('', 304)
        resp.headers['ETag'] = etag
        if req_version and req_version == (organization.logo_blob_name or ''):
            resp.headers['Cache-Control'] = 'private, max-age=31536000, immutable'
        else:
            resp.headers['Cache-Control'] = 'private, max-age=300'
        current_app.logger.info('Org logo 304 (etag match) org_id=%s', org_id)
        return resp

    # Cache logo bytes in-memory to avoid repeated Azure fetches.
    try:
        logo_cache_seconds = int((current_app.config.get('ORG_LOGO_CACHE_SECONDS') or 300))
    except Exception:
        logo_cache_seconds = 300

    t0 = time.monotonic()
    cached = _get_cached_org_logo(int(org_id), organization.logo_blob_name)
    if cached:
        blob_data, cached_type = cached
        content_type = cached_type or organization.logo_content_type
        current_app.logger.info('Org logo served from memory cache org_id=%s', org_id)
    else:
        disk_cached = _get_disk_cached_org_logo(int(org_id), organization.logo_blob_name)
        if disk_cached:
            blob_data, disk_type = disk_cached
            content_type = disk_type or organization.logo_content_type
            _set_cached_org_logo(int(org_id), organization.logo_blob_name, blob_data, content_type, ttl_seconds=logo_cache_seconds)
            current_app.logger.info('Org logo served from disk cache org_id=%s', org_id)
        else:
            from app.services.azure_storage_service import azure_storage_service
            # Pass org_id to ensure correct path (org_X/ prefix)
            blob_data = azure_storage_service.download_blob(organization.logo_blob_name, organization_id=int(org_id))
            if not blob_data:
                abort(404)
            content_type = organization.logo_content_type
            _set_cached_org_logo(int(org_id), organization.logo_blob_name, blob_data, content_type, ttl_seconds=logo_cache_seconds)
            _set_disk_cached_org_logo(int(org_id), organization.logo_blob_name, blob_data, content_type)
            elapsed = time.monotonic() - t0
            current_app.logger.warning('Org logo fetched from Azure org_id=%s took %.2fs', org_id, elapsed)

    file_stream = io.BytesIO(blob_data)
    file_stream.seek(0)
    resp = send_file(
        file_stream,
        mimetype=content_type or 'application/octet-stream',
        as_attachment=False,
        download_name='logo'
    )

    resp.headers['ETag'] = etag
    if req_version and req_version == (organization.logo_blob_name or ''):
        resp.headers['Cache-Control'] = 'private, max-age=31536000, immutable'
    else:
        resp.headers['Cache-Control'] = 'private, max-age=300'
    return resp

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

    organization = db.session.get(Organization, int(org_id))
    if not organization or not organization.logo_blob_name:
        abort(404)

    etag = f'W/"orglogo-{int(org_id)}-{organization.logo_blob_name}"'
    req_version = (request.args.get('v') or '').strip()
    inm = request.headers.get('If-None-Match')
    if _etag_matches_if_none_match(inm, etag):
        resp = make_response('', 304)
        resp.headers['ETag'] = etag
        if req_version and req_version == (organization.logo_blob_name or ''):
            resp.headers['Cache-Control'] = 'private, max-age=31536000, immutable'
        else:
            resp.headers['Cache-Control'] = 'private, max-age=300'
        current_app.logger.info('Org logo(by_id) 304 (etag match) org_id=%s', org_id)
        return resp

    try:
        logo_cache_seconds = int((current_app.config.get('ORG_LOGO_CACHE_SECONDS') or 300))
    except Exception:
        logo_cache_seconds = 300

    t0 = time.monotonic()
    cached = _get_cached_org_logo(int(org_id), organization.logo_blob_name)
    if cached:
        blob_data, cached_type = cached
        content_type = cached_type or organization.logo_content_type
        current_app.logger.info('Org logo(by_id) served from memory cache org_id=%s', org_id)
    else:
        disk_cached = _get_disk_cached_org_logo(int(org_id), organization.logo_blob_name)
        if disk_cached:
            blob_data, disk_type = disk_cached
            content_type = disk_type or organization.logo_content_type
            _set_cached_org_logo(int(org_id), organization.logo_blob_name, blob_data, content_type, ttl_seconds=logo_cache_seconds)
            current_app.logger.info('Org logo(by_id) served from disk cache org_id=%s', org_id)
        else:
            from app.services.azure_storage_service import azure_storage_service
            # Pass org_id to ensure correct path (org_X/ prefix)
            blob_data = azure_storage_service.download_blob(organization.logo_blob_name, organization_id=int(org_id))
            if not blob_data:
                abort(404)
            content_type = organization.logo_content_type
            _set_cached_org_logo(int(org_id), organization.logo_blob_name, blob_data, content_type, ttl_seconds=logo_cache_seconds)
            _set_disk_cached_org_logo(int(org_id), organization.logo_blob_name, blob_data, content_type)
            elapsed = time.monotonic() - t0
            current_app.logger.warning('Org logo(by_id) fetched from Azure org_id=%s took %.2fs', org_id, elapsed)

    file_stream = io.BytesIO(blob_data)
    file_stream.seek(0)
    resp = send_file(
        file_stream,
        mimetype=content_type or 'application/octet-stream',
        as_attachment=False,
        download_name=f'{organization.name}_logo'
    )

    resp.headers['ETag'] = etag
    if req_version and req_version == (organization.logo_blob_name or ''):
        resp.headers['Cache-Control'] = 'private, max-age=31536000, immutable'
    else:
        resp.headers['Cache-Control'] = 'private, max-age=300'
    return resp

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
    document = db.session.get(Document, int(doc_id))
    if not document or document.uploaded_by != current_user.id:
        return redirect(url_for('main.documents'))
    
    return render_template('main/document_detail.html',
                         title=f'Document: {document.filename}',
                         document=document)

@bp.route('/gap-analysis')
@login_required
def gap_analysis():
    """Gap Analysis route."""
    maybe = _require_active_org()
    if maybe is not None:
        return maybe

    org_id = _active_org_id()
    if not current_user.has_permission('documents.view', org_id=int(org_id)):
        abort(403)

    # Get real ADLS data (org-scoped). Keep this endpoint quiet to avoid slow log I/O.
    summary = azure_data_service.get_dashboard_summary(user_id=current_user.id, organization_id=org_id)
    
    # Build gap analysis data from ADLS
    gap_data = []
    
    if summary.get('file_summaries'):
        for file_summary in summary['file_summaries']:
            frameworks_data = file_summary.get('frameworks', [])
            
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
                gap_data.append(item)
    
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
    from app.main.forms import UserProfileForm
    from app.models import Department

    form = UserProfileForm(obj=current_user)

    if form.validate_on_submit():
        current_user.first_name = (form.first_name.data or '').strip() or None
        current_user.last_name = (form.last_name.data or '').strip() or None

        # Keep full_name in sync if it was empty.
        if not (current_user.full_name or '').strip():
            parts = [p for p in [(current_user.first_name or ''), (current_user.last_name or '')] if p.strip()]
            current_user.full_name = ' '.join([p.strip() for p in parts]) or None

        try:
            db.session.commit()
            flash('Profile updated.', 'success')
            return redirect(url_for('main.profile'))
        except Exception as e:
            db.session.rollback()
            flash('Profile update failed. Please try again.', 'error')
            current_app.logger.error(f"Profile update failed for user {current_user.id}: {e}")

    # Get current membership and departments for self-assignment
    current_membership = None
    departments = []
    org_id = getattr(current_user, 'organization_id', None)
    if org_id:
        current_membership = (
            OrganizationMembership.query
            .filter_by(user_id=int(current_user.id), organization_id=int(org_id), is_active=True)
            .first()
        )
        departments = (
            Department.query
            .filter_by(organization_id=int(org_id))
            .order_by(Department.name.asc())
            .all()
        )

    # Get current membership and departments for self-assignment
    current_membership = None
    departments = []
    org_id = getattr(current_user, 'organization_id', None)
    if org_id:
        current_membership = (
            OrganizationMembership.query
            .filter_by(user_id=int(current_user.id), organization_id=int(org_id), is_active=True)
            .first()
        )
        departments = (
            Department.query
            .filter_by(organization_id=int(org_id))
            .order_by(Department.name.asc())
            .all()
        )

    return render_template(
        'main/profile.html',
        title='My Profile',
        form=form,
        current_membership=current_membership,
        departments=departments
    )


@bp.route('/profile/department', methods=['POST'])
@login_required
def profile_update_department():
    """Allow user to assign themselves to a department."""
    from app.models import Department

    org_id = getattr(current_user, 'organization_id', None)
    if not org_id:
        flash('No organisation associated with your account.', 'error')
        return redirect(url_for('main.profile'))

    membership = (
        OrganizationMembership.query
        .filter_by(user_id=int(current_user.id), organization_id=int(org_id), is_active=True)
        .first()
    )
    if not membership:
        flash('Membership not found.', 'error')
        return redirect(url_for('main.profile'))

    dept_id_str = (request.form.get('department_id') or '').strip()
    
    if not dept_id_str:
        # Unassign department
        membership.department_id = None
        try:
            db.session.commit()
            flash('Department unassigned.', 'success')
        except Exception as e:
            db.session.rollback()
            flash('Failed to update department.', 'error')
            current_app.logger.error(f"Failed to unassign department for user {current_user.id}: {e}")
        return redirect(url_for('main.profile'))

    try:
        dept_id = int(dept_id_str)
    except ValueError:
        flash('Invalid department selected.', 'error')
        return redirect(url_for('main.profile'))

    # Verify department belongs to the same organization
    department = db.session.get(Department, dept_id)
    if not department or department.organization_id != int(org_id):
        flash('Invalid department selected.', 'error')
        return redirect(url_for('main.profile'))

    membership.department_id = dept_id
    try:
        db.session.commit()
        flash(f'Department updated to "{department.name}".', 'success')
    except Exception as e:
        db.session.rollback()
        flash('Failed to update department.', 'error')
        current_app.logger.error(f"Failed to update department for user {current_user.id}: {e}")

    return redirect(url_for('main.profile'))


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
    if not current_app.config.get('ML_SUMMARY_ENABLED', False):
        abort(404)

    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

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
    if not current_app.config.get('ML_SUMMARY_ENABLED', False):
        abort(404)

    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

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
    maybe = _require_active_org()
    if maybe is not None:
        return jsonify({'error': 'No active organization'}), 400

    org_id = _active_org_id()
    if not current_user.has_permission('documents.view', org_id=int(org_id)):
        return jsonify({'error': 'Forbidden'}), 403

    if current_app.config.get('TESTING'):
        return jsonify(get_mock_ml_summary())

    # ML feature is not implemented yet; keep endpoint fast and predictable.
    if not current_app.config.get('ML_SUMMARY_ENABLED', False):
        return jsonify({
            'total_files': 0,
            'avg_compliancy_rate': 0,
            'total_requirements': 0,
            'total_complete': 0,
            'total_needs_review': 0,
            'total_missing': 0,
            'last_updated': None,
            'file_summaries': [],
            'connection_status': 'Coming soon',
        })

    summary = azure_data_service.get_dashboard_summary(user_id=current_user.id, organization_id=org_id)
    return jsonify(summary)

@bp.route('/adls-raw-data')
@login_required
def adls_raw_data():
    """Show raw ADLS data."""
    if not current_app.config.get('ML_SUMMARY_ENABLED', False):
        abort(404)

    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

    return render_template('main/adls_raw_data.html',
                         title='ADLS Raw Data',
                         ml_summary=get_mock_ml_summary())

@bp.route('/adls-connection')
@login_required
def adls_connection():
    """Show ADLS connection status."""
    if not current_app.config.get('ML_SUMMARY_ENABLED', False):
        abort(404)

    maybe = _require_org_admin()
    if maybe is not None:
        return maybe

    return render_template('main/adls_connection.html',
                         title='ADLS Connection',
                         ml_summary=get_mock_ml_summary())

@bp.route('/audit-export')
@login_required
def audit_export():
    """Audit export route for generating compliance reports."""
    maybe = _require_org_permission('audits.export')
    if maybe is not None:
        return maybe

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
    maybe = _require_org_permission('audits.export')
    if maybe is not None:
        return maybe

    from flask import send_file
    from app.services.report_generator import report_generator
    from datetime import datetime

    org_id = _active_org_id()
    organization = db.session.get(Organization, int(org_id))
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
    summary = azure_data_service.get_dashboard_summary(user_id=current_user.id, organization_id=org_id)
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


@bp.route('/system-logs')
@login_required
def system_logs():
    """System logs viewing interface (organisation admin only)."""
    maybe = _require_active_org()
    if maybe is not None:
        return maybe

    org_id = _active_org_id()
    
    # Check if user is admin or has org.settings permission
    from app.models import OrganizationMembership
    org_member = OrganizationMembership.query.filter_by(
        user_id=current_user.id,
        organization_id=org_id
    ).first()
    
    # Allow if user is org admin or has explicit org.settings permission
    if not (org_member and (org_member.role == 'Admin' or current_user.has_permission('org.settings', org_id=int(org_id)))):
        flash('You must be an organisation administrator to view system logs.', 'error')
        return redirect(url_for('main.dashboard'))
    
    # Get filter parameters
    log_type = request.args.get('log_type', 'all')
    event_type = request.args.get('event_type', '')
    time_range = request.args.get('time_range', '24h')
    user_id_filter = request.args.get('user_id', '')
    
    # Parse time range
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)

    # Display timestamps in the user's preferred timezone.
    # Source timestamps are stored in UTC in the database.
    display_tz_name = (getattr(current_user, 'time_zone', None) or 'Australia/Sydney').strip() or 'Australia/Sydney'
    display_tz = timezone.utc
    display_tz_label = 'UTC'
    try:
        from zoneinfo import ZoneInfo  # py>=3.9

        display_tz = ZoneInfo(display_tz_name)
        # Use current time to derive a readable label (handles DST).
        display_tz_label = (now.astimezone(display_tz).tzname() or display_tz_name)
    except Exception:
        display_tz = timezone.utc
        display_tz_label = 'UTC'
    time_ranges = {
        '1h': timedelta(hours=1),
        '24h': timedelta(hours=24),
        '7d': timedelta(days=7),
        '30d': timedelta(days=30),
    }
    time_delta = time_ranges.get(time_range, timedelta(hours=24))
    start_time = now - time_delta
    
    logs = []

    # NOTE: We currently back System Logs with persisted DB events.
    # `LoginEvent` captures login success/failure, and we scope to the active organisation
    # by selecting events for users who are members of that organisation.
    if log_type in ['all', 'security']:
        from app.models import LoginEvent
        from sqlalchemy import desc

        member_ids = [m.user_id for m in OrganizationMembership.query.filter_by(organization_id=org_id).all()]

        if member_ids:
            q = LoginEvent.query.filter(LoginEvent.user_id.in_(member_ids))
            if start_time is not None:
                q = q.filter(LoginEvent.created_at >= start_time)

            if (user_id_filter or '').strip():
                try:
                    q = q.filter(LoginEvent.user_id == int(user_id_filter))
                except Exception:
                    pass

            if (event_type or '').strip() == 'LOGIN_SUCCESS':
                q = q.filter(LoginEvent.success.is_(True))
            elif (event_type or '').strip() == 'LOGIN_FAILURE':
                q = q.filter(LoginEvent.success.is_(False))

            events = q.order_by(desc(LoginEvent.created_at)).limit(500).all()
            for evt in events:
                created_at = evt.created_at
                if created_at and getattr(created_at, 'tzinfo', None) is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)

                created_at_local = None
                try:
                    created_at_local = created_at.astimezone(display_tz) if created_at else None
                except Exception:
                    created_at_local = created_at

                is_success = bool(evt.success)
                derived_event_type = 'LOGIN_SUCCESS' if is_success else 'LOGIN_FAILURE'
                derived_description = 'User logged in successfully' if is_success else 'Failed login attempt'

                user_name = None
                user_email = None
                if getattr(evt, 'user', None) is not None:
                    try:
                        user_name = evt.user.display_name()
                    except Exception:
                        user_name = None
                    user_email = getattr(evt.user, 'email', None)

                logs.append({
                    'timestamp': created_at_local.strftime('%Y-%m-%d %H:%M:%S %Z') if created_at_local else None,
                    'log_type': 'security',
                    'event_type': derived_event_type,
                    'event_description': derived_description,
                    'user_id': evt.user_id,
                    'user_name': user_name,
                    'user_email': user_email or evt.email,
                    'organization_id': org_id,
                    'ip_address': evt.ip_address,
                    'details': {
                        'email': evt.email,
                        'provider': evt.provider,
                        'success': is_success,
                        'reason': evt.reason,
                        'user_agent': evt.user_agent,
                    }
                })
    
    # Statistics
    total_logs = len(logs)
    security_events = len([l for l in logs if l.get('log_type') == 'security'])
    error_count = len([l for l in logs if l.get('log_type') == 'error'])
    failed_logins = len([l for l in logs if l.get('event_type') == 'LOGIN_FAILURE'])
    
    appinsights_enabled = current_app.config.get('APPINSIGHTS_ENABLED', False)
    
    return render_template('main/system_logs.html',
                         title='System Logs',
                         logs=logs,
                         log_type=log_type,
                         event_type=event_type,
                         time_range=time_range,
                         user_id=user_id_filter,
                         total_logs=total_logs,
                         security_events=security_events,
                         error_count=error_count,
                         failed_logins=failed_logins,
                         display_tz_label=display_tz_label,
                         appinsights_enabled=appinsights_enabled)
