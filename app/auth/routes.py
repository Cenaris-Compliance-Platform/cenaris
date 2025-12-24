from flask import render_template, redirect, url_for, flash, request, current_app, session
from flask_login import login_user, logout_user, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import requests

from flask_mail import Message
from app.auth import bp
from app.auth.forms import LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm
from datetime import datetime, timezone

from app.models import User, Organization, OrganizationMembership
from app import db, oauth, mail


_RESEND_VERIFY_EMAIL_COOLDOWN_SECONDS = 60
_RESET_PASSWORD_REQUEST_COOLDOWN_SECONDS = 60


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _get_pending_verification_email() -> str:
    if current_user.is_authenticated and not getattr(current_user, 'email_verified', False):
        return (current_user.email or '').strip().lower()
    return (session.get('pending_verification_email') or '').strip().lower()


def _get_pending_reset_email() -> str:
    return (session.get('pending_reset_email') or '').strip().lower()


def _after_login_redirect():
    # If the user has org memberships but no active org selected, select one.
    if not getattr(current_user, 'organization_id', None):
        membership = (
            OrganizationMembership.query
            .filter_by(user_id=int(current_user.id), is_active=True)
            .order_by(OrganizationMembership.created_at.asc())
            .first()
        )
        if membership:
            current_user.organization_id = int(membership.organization_id)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()

    # If onboarding not complete, force the wizard.
    org_id = getattr(current_user, 'organization_id', None)
    if not org_id:
        return redirect(url_for('onboarding.organization'))

    org = Organization.query.get(int(org_id))
    if not org or not org.onboarding_complete():
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


def _email_verification_required() -> bool:
    # Always require email verification (production best practice).
    return True


def _email_verify_token(user: User) -> str:
    return _serializer().dumps({'user_id': user.id, 'email': user.email}, salt='email-verify')


def _verify_email_token(token: str, max_age_seconds: int = 60 * 60 * 24 * 7) -> dict | None:
    try:
        data = _serializer().loads(token, salt='email-verify', max_age=max_age_seconds)
        if not isinstance(data, dict):
            return None
        if 'user_id' not in data or 'email' not in data:
            return None
        return data
    except (BadSignature, SignatureExpired):
        return None


def _send_email_verification_email(user: User, verify_url: str) -> None:
    if not _mail_configured():
        current_app.logger.warning('MAIL not configured; verify-email URL: %s', verify_url)
        return

    msg = Message(
        subject='Verify your email',
        recipients=[user.email],
        body=(
            'Welcome to CCM. Please verify your email address to activate your account.\n\n'
            f'Verify link: {verify_url}\n\n'
            'If you did not create this account, you can ignore this email.'
        ),
    )
    mail.send(msg)


def _turnstile_enabled() -> bool:
    return bool(current_app.config.get('TURNSTILE_SECRET_KEY'))


def _verify_turnstile() -> bool:
    """Verify Cloudflare Turnstile CAPTCHA if configured; otherwise allow."""
    if not _turnstile_enabled():
        return True

    token = (request.form.get('cf-turnstile-response') or '').strip()
    if not token:
        return False

    secret = current_app.config.get('TURNSTILE_SECRET_KEY')
    try:
        resp = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={
                'secret': secret,
                'response': token,
                'remoteip': request.remote_addr,
            },
            timeout=5,
        )
        data = resp.json() if resp is not None else {}
        return bool(data.get('success'))
    except Exception:
        current_app.logger.exception('Turnstile verification failed')
        return False


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
            if _email_verification_required() and not getattr(user, 'email_verified', False):
                flash('Please verify your email before signing in. You can request a new verification link below.', 'warning')
                return redirect(url_for('auth.verify_email_request', email=email))
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
        if not _verify_turnstile():
            flash('CAPTCHA verification failed. Please try again.', 'error')
            return render_template('auth/signup.html', form=form, title='Create Account')

        org_name = form.organization_name.data.strip()
        abn = (form.abn.data or '').strip()
        first_name = (form.first_name.data or '').strip()
        last_name = (form.last_name.data or '').strip()
        title = (form.title.data or '').strip()
        mobile_number = (form.mobile_number.data or '').strip() or None
        time_zone = (form.time_zone.data or '').strip() or 'Australia/Sydney'
        email = form.email.data.lower().strip()
        password = form.password.data
        
        try:
            organization = Organization(
                name=org_name,
                abn=abn,
                contact_email=email,
            )
            db.session.add(organization)
            db.session.flush()

            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                title=title,
                mobile_number=mobile_number,
                time_zone=time_zone,
                full_name=(f"{first_name} {last_name}").strip(),
                role='Admin',
                organization_id=organization.id,
                email_verified=False,
                terms_accepted_at=datetime.now(timezone.utc),
            )
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            membership = OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role='Admin',
                is_active=True,
            )
            db.session.add(membership)
            db.session.commit()

            if _email_verification_required():
                token = _email_verify_token(user)
                verify_url = url_for('auth.verify_email', token=token, _external=True)
                try:
                    _send_email_verification_email(user, verify_url)
                except Exception:
                    current_app.logger.exception('Failed to send verification email')

                # Carry the email through to the verify screen so the user does not
                # need to type it again just to resend.
                session['pending_verification_email'] = user.email
                session['verify_email_last_sent_at'] = _now_ts()

                if not _mail_configured():
                    flash('Email is required to continue. MAIL is not configured; check the server logs for the verification link.', 'warning')

                flash('Account created. Please verify your email to continue.', 'info')
                return redirect(url_for('auth.verify_email_request'))

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

    # Prefill the email when arriving from login, or after a previous request.
    email_prefill = (request.args.get('email') or '').strip().lower() or _get_pending_reset_email()
    if request.method == 'GET' and email_prefill and not (form.email.data or '').strip():
        form.email.data = email_prefill

    sent = (request.args.get('sent') or '').strip() in {'1', 'true', 'yes'}

    if form.validate_on_submit():
        last_sent_at = int(session.get('reset_password_last_sent_at') or 0)
        wait_seconds = _RESET_PASSWORD_REQUEST_COOLDOWN_SECONDS - (_now_ts() - last_sent_at)
        if wait_seconds > 0:
            flash(f'Please wait {wait_seconds} seconds before requesting another reset link.', 'warning')
            return render_template('auth/forgot_password.html', form=form, title='Forgot Password', sent=False)

        if not _verify_turnstile():
            flash('CAPTCHA verification failed. Please try again.', 'error')
            return render_template('auth/forgot_password.html', form=form, title='Forgot Password', sent=False)

        email = form.email.data.lower().strip()
        user = User.query.filter_by(email=email).first()

        # Always show the same message to avoid account enumeration.
        flash('If that email exists, a reset link has been sent.', 'info')

        session['pending_reset_email'] = email
        session['reset_password_last_sent_at'] = _now_ts()

        if user and user.is_active:
            token = _password_reset_token(user)
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            try:
                _send_password_reset_email(user, reset_url)
            except Exception:
                current_app.logger.exception('Failed to send password reset email')

        return redirect(url_for('auth.forgot_password', sent='1'))

    return render_template('auth/forgot_password.html', form=form, title='Forgot Password', sent=sent)


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
            try:
                session.pop('pending_reset_email', None)
                session.pop('reset_password_last_sent_at', None)
            except Exception:
                pass
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
        user = User(email=email, full_name=full_name, role='User', organization_id=None, email_verified=True)
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


@bp.route('/verify-email/<token>')
def verify_email(token):
    # Allow verifying from an email link even if the user is currently signed in.
    # Otherwise, an authenticated-but-unverified session can get stuck in a redirect loop
    # between the main blueprint guard and the resend/verify endpoints.
    if current_user.is_authenticated and getattr(current_user, 'email_verified', False):
        return _after_login_redirect()

    data = _verify_email_token(token)
    if not data:
        flash('This verification link is invalid or has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.verify_email_request'))

    user = User.query.get(int(data['user_id']))
    if not user or (user.email or '').lower().strip() != (data.get('email') or '').lower().strip():
        flash('This verification link is invalid. Please request a new one.', 'error')
        return redirect(url_for('auth.verify_email_request'))

    user.email_verified = True
    try:
        db.session.commit()
        # Clear any pending verification state once verified.
        try:
            session.pop('pending_verification_email', None)
            session.pop('verify_email_last_sent_at', None)
        except Exception:
            pass
        if user.is_active:
            login_user(user)
            flash('Email verified successfully.', 'success')
            return _after_login_redirect()

        flash('Email verified successfully. You can now sign in.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to verify email. Please try again.', 'error')

    return redirect(url_for('auth.login'))


@bp.route('/verify-email', methods=['GET', 'POST'])
def verify_email_request():
    # If the user is signed in but not verified yet, they must be able to access this page.
    # Redirecting them back into the app creates an infinite redirect loop.
    if current_user.is_authenticated and getattr(current_user, 'email_verified', False):
        return _after_login_redirect()

    email_prefill = (request.args.get('email') or '').strip().lower()
    if not email_prefill:
        email_prefill = _get_pending_verification_email()

    prefilled = bool(email_prefill)
    if request.method == 'POST':
        email_prefill = (request.form.get('email') or '').strip().lower() or _get_pending_verification_email()
        prefilled = bool(email_prefill)

        last_sent_at = int(session.get('verify_email_last_sent_at') or 0)
        wait_seconds = _RESEND_VERIFY_EMAIL_COOLDOWN_SECONDS - (_now_ts() - last_sent_at)
        if wait_seconds > 0:
            flash(f'Please wait {wait_seconds} seconds before resending.', 'warning')
            return render_template('auth/verify_email.html', title='Verify Email', email=email_prefill, prefilled=prefilled, cooldown_seconds=max(wait_seconds, 0))

        # Optional: protect resend form too.
        if not _verify_turnstile():
            flash('CAPTCHA verification failed. Please try again.', 'error')
            return render_template('auth/verify_email.html', title='Verify Email', email=email_prefill, prefilled=prefilled)

        user = User.query.filter_by(email=email_prefill).first()
        flash('If that email exists, a verification link has been sent.', 'info')

        if user and user.is_active and not getattr(user, 'email_verified', False):
            token = _email_verify_token(user)
            verify_url = url_for('auth.verify_email', token=token, _external=True)
            try:
                _send_email_verification_email(user, verify_url)
                session['pending_verification_email'] = user.email
                session['verify_email_last_sent_at'] = _now_ts()
            except Exception:
                current_app.logger.exception('Failed to resend verification email')

        # Keep the user on the "check your email" screen.
        return redirect(url_for('auth.verify_email_request'))

    return render_template('auth/verify_email.html', title='Verify Email', email=email_prefill, prefilled=prefilled, cooldown_seconds=0)

@bp.route('/logout', methods=['POST'])
def logout():
    """User logout route."""
    if current_user.is_authenticated:
        logout_user()
        flash('You have been successfully signed out.', 'info')
    return redirect(url_for('main.index'))