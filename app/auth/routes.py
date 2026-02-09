from flask import render_template, redirect, url_for, flash, request, current_app, session, jsonify
from flask_login import login_user, logout_user, current_user
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
import requests
import os

from flask_mail import Message
from app.auth import bp
from app.auth.forms import LoginForm, RegisterForm, ForgotPasswordForm, ResetPasswordForm
from datetime import datetime, timezone, timedelta
from sqlalchemy.exc import SQLAlchemyError

from app.models import User, Organization, OrganizationMembership, LoginEvent, SuspiciousIP
from app import db, oauth, mail, limiter
from app.services.logging_service import log_security_event


_RESEND_VERIFY_EMAIL_COOLDOWN_SECONDS = 60
_RESET_PASSWORD_REQUEST_COOLDOWN_SECONDS = 60

_PASSWORD_RESET_TOKEN_SALT = 'password-reset'
_ORG_INVITE_TOKEN_SALT = 'org-invite'


def _safe_int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name) or default)
    except Exception:
        return default


def _password_reset_token_ttl_seconds() -> int:
    # Default 1 hour for security.
    return max(60, _safe_int_env('PASSWORD_RESET_TOKEN_TTL_SECONDS', 60 * 60))


def _org_invite_token_ttl_seconds() -> int:
    # Default 24 hours so invited users have time to accept.
    return max(60, _safe_int_env('ORG_INVITE_TOKEN_TTL_SECONDS', 60 * 60 * 24))

_LOGIN_LOCKOUT_THRESHOLD = 5
_LOGIN_LOCKOUT_SECONDS = 60 * 15
_FAILED_LOGIN_WINDOW_SECONDS = 60 * 30

_SUSPICIOUS_IP_WINDOW_SECONDS = 60 * 10
_SUSPICIOUS_IP_FAILURE_THRESHOLD = 20
_SUSPICIOUS_IP_BLOCK_SECONDS = 60 * 30


def _looks_like_schema_mismatch(err: Exception) -> bool:
    """Best-effort detection of missing migrations (table/column not found)."""
    # psycopg2 exposes SQLSTATE codes for common schema issues.
    orig = getattr(err, 'orig', None)
    pgcode = getattr(orig, 'pgcode', None)
    if pgcode in {'42P01', '42703'}:  # undefined_table, undefined_column
        return True

    msg = (str(orig) if orig is not None else str(err) or '').lower()
    return any(
        needle in msg
        for needle in [
            'does not exist',
            'undefined table',
            'undefined column',
            'relation',
            'column',
        ]
    )


def _schema_upgrade_hint() -> str:
    return (
        'Database schema appears out of date. Run `flask db upgrade` against your configured database '
        '(your DEV_DATABASE_URL) and restart the server.'
    )


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _get_pending_verification_email() -> str:
    if current_user.is_authenticated and not getattr(current_user, 'email_verified', False):
        return (current_user.email or '').strip().lower()
    return (session.get('pending_verification_email') or '').strip().lower()


def _get_pending_reset_email() -> str:
    return (session.get('pending_reset_email') or '').strip().lower()


def _after_login_redirect():
    # Always verify the user has an active membership for their current org.
    # If organization_id is set but there's no active membership, fix it.
    org_id = getattr(current_user, 'organization_id', None)
    
    if org_id:
        # Verify this org_id has an active membership
        membership = (
            OrganizationMembership.query
            .filter_by(user_id=int(current_user.id), organization_id=int(org_id), is_active=True)
            .first()
        )
        if not membership:
            # Current org_id is invalid, clear it and find a valid one
            org_id = None
    
    # If no valid org_id, find the first active membership
    if not org_id:
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
            org_id = current_user.organization_id

    # If still no org, redirect to onboarding
    if not org_id:
        return redirect(url_for('onboarding.organization'))

    # User has an organization - go to dashboard
    # (invited users should go to the org they were invited to, even if onboarding incomplete)
    return redirect(url_for('main.dashboard'))


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])


def _password_reset_token(user: User) -> str:
    return _serializer().dumps({'user_id': user.id, 'email': user.email}, salt=_PASSWORD_RESET_TOKEN_SALT)


def _org_invite_token(user: User) -> str:
    return _serializer().dumps({'user_id': user.id, 'email': user.email}, salt=_ORG_INVITE_TOKEN_SALT)


def _verify_timed_token(token: str, *, salt: str, max_age_seconds: int) -> dict | None:
    try:
        data = _serializer().loads(token, salt=salt, max_age=max_age_seconds)
        if not isinstance(data, dict):
            return None
        if 'user_id' not in data or 'email' not in data:
            return None
        return data
    except (BadSignature, SignatureExpired):
        return None


def _verify_password_reset_token(token: str, max_age_seconds: int = 3600) -> dict | None:
    return _verify_timed_token(token, salt=_PASSWORD_RESET_TOKEN_SALT, max_age_seconds=max_age_seconds)


