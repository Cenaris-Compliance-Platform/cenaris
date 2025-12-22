from flask import render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from flask_mail import Message
from app.auth import bp
from app.auth.forms import LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm
from app.models import User
from app import db, oauth, mail


def _after_login_redirect():
    # If onboarding not complete, force the wizard.
    if not getattr(current_user, 'organization_id', None):
        return redirect(url_for('onboarding.organization'))
    return redirect(url_for('main.dashboard'))


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _password_reset_token(user: User) -> str:
    return _serializer().dumps({'user_id': user.id, 'email': user.email}, salt='password-reset')


def _verify_password_reset_token(token: str, max_age_seconds: int = 3600) -> dict | None:
    try:
        data = _serializer().loads(token, salt='password-reset', max_age=max_age_seconds)
        if not isinstance(data, dict):
            return None
        if 'user_id' not in data or 'email' not in data:
            return None
        return data
    except (BadSignature, SignatureExpired):
        return None


def _mail_configured() -> bool:
    return bool(current_app.config.get('MAIL_SERVER') and current_app.config.get('MAIL_DEFAULT_SENDER'))


def _send_password_reset_email(user: User, reset_url: str) -> None:
    # If mail isn't configured (common for local dev), we still provide the link via logs.
    if not _mail_configured():
        current_app.logger.warning('MAIL not configured; password reset URL: %s', reset_url)
        return

    msg = Message(
        subject='Reset your password',
        recipients=[user.email],
        body=(
            'We received a request to reset your password.\n\n'
            f'Reset link: {reset_url}\n\n'
            'If you did not request this, you can ignore this email.'
        ),
    )
    mail.send(msg)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login route."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    form = LoginForm()
    
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        password = form.password.data

        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=form.remember_me.data)
            flash('Welcome back! You have been successfully signed in.', 'success')
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return _after_login_redirect()
        else:
            flash('Invalid email address or password. Please try again.', 'error')
    
    return render_template('auth/login.html', form=form, title='Sign In')

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration route (generic), followed by onboarding wizard."""
    if current_user.is_authenticated:
        return _after_login_redirect()
    
    form = RegisterForm()
    
    if form.validate_on_submit():
        full_name = form.full_name.data.strip()
        email = form.email.data.lower().strip()
        password = form.password.data
        
        try:
            user = User(
                email=email,
                full_name=full_name,
                role='User',
                organization_id=None
            )
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            flash('Account created. Let\'s finish your setup.', 'success')
            return redirect(url_for('onboarding.organization'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while creating your account. Please try again.', 'error')
    
    return render_template('auth/signup.html', form=form, title='Create Account')


@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if current_user.is_authenticated:
        return _after_login_redirect()

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        user = User.query.filter_by(email=email).first()

        # Always show the same message to avoid account enumeration.
        flash('If that email exists, a reset link has been sent.', 'info')

        if user and user.is_active:
            token = _password_reset_token(user)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            try:
                _send_password_reset_email(user, reset_url)
            except Exception:
                current_app.logger.exception('Failed to send password reset email')
        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html', form=form, title='Forgot Password')


@bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    if current_user.is_authenticated:
        return _after_login_redirect()

    data = _verify_password_reset_token(token)
    if not data:
        flash('This reset link is invalid or has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))

    user = User.query.get(int(data['user_id']))
    if not user or (user.email or '').lower().strip() != (data.get('email') or '').lower().strip():
        flash('This reset link is invalid. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        try:
            db.session.commit()
            flash('Your password has been reset. You can now sign in.', 'success')
            return redirect(url_for('auth.login'))
        except Exception:
            db.session.rollback()
            flash('Failed to reset password. Please try again.', 'error')

    return render_template('auth/reset_password.html', form=form, title='Reset Password')


@bp.route('/oauth/<provider>')
def oauth_login(provider):
    if current_user.is_authenticated:
        return _after_login_redirect()

    client = oauth.create_client(provider)
    if not client:
        flash(f'{provider.title()} sign-in is not configured yet.', 'error')
        return redirect(url_for('auth.login'))

    redirect_uri = url_for('auth.oauth_callback', provider=provider, _external=True)
    return client.authorize_redirect(redirect_uri)


@bp.route('/oauth/<provider>/callback')
def oauth_callback(provider):
    if current_user.is_authenticated:
        return _after_login_redirect()

    client = oauth.create_client(provider)
    if not client:
        flash(f'{provider.title()} sign-in is not configured yet.', 'error')
        return redirect(url_for('auth.login'))

    token = client.authorize_access_token()
    userinfo = None

    # Prefer ID token claims when present.
    try:
        userinfo = client.parse_id_token(token)
    except Exception:
        userinfo = None

    if not userinfo:
        # Fallback to userinfo endpoint.
        userinfo = token.get('userinfo')

    email = (userinfo.get('email') if isinstance(userinfo, dict) else None) or ''
    email = email.lower().strip()

    # Microsoft sometimes returns preferred_username instead of email.
    if not email and isinstance(userinfo, dict):
        email = (userinfo.get('preferred_username') or '').lower().strip()

    if not email:
        flash('Unable to read your email from the provider.', 'error')
        return redirect(url_for('auth.login'))

    full_name = (userinfo.get('name') if isinstance(userinfo, dict) else None) or None

    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(email=email, full_name=full_name, role='User', organization_id=None)
        db.session.add(user)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash('Failed to create your account. Please try again.', 'error')
            return redirect(url_for('auth.login'))

    if not user.is_active:
        flash('This account is disabled. Please contact support.', 'error')
        return redirect(url_for('auth.login'))

    login_user(user)
    flash('Signed in successfully.', 'success')
    return _after_login_redirect()

@bp.route('/logout', methods=['POST'])
def logout():
    """User logout route."""
    if current_user.is_authenticated:
        logout_user()
        flash('You have been successfully signed out.', 'info')
    return redirect(url_for('main.index'))