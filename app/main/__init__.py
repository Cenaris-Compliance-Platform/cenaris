from flask import Blueprint, redirect, request, url_for, session, current_app
from flask_login import current_user

bp = Blueprint('main', __name__)


@bp.before_request
def require_onboarding():
	if not current_user.is_authenticated:
		return None

	# Avoid repeated onboarding DB checks for asset-like endpoints.
	# These routes have their own auth/permission checks.
	if request.endpoint in {
		'main.organization_logo',
		'main.organization_logo_by_id',
	}:
		return None

	# Enforce email verification before allowing access to the app.
	# (Auth endpoints live under a different blueprint, so they are not blocked here.)
	if not getattr(current_user, 'email_verified', False):
		# Allow homepage and theme toggle so the UI still renders.
		if request.endpoint in {'main.index', 'main.set_theme'}:
			return None
		return redirect(url_for('auth.verify_email_request', email=getattr(current_user, 'email', '')))

	# Force the user to complete organization setup before using the app.
	org_id = getattr(current_user, 'organization_id', None)
	if not org_id:
		# Allow the homepage to redirect naturally.
		if request.endpoint == 'main.index':
			return None
		return redirect(url_for('onboarding.organization'))

	# Cache onboarding status briefly in the session to avoid a DB lookup on every request.
	try:
		cache_seconds = int((current_app.config.get('ONBOARDING_CHECK_CACHE_SECONDS') or 30))
	except Exception:
		cache_seconds = 30

	if cache_seconds > 0:
		cached_org_id = session.get('onboarding_org_id')
		cached_ok = session.get('onboarding_ok')
		cached_at = session.get('onboarding_checked_at')
		try:
			cached_at = float(cached_at) if cached_at is not None else None
		except Exception:
			cached_at = None

		from time import time as _time
		now = _time()
		if (
			cached_org_id is not None
			and str(cached_org_id) == str(org_id)
			and cached_at is not None
			and (now - cached_at) < cache_seconds
			and cached_ok is True
		):
			return None

	from app.models import Organization
	from app import db
	org = db.session.get(Organization, int(org_id))
	ok = bool(org and org.onboarding_complete())
	if cache_seconds > 0:
		try:
			from time import time as _time
			session['onboarding_org_id'] = int(org_id)
			session['onboarding_ok'] = bool(ok)
			session['onboarding_checked_at'] = float(_time())
		except Exception:
			pass

	if not ok:
		return redirect(url_for('onboarding.organization'))

from app.main import routes