def _verify_reset_or_invite_token(token: str) -> dict | None:
    # Accept both org invites (24h default) and password reset links (1h default).
    # Try invite first so users clicking invite links get the longer TTL.
    data = _verify_timed_token(
        token,
        salt=_ORG_INVITE_TOKEN_SALT,
        max_age_seconds=_org_invite_token_ttl_seconds(),
    )
    if data:
        return data
    return _verify_timed_token(
        token,
        salt=_PASSWORD_RESET_TOKEN_SALT,
        max_age_seconds=_password_reset_token_ttl_seconds(),
    )


def _mail_configured() -> bool:
    return bool(current_app.config.get('MAIL_SERVER') and current_app.config.get('MAIL_DEFAULT_SENDER'))


def _email_verification_required() -> bool:
    # Require email verification for password-based signups.
    # OAuth sign-ins can mark the email as verified by the provider.
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

    subject = 'Verify your email - Cenaris'
    
    # Plain text version
    body = (
        f'Welcome to Cenaris!\n\n'
        f'Thank you for creating an account. Please verify your email address ({user.email}) to get started.\n\n'
        f'Verify link: {verify_url}\n\n'
        'If you didn\'t create this account, you can safely ignore this email.\n\n'
        '---\n'
        'Cenaris Compliance Management System'
    )
    
    # HTML version with template
    try:
        from flask import render_template
        html = render_template('email/verify_email.html', user=user, verify_url=verify_url)
    except Exception:
        html = None
    
    try:
        if html:
            _send_email_html(user.email, subject, body, html)
        else:
            _send_email(user.email, subject, body)
    except Exception:
        current_app.logger.exception('Failed to send verification email to %s', user.email)
        raise


def _send_email(to_email: str, subject: str, body: str) -> None:
    """Send email via SendGrid API (fast, no SMTP port issues) or SMTP fallback."""
    sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
    
    # Try SendGrid Web API first (more reliable on cloud hosts that block SMTP)
    if sendgrid_api_key:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail as SGMail
            
            sender = current_app.config.get('MAIL_DEFAULT_SENDER')
            message = SGMail(
                from_email=sender,
                to_emails=to_email,
                subject=subject,
                plain_text_content=body,
            )
            
            sg = SendGridAPIClient(sendgrid_api_key)
            response = sg.send(message)
            
            if response.status_code not in (200, 201, 202):
                raise Exception(f'SendGrid API returned {response.status_code}')
            
            current_app.logger.info('Email sent via SendGrid API to %s', to_email)
            return
        except Exception as e:
            current_app.logger.warning('SendGrid API failed (%s), falling back to SMTP', e)
    
    # Fallback to SMTP (Flask-Mail)
    msg = Message(
        subject=subject,
        recipients=[to_email],
        body=body,
    )
    mail.send(msg)


def _turnstile_enabled() -> bool:
    return bool(current_app.config.get('TURNSTILE_SECRET_KEY'))


def _verify_turnstile() -> tuple[bool, str]:
    """Verify Cloudflare Turnstile CAPTCHA.

    Returns (ok, reason) where reason is one of:
    - 'disabled': Turnstile not configured
    - 'missing': no token was submitted (user didn't complete widget or script blocked)
    - 'invalid': Turnstile rejected the token
    - 'error': verification request failed
    - 'ok': verified
    """
    if not _turnstile_enabled():
        return True, 'disabled'

    token = (request.form.get('cf-turnstile-response') or '').strip()
    if not token:
        return False, 'missing'

    secret = current_app.config.get('TURNSTILE_SECRET_KEY')
    try:
        # NOTE: Do not send remoteip.
        # In proxied deployments (Render/NGINX), request.remote_addr may not be the real client IP.
        # Turnstile verification works without it and avoids false negatives.
        resp = requests.post(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            data={
                'secret': secret,
                'response': token,
            },
            timeout=5,
        )
        data = resp.json() if resp is not None else {}
        ok = bool(data.get('success'))
        if ok:
            return True, 'ok'

        # Helpful diagnostics in server logs (do NOT log the token).
        error_codes = data.get('error-codes') or data.get('error_codes')
        hostname = data.get('hostname')
        current_app.logger.warning('Turnstile rejected token: error_codes=%s hostname=%s', error_codes, hostname)
        return False, 'invalid'
    except Exception:
        current_app.logger.exception('Turnstile verification request failed')
        return False, 'error'


def _client_ip() -> str | None:
    # Honor proxy headers when present (common in Render/NGINX), but only take the first hop.
    xff = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    if xff:
        return xff
    return request.remote_addr


def _log_login_event(
    *,
    email: str | None,
    user: User | None,
    provider: str,
    success: bool,
    reason: str | None = None,
) -> None:
    try:
        evt = LoginEvent(
            user_id=int(user.id) if user else None,
            email=(email or (user.email if user else None) or None),
            provider=(provider or 'password')[:20],
            success=bool(success),
            reason=(reason or None)[:80] if (reason or '').strip() else None,
            ip_address=(_client_ip() or None),
            user_agent=((request.user_agent.string or '')[:255] or None),
        )
        db.session.add(evt)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed to log login event')


def _ip_block_status(now: datetime) -> tuple[bool, datetime | None]:
    ip = _client_ip()
    if not ip:
        return False, None
    rec = SuspiciousIP.query.filter_by(ip_address=ip).first()
    if rec and rec.blocked_until:
        blocked_until = rec.blocked_until
        # SQLite often returns naive datetimes; normalize to UTC-aware.
        if getattr(blocked_until, 'tzinfo', None) is None:
            blocked_until = blocked_until.replace(tzinfo=timezone.utc)
        if blocked_until > now:
            return True, blocked_until
    return False, None


def _register_ip_failure(now: datetime) -> None:
    ip = _client_ip()
    if not ip:
        return

    try:
        rec = SuspiciousIP.query.filter_by(ip_address=ip).first()
        if not rec:
            rec = SuspiciousIP(ip_address=ip)
            db.session.add(rec)

        rec.last_seen_at = now

        window_started_at = rec.window_started_at
        if window_started_at and getattr(window_started_at, 'tzinfo', None) is None:
            window_started_at = window_started_at.replace(tzinfo=timezone.utc)

        if not window_started_at or int((now - window_started_at).total_seconds()) > _SUSPICIOUS_IP_WINDOW_SECONDS:
            rec.window_started_at = now
            rec.failure_count = 0

        rec.failure_count = int(rec.failure_count or 0) + 1
        if int(rec.failure_count or 0) >= _SUSPICIOUS_IP_FAILURE_THRESHOLD:
            rec.blocked_until = now.replace(microsecond=0) + timedelta(seconds=_SUSPICIOUS_IP_BLOCK_SECONDS)

        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception('Failed to update suspicious IP tracking')


def _clear_ip_failures_on_success(now: datetime) -> None:
    ip = _client_ip()
    if not ip:
        return
    try:
        rec = SuspiciousIP.query.filter_by(ip_address=ip).first()
        if not rec:
            return
        rec.last_seen_at = now
        rec.window_started_at = now
        rec.failure_count = 0
        rec.blocked_until = None
        db.session.commit()
    except Exception:
        db.session.rollback()


def _send_password_reset_email(user: User, reset_url: str) -> None:
    # If mail isn't configured (common for local dev), we still provide the link via logs.
    if not _mail_configured():
        current_app.logger.warning('MAIL not configured; password reset URL: %s', reset_url)
        return

    from flask import render_template

    subject = 'Reset your password'
    body = render_template('email/password_reset.txt', user=user, reset_url=reset_url)
    html = render_template('email/password_reset.html', user=user, reset_url=reset_url)
    
    try:
        _send_email_html(user.email, subject, body, html)
    except Exception:
        current_app.logger.exception('Failed to send password reset email to %s', user.email)
        raise


def _send_email_html(to_email: str, subject: str, body: str, html: str) -> None:
    """Send HTML email via SendGrid API or SMTP fallback."""
    sendgrid_api_key = os.environ.get('SENDGRID_API_KEY')
    
    if sendgrid_api_key:
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail as SGMail
            
            sender = current_app.config.get('MAIL_DEFAULT_SENDER')
            message = SGMail(
                from_email=sender,
                to_emails=to_email,
                subject=subject,
                plain_text_content=body,
                html_content=html,
            )
            
            sg = SendGridAPIClient(sendgrid_api_key)
            response = sg.send(message)
            
            if response.status_code not in (200, 201, 202):
                raise Exception(f'SendGrid API returned {response.status_code}')
            
            current_app.logger.info('HTML email sent via SendGrid API to %s', to_email)
            return
        except Exception as e:
            current_app.logger.warning('SendGrid API failed (%s), falling back to SMTP', e)
    
    # Fallback to SMTP
    msg = Message(
        subject=subject,
        recipients=[to_email],
        body=body,
        html=html,
    )
    mail.send(msg)

@bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
@limiter.limit('100 per hour')
def login():
    """User login route."""
    # If user is already logged in, check if they want to switch accounts
    if current_user.is_authenticated:
        # If 'force_logout' param is present, logout first to allow account switching
        if request.args.get('force_logout') == '1':
            logout_user()
            session.clear()
            flash('You have been logged out. Please sign in with a different account.', 'info')
            return redirect(url_for('auth.login'))
        return _after_login_redirect()
    
    form = LoginForm()
    
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        password = form.password.data

        now = datetime.now(timezone.utc)

        # Suspicious IP detection (DB-backed, survives restarts)
        is_blocked, blocked_until = _ip_block_status(now)
        if is_blocked:
            _log_login_event(email=email, user=None, provider='password', success=False, reason='ip_blocked')
            flash('Login temporarily unavailable. Please try again later.', 'error')
            return render_template('auth/login.html', form=form, title='Sign In')

        user = User.query.filter_by(email=email).first()

        # Account lockout (only enforced for known users, but response is generic).
        if user and user.locked_until:
            locked_until = user.locked_until
            if getattr(locked_until, 'tzinfo', None) is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until > now:
                _log_login_event(email=email, user=user, provider='password', success=False, reason='locked')
                flash('Login temporarily unavailable. Please try again later.', 'error')
                return render_template('auth/login.html', form=form, title='Sign In')
        
        if user and user.check_password(password) and user.is_active:
            if _email_verification_required() and not getattr(user, 'email_verified', False):
                _log_login_event(email=email, user=user, provider='password', success=False, reason='email_not_verified')
                flash('Please verify your email before signing in. You can request a new verification link below.', 'warning')
                return redirect(url_for('auth.verify_email_request', email=email))

            # Successful login resets lockout counters.
            try:
                user.failed_login_count = 0
                user.last_failed_login_at = None
                user.locked_until = None
                user.last_login_at = now
                db.session.commit()
            except Exception:
                db.session.rollback()

            # Regenerate session to reduce session fixation risk.
            try:
                session.clear()
            except Exception:
                pass

            login_user(user, remember=form.remember_me.data)
            try:
                session['auth_time'] = int(now.timestamp())
                session['session_version'] = getattr(user, 'session_version', 1)
                session['last_activity_time'] = now.timestamp()
            except Exception:
                pass
            _clear_ip_failures_on_success(now)
            _log_login_event(email=email, user=user, provider='password', success=True)
            
            # Log security event
            log_security_event('LOGIN_SUCCESS', details={'email': email, 'provider': 'password'})
            
            flash('Welcome back! You have been successfully signed in.', 'success')
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            return _after_login_redirect()
        else:
            _log_login_event(email=email, user=user, provider='password', success=False, reason='invalid_credentials')
            _register_ip_failure(now)

            # Update lockout counters only for existing active users.
            if user and user.is_active:
                try:
                    if user.last_failed_login_at:
                        last_failed_login_at = user.last_failed_login_at
                        if getattr(last_failed_login_at, 'tzinfo', None) is None:
                            last_failed_login_at = last_failed_login_at.replace(tzinfo=timezone.utc)
                        age = int((now - last_failed_login_at).total_seconds())
                        if age > _FAILED_LOGIN_WINDOW_SECONDS:
                            user.failed_login_count = 0
                    user.failed_login_count = int(user.failed_login_count or 0) + 1
                    user.last_failed_login_at = now
                    if int(user.failed_login_count or 0) >= _LOGIN_LOCKOUT_THRESHOLD:
                        user.locked_until = now.replace(microsecond=0) + timedelta(seconds=_LOGIN_LOCKOUT_SECONDS)
                    db.session.commit()
                except Exception:
                    db.session.rollback()

            flash('Invalid email address or password. Please try again.', 'error')
    
    return render_template('auth/login.html', form=form, title='Sign In')

@bp.route('/signup', methods=['GET', 'POST'])
def signup():
    """User registration route (generic), followed by onboarding wizard."""
    # If user is already logged in, check if they want to switch accounts
    if current_user.is_authenticated:
        # If 'force_logout' param is present, logout first to allow account switching
        if request.args.get('force_logout') == '1':
            logout_user()
            session.clear()
            flash('You have been logged out. Please create a new account.', 'info')
            return redirect(url_for('auth.signup'))
        return _after_login_redirect()
    
    form = RegisterForm()
    
    if form.validate_on_submit():
        ok, reason = _verify_turnstile()
        if not ok:
            flash('Please complete the CAPTCHA.' if reason == 'missing' else 'CAPTCHA verification failed. Please try again.', 'error')
            return render_template('auth/signup.html', form=form, title='Create Account')

        org_name = form.organization_name.data.strip()
        abn = (form.abn.data or '').strip()
        acn = (form.acn.data or '').strip() or None
        first_name = (form.first_name.data or '').strip()
        last_name = (form.last_name.data or '').strip()
        title = (form.title.data or '').strip()
        mobile_number = (form.mobile_number.data or '').strip() or None
        work_phone = (form.work_phone.data or '').strip() or None
        time_zone = (form.time_zone.data or '').strip() or 'Australia/Sydney'
        email = form.email.data.lower().strip()
        password = form.password.data
        
        try:
            organization = Organization(
                name=org_name,
                abn=abn,
                acn=acn,
                contact_email=email,
            )
            db.session.add(organization)
            db.session.flush()

            # Ensure org-scoped RBAC roles exist. If RBAC tables are missing in the target DB
            # (common when switching from SQLite tests to a fresh Postgres DB), fail fast with
            # a clear migration hint.
            org_admin_role_id = None
            try:
                from app.services.rbac import ensure_rbac_seeded_for_org, BUILTIN_ROLE_KEYS
                from app.models import RBACRole

                ensure_rbac_seeded_for_org(int(organization.id))
                db.session.flush()
                org_admin_role = (
                    RBACRole.query
                    .filter_by(organization_id=int(organization.id), name=BUILTIN_ROLE_KEYS.ORG_ADMIN)
                    .first()
                )
                org_admin_role_id = int(org_admin_role.id) if org_admin_role else None
            except Exception as e:
                db.session.rollback()
                current_app.logger.exception('RBAC seeding failed during signup')
                flash(_schema_upgrade_hint() if _looks_like_schema_mismatch(e) else 'Account creation failed. Please try again.', 'error')
                return render_template('auth/signup.html', form=form, title='Create Account')

            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                title=title,
                mobile_number=mobile_number,
                work_phone=work_phone,
                time_zone=time_zone,
                full_name=(f"{first_name} {last_name}").strip(),
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
                role_id=org_admin_role_id,
                is_active=True,
            )
            db.session.add(membership)
            db.session.commit()
            
            # Refresh the user object to ensure all relationships are loaded
            db.session.refresh(user)
            db.session.refresh(organization)

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
            current_app.logger.exception('Signup failed')

            # Provide a more actionable message in DEBUG so issues like missing
            # migrations / DB connectivity are obvious during setup.
            try:
                from sqlalchemy.exc import IntegrityError  # type: ignore

                if isinstance(e, IntegrityError):
                    flash('That email address is already registered. Please sign in instead.', 'error')
                    return render_template('auth/signup.html', form=form, title='Create Account')
            except Exception:
                pass

            if current_app.debug:
                msg = (str(e) or type(e).__name__).strip()
                msg = (msg[:200] + '…') if len(msg) > 200 else msg
                flash(f'Account creation failed: {msg}', 'error')
            else:
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

        ok, reason = _verify_turnstile()
        if not ok:
            flash('Please complete the CAPTCHA.' if reason == 'missing' else 'CAPTCHA verification failed. Please try again.', 'error')
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

    data = _verify_reset_or_invite_token(token)
    if not data:
        flash('This reset link is invalid or has expired. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))

    user = db.session.get(User, int(data['user_id']))
    if not user or (user.email or '').lower().strip() != (data.get('email') or '').lower().strip():
        flash('This reset link is invalid. Please request a new one.', 'error')
        return redirect(url_for('auth.forgot_password'))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        had_password = bool(user.password_hash)
        user.set_password(form.password.data)
        try:
            # If this was the user's first password set (common for org invites),
            # mark any pending invites as accepted and activate membership.
            if not had_password:
                try:
                    now = datetime.now(timezone.utc)
                    pending_memberships = (
                        OrganizationMembership.query
                        .filter_by(user_id=int(user.id))
                        .filter(OrganizationMembership.invited_at.isnot(None))
                        .filter(OrganizationMembership.invite_accepted_at.is_(None))
                        .all()
                    )
                    for m in pending_memberships:
                        m.invite_accepted_at = now
                        m.is_active = True  # Activate membership when user accepts invite
                except Exception:
                    current_app.logger.exception('Failed to mark invite accepted')

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
    # If user is already logged in, check if they want to switch accounts
    if current_user.is_authenticated:
        # If 'force_logout' param is present, logout first to allow OAuth account switching
        if request.args.get('force_logout') == '1':
            logout_user()
            session.clear()
            flash('You have been logged out. Please sign in with a different account.', 'info')
            return redirect(url_for('auth.oauth_authorize', provider=provider))
        return _after_login_redirect()

    client = oauth.create_client(provider)
    if not client:
        flash(f'{provider.title()} sign-in is not configured yet.', 'error')
        return redirect(url_for('auth.login'))

    # Work around TLS/proxy issues on some Windows networks by forcing TLS 1.2
    # for Google endpoints (metadata + token exchange).
    if (provider or '').lower() == 'google':
        try:
            from app.auth.oauth_transport import apply_google_tls12_workaround

            apply_google_tls12_workaround(client)
        except Exception:
            pass

    redirect_uri = url_for('auth.oauth_callback', provider=provider, _external=True)

    # Microsoft Entra validates redirect_uri strictly (scheme/host/path must match exactly).
    # When running behind a reverse proxy, forwarded headers may be missing/misread and Flask
    # can generate an http:// redirect_uri even though the site is accessed via https://.
    # Force https for *public* hosts (non-localhost) to avoid Entra redirect_uri mismatch.
    if (provider or '').lower() == 'microsoft':
        try:
            if isinstance(redirect_uri, str) and redirect_uri.startswith('http://'):
                from urllib.parse import urlsplit

                host = (urlsplit(redirect_uri).hostname or '').strip().lower()
                is_local = host in {'localhost', '127.0.0.1', '0.0.0.0'}
                if not is_local:
                    redirect_uri = url_for('auth.oauth_callback', provider=provider, _external=True, _scheme='https')
        except Exception:
            pass

    if (provider or '').lower() == 'microsoft':
        try:
            ms_client_id = (current_app.config.get('MICROSOFT_CLIENT_ID') or '').strip()
            ms_client_id_hint = (ms_client_id[-6:] if ms_client_id else '')
            current_app.logger.info(
                '[OAUTH] microsoft authorize_redirect redirect_uri=%s | scheme=%s host=%s xf_proto=%s xf_host=%s xf_port=%s client_id_endswith=%s',
                redirect_uri,
                request.scheme,
                request.host,
                request.headers.get('X-Forwarded-Proto'),
                request.headers.get('X-Forwarded-Host'),
                request.headers.get('X-Forwarded-Port'),
                ms_client_id_hint,
            )
        except Exception:
            pass
    elif current_app.debug:
        current_app.logger.info('[OAUTH DEBUG] Provider=%s RedirectURI=%s', provider, redirect_uri)
    try:
        return client.authorize_redirect(redirect_uri)
    except Exception as e:
        # Most common local failure: TLS inspection / proxy / blocked outbound.
        try:
            import requests  # type: ignore

            ssl_error = getattr(requests.exceptions, 'SSLError', None)
            conn_error = getattr(requests.exceptions, 'ConnectionError', None)
            if (ssl_error and isinstance(e, ssl_error)) or (conn_error and isinstance(e, conn_error)):
                current_app.logger.exception('OAuth authorize_redirect failed due to network/SSL error')
                flash(
                    'Google sign-in failed due to an SSL/TLS or network error reaching Google. '
                    'This is usually caused by a proxy/firewall/antivirus HTTPS scanning. '
                    'Try a different network (mobile hotspot) or disable HTTPS inspection. '
                    'If needed, set OAUTH_FORCE_TLS12=1 (default) and restart the app.',
                    'error',
                )
                return redirect(url_for('auth.login'))
        except Exception:
            pass

        current_app.logger.exception('OAuth authorize_redirect failed')
        flash('OAuth sign-in failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))


@bp.route('/oauth/<provider>/callback')
def oauth_callback(provider):
    if current_user.is_authenticated:
        return _after_login_redirect()

    client = oauth.create_client(provider)
    if not client:
        flash(f'{provider.title()} sign-in is not configured yet.', 'error')
        return redirect(url_for('auth.login'))

    # Ensure Google client uses the same transport settings in the callback as in the
    # initial authorize redirect. Without this, token exchange can fail on some
    # Windows/corporate networks.
    if (provider or '').lower() == 'google':
        try:
            from app.auth.oauth_transport import apply_google_tls12_workaround

            apply_google_tls12_workaround(client)
        except Exception:
            pass

    # Authlib raises specific exception types for common callback issues (state mismatch,
    # provider errors). Import them best-effort so we can show actionable guidance.
    try:  # pragma: no cover
        from authlib.integrations.base_client.errors import MismatchingStateError, OAuthError  # type: ignore
    except Exception:  # pragma: no cover
        MismatchingStateError = None  # type: ignore
        OAuthError = None  # type: ignore

    try:
        # Authlib validates OIDC `iss` during `authorize_access_token()` when an `id_token` is present.
        # Microsoft Entra ID's multi-tenant discovery (e.g. `common`) can yield an issuer that doesn't
        # match the token's tenant-specific `iss`. Disable `iss` validation for Microsoft only.
        if (provider or '').lower() == 'microsoft':
            token = client.authorize_access_token(claims_options={'iss': {'essential': False}})
        else:
            token = client.authorize_access_token()
    except Exception as e:
        if MismatchingStateError is not None and isinstance(e, MismatchingStateError):
            current_app.logger.warning('OAuth callback failed: mismatching_state (host=%s)', request.host, exc_info=True)
            flash(
                'OAuth sign-in failed because your login session could not be validated (state mismatch). '
                'This commonly happens when switching between localhost and 127.0.0.1. '
                'Retry using the same hostname you started with (recommended: http://localhost).',
                'error',
            )
            return redirect(url_for('auth.login'))

        if OAuthError is not None and isinstance(e, OAuthError):
            desc = (getattr(e, 'description', None) or str(e) or '').strip()
            current_app.logger.warning('OAuth token exchange failed: %s', desc or type(e).__name__, exc_info=True)
            if current_app.debug and desc:
                flash(f'OAuth sign-in failed: {desc}', 'error')
            else:
                flash('OAuth sign-in failed. Please try again.', 'error')
            return redirect(url_for('auth.login'))

        # Most common local failure: TLS interception / proxy / missing certs on Windows.
        try:
            import requests  # type: ignore

            if isinstance(e, getattr(requests.exceptions, 'SSLError', Exception)):
                current_app.logger.exception('OAuth token exchange failed due to SSL/TLS error')
                flash(
                    'OAuth sign-in failed due to an SSL/TLS connection error. '
                    'This is usually a network/proxy or certificate issue. '
                    'If you are on Windows/corporate network, install `truststore` and restart, '
                    'or try a different network (e.g., home hotspot).',
                    'error',
                )
                return redirect(url_for('auth.login'))
        except Exception:
            pass

        current_app.logger.exception('OAuth token exchange failed')
        if current_app.debug:
            msg = (str(e) or type(e).__name__).strip()
            # Keep it short to avoid flooding the UI.
            msg = (msg[:160] + '…') if len(msg) > 160 else msg
            flash(f'OAuth sign-in failed: {msg}', 'error')
        else:
            flash('OAuth sign-in failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))
    # Authlib puts parsed userinfo into token['userinfo'] when an id_token is present.
    userinfo = token.get('userinfo')
    if not userinfo:
        # Best-effort fallback to userinfo endpoint.
        try:
            userinfo = client.userinfo()
        except Exception:
            userinfo = None

    email = (userinfo.get('email') if isinstance(userinfo, dict) else None) or ''
    email = email.lower().strip()

    # Microsoft sometimes returns preferred_username instead of email.
    if not email and isinstance(userinfo, dict):
        email = (userinfo.get('preferred_username') or '').lower().strip()

    if not email:
        flash('Unable to read your email from the provider.', 'error')
        return redirect(url_for('auth.login'))

    full_name = (userinfo.get('name') if isinstance(userinfo, dict) else None) or None
    picture_url = (userinfo.get('picture') if isinstance(userinfo, dict) else None) or None

    user = User.query.filter_by(email=email).first()
    if not user:
        # For OAuth sign-ups, create a placeholder organization + membership,
        # then require email verification (same as password signup).
        try:
            name_parts = (full_name or '').split() if full_name else []
            first_name = name_parts[0] if len(name_parts) > 0 else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

            email_domain = email.split('@')[-1] if '@' in email else ''
            org_base = (email_domain.split('.')[0] if email_domain else 'My').strip() or 'My'
            org_name = f"{org_base.title()} Organization"

            organization = Organization(
                name=org_name,
                contact_email=email,
            )
            db.session.add(organization)
            db.session.flush()

            # Ensure org-scoped RBAC roles exist.
            org_admin_role_id = None
            try:
                from app.services.rbac import ensure_rbac_seeded_for_org, BUILTIN_ROLE_KEYS
                from app.models import RBACRole

                ensure_rbac_seeded_for_org(int(organization.id))
                db.session.flush()
                org_admin_role = (
                    RBACRole.query
                    .filter_by(organization_id=int(organization.id), name=BUILTIN_ROLE_KEYS.ORG_ADMIN)
                    .first()
                )
                org_admin_role_id = int(org_admin_role.id) if org_admin_role else None
            except Exception as e:
                db.session.rollback()
                current_app.logger.exception('RBAC seeding failed during OAuth signup')
                flash(_schema_upgrade_hint() if _looks_like_schema_mismatch(e) else 'Failed to create your account. Please try again.', 'error')
                return redirect(url_for('auth.login'))

            user = User(
                email=email,
                first_name=first_name,
                last_name=last_name,
                full_name=full_name,
                organization_id=organization.id,
                email_verified=True,
                terms_accepted_at=None,
            )
            db.session.add(user)
            db.session.flush()

            membership = OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role='Admin',
                role_id=org_admin_role_id,
                is_active=True,
            )
            db.session.add(membership)
            db.session.commit()

            db.session.refresh(user)
            db.session.refresh(organization)
        except Exception:
            db.session.rollback()
            flash('Failed to create your account. Please try again.', 'error')
            return redirect(url_for('auth.login'))
    else:
        # Legacy safety: ensure an OAuth user has an org + active membership.
        try:
            needs_org = not getattr(user, 'organization_id', None)
            has_active_membership = bool(
                OrganizationMembership.query.filter_by(user_id=int(user.id), is_active=True).first()
            )

            if needs_org or not has_active_membership:
                organization = None
                created_org = False
                if getattr(user, 'organization_id', None):
                    organization = db.session.get(Organization, int(user.organization_id))

                if not organization:
                    email_domain = email.split('@')[-1] if '@' in email else ''
                    org_base = (email_domain.split('.')[0] if email_domain else 'My').strip() or 'My'
                    organization = Organization(
                        name=f"{org_base.title()} Organization",
                        contact_email=email,
                    )
                    db.session.add(organization)
                    db.session.flush()
                    user.organization_id = int(organization.id)
                    created_org = True

                if not has_active_membership:
                    legacy_role = (getattr(user, 'role', None) or '').strip().lower()
                    membership_role = 'Admin' if (created_org or legacy_role == 'admin') else 'User'

                    role_id = None
                    try:
                        from app.services.rbac import ensure_rbac_seeded_for_org

                        ensure_rbac_seeded_for_org(int(organization.id))
                        db.session.flush()
                    except Exception as e:
                        db.session.rollback()
                        current_app.logger.exception('RBAC seeding failed during OAuth legacy safety')
                        flash(_schema_upgrade_hint() if _looks_like_schema_mismatch(e) else 'OAuth sign-in failed. Please try again.', 'error')
                        return redirect(url_for('auth.login'))

                    try:
                        # Prefer mapping via seeded roles.
                        from app.models import RBACRole
                        from app.services.rbac import BUILTIN_ROLE_KEYS

                        target = BUILTIN_ROLE_KEYS.ORG_ADMIN if membership_role == 'Admin' else BUILTIN_ROLE_KEYS.MEMBER
                        r = RBACRole.query.filter_by(organization_id=int(organization.id), name=target).first()
                        role_id = int(r.id) if r else None
                    except Exception:
                        role_id = None

                    membership = OrganizationMembership(
                        organization_id=int(organization.id),
                        user_id=int(user.id),
                        role=membership_role,
                        role_id=role_id,
                        is_active=True,
                    )
                    db.session.add(membership)

                db.session.commit()
        except Exception:
            db.session.rollback()

    if not user.is_active:
        flash('This account is disabled. Please contact support.', 'error')
        return redirect(url_for('auth.login'))

    # Successful OAuth sign-in implies the provider has verified control of the email.
    # This allows Google/Microsoft users to proceed without an additional email-verification step.
    try:
        if not getattr(user, 'email_verified', False):
            user.email_verified = True
            db.session.commit()
    except Exception:
        db.session.rollback()

    if _email_verification_required() and not getattr(user, 'email_verified', False):
        # Avoid re-sending repeatedly within the cooldown.
        last_sent_at = int(session.get('verify_email_last_sent_at') or 0)
        should_send = (_now_ts() - last_sent_at) >= _RESEND_VERIFY_EMAIL_COOLDOWN_SECONDS

        if should_send:
            token = _email_verify_token(user)
            verify_url = url_for('auth.verify_email', token=token, _external=True)
            try:
                _send_email_verification_email(user, verify_url)
            except Exception:
                current_app.logger.exception('Failed to send verification email')

            session['pending_verification_email'] = user.email
            session['verify_email_last_sent_at'] = _now_ts()

        if not _mail_configured():
            flash('Email is required to continue. MAIL is not configured; check the server logs for the verification link.', 'warning')

        _log_login_event(email=email, user=user, provider=(provider or 'oauth'), success=False, reason='email_not_verified')
        flash('Please verify your email to continue.', 'warning')
        return redirect(url_for('auth.verify_email_request', email=email))

    # Regenerate session to reduce session fixation risk.
    try:
        session.clear()
    except Exception:
        pass

    login_user(user)
    # Treat a successful OAuth sign-in as an accepted invite for any invited memberships.
    # Also update last_login_at so the user is not misclassified as "pending" elsewhere.
    try:
        now = datetime.now(timezone.utc)
        user.last_login_at = now
        user.failed_login_count = 0
        user.last_failed_login_at = None
        user.locked_until = None

        pending_memberships = (
            OrganizationMembership.query
            .filter_by(user_id=int(user.id))
            .filter(OrganizationMembership.invited_at.isnot(None))
            .filter(OrganizationMembership.invite_accepted_at.is_(None))
            .filter(OrganizationMembership.invite_revoked_at.is_(None))
            .all()
        )
        for m in pending_memberships:
            m.invite_accepted_at = now
            m.is_active = True  # Activate membership when OAuth user accepts invite

        db.session.commit()
        try:
            _clear_ip_failures_on_success(now)
        except Exception:
            pass
    except Exception:
        db.session.rollback()
    try:
        now_ts = datetime.now(timezone.utc).timestamp()
        session['auth_time'] = int(now_ts)
        session['session_version'] = getattr(user, 'session_version', 1)
        session['last_activity_time'] = now_ts
        # Store OAuth profile picture URL (Google provides `picture`).
        # This is only used for display on the profile page (not as a branding/logo).
        if picture_url and isinstance(picture_url, str):
            session['oauth_profile_picture_url'] = picture_url
            session['oauth_provider'] = provider
    except Exception:
        pass
    _log_login_event(email=email, user=user, provider=(provider or 'oauth'), success=True)
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

    user = db.session.get(User, int(data['user_id']))
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
        ok, reason = _verify_turnstile()
        if not ok:
            flash('Please complete the CAPTCHA.' if reason == 'missing' else 'CAPTCHA verification failed. Please try again.', 'error')
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


@bp.route('/verify-email/status')
def verify_email_status():
    """Lightweight status endpoint for the verify-email page.

    Used to auto-advance the UI once the current (authenticated) user becomes verified
    after clicking the email link in another tab.
    """
    if not current_user.is_authenticated:
        return jsonify({'authenticated': False, 'verified': False, 'next_url': None})

    verified = bool(getattr(current_user, 'email_verified', False))
    # When verified, advance to wherever _after_login_redirect would send them
    next_url = url_for('main.dashboard') if verified else None
    return jsonify({'authenticated': True, 'verified': verified, 'next_url': next_url})

@bp.route('/logout', methods=['POST'])
def logout():
    """User logout route."""
    if current_user.is_authenticated:
        # Log security event before logout
        log_security_event('LOGOUT', details={'email': current_user.email})
        
        logout_user()
        session.clear()
        flash('You have been successfully signed out.', 'info')
    return redirect(url_for('main.index'))


@bp.route('/logout-all-devices', methods=['POST'])
@limiter.limit('5 per minute')
def logout_all_devices():
    """Logout from all devices by incrementing session_version."""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    try:
        # Increment session version - invalidates all other sessions
        current_user.session_version = int(getattr(current_user, 'session_version', 1)) + 1
        db.session.commit()
        
        # Logout current session
        logout_user()
        session.clear()
        
        flash('You have been logged out from all devices. Please sign in again.', 'success')
    except Exception:
        db.session.rollback()
        flash('Failed to logout from all devices. Please try again.', 'error')
    
    return redirect(url_for('auth.login'))