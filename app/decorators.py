from functools import wraps
from flask import redirect, url_for, flash, request, abort
from flask_login import current_user

def login_required(f):
    """
    Custom login required decorator with better error handling.
    This supplements Flask-Login's login_required decorator.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please sign in to access this page.', 'info')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def anonymous_required(f):
    """
    Decorator to ensure user is not logged in.
    Redirects authenticated users to dashboard.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated:
            return redirect(url_for('main.dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """
    Decorator to require admin privileges.
    For future use when admin functionality is added.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Backward-compatible alias for org-level admin permission.
        if not current_user.is_authenticated:
            flash('Please sign in to access this page.', 'info')
            return redirect(url_for('auth.login', next=request.url))

        org_id = getattr(current_user, 'organization_id', None)
        if not current_user.has_permission('users.manage', org_id=org_id):
            abort(403)

        return f(*args, **kwargs)
    return decorated_function


def permission_required(*permission_codes: str, any_of: bool = False):
    """Require one (or all) permissions for the active organization.

    By default, all permissions must be present. Set any_of=True to allow any.
    """

    required = [c.strip() for c in permission_codes if (c or '').strip()]

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please sign in to access this page.', 'info')
                return redirect(url_for('auth.login', next=request.url))

            org_id = getattr(current_user, 'organization_id', None)
            if not org_id:
                flash('Please select an organisation to continue.', 'info')
                return redirect(url_for('onboarding.organization'))

            if not required:
                return f(*args, **kwargs)

            checks = [current_user.has_permission(code, org_id=int(org_id)) for code in required]
            ok = any(checks) if any_of else all(checks)
            if not ok:
                abort(403)

            return f(*args, **kwargs)

        return decorated_function

    return decorator