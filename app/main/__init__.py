from flask import Blueprint, redirect, request, url_for
from flask_login import current_user

bp = Blueprint('main', __name__)


@bp.before_request
def require_onboarding():
	if not current_user.is_authenticated:
		return None

	# Force the user to complete organization setup before using the app.
	if not getattr(current_user, 'organization_id', None):
		# Allow the homepage to redirect naturally.
		if request.endpoint == 'main.index':
			return None
		return redirect(url_for('onboarding.organization'))

from app.main import routes