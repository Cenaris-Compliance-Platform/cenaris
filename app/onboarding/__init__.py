from flask import Blueprint

bp = Blueprint('onboarding', __name__)

from app.onboarding import routes
