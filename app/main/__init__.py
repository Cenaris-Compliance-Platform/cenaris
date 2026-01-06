from flask import Blueprint, redirect, request, url_for
from flask_login import current_user

bp = Blueprint('main', __name__)


@bp.before_request
def require_onboarding():
	if not current_user.is_authenticated:
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

	from app.models import Organization
	from app import db
	org = db.session.get(Organization, int(org_id))
	if not org or not org.onboarding_complete():
		return redirect(url_for('onboarding.organization'))

from app.main import routes