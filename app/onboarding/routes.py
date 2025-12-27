from datetime import datetime, timezone

from flask import render_template, redirect, url_for, flash, request, make_response, abort, current_app
from flask_login import login_required, current_user

from flask_mail import Message

from app.onboarding import bp
from app.onboarding.forms import OnboardingOrganizationForm, OnboardingBillingForm, OnboardingLogoForm, OnboardingThemeForm
from app import db, mail
from app.models import Organization, User


def _require_verified():
    if getattr(current_user, 'email_verified', False):
        return None
    flash('Please verify your email to continue.', 'warning')
    return redirect(url_for('auth.verify_email_request', email=getattr(current_user, 'email', '')))


def _mail_configured() -> bool:
    return bool(current_app.config.get('MAIL_SERVER') and current_app.config.get('MAIL_DEFAULT_SENDER'))


def _send_welcome_email(user: User, dashboard_url: str) -> bool:
    if not _mail_configured():
        current_app.logger.warning(
            'MAIL not configured; welcome email skipped for %s (dashboard: %s)',
            user.email,
            dashboard_url,
        )
        return False

    msg = Message(
        subject='Welcome to CCM',
        recipients=[user.email],
        body=(
            'Welcome to CCM. Your organization setup is complete.\n\n'
            f'Dashboard: {dashboard_url}\n\n'
            'You can now upload documents and start managing your compliance evidence.\n'
        ),
    )
    mail.send(msg)
    return True


def _maybe_send_welcome_email(user_id: int) -> None:
    user: User | None = User.query.get(int(user_id))
    if not user or not getattr(user, 'email', None):
        return

    if getattr(user, 'welcome_email_sent_at', None):
        return

    dashboard_url = url_for('main.dashboard', _external=True)

    try:
        sent = _send_welcome_email(user, dashboard_url)
    except Exception:
        current_app.logger.exception('Failed to send welcome email')
        return

    if not sent:
        return

    user.welcome_email_sent_at = datetime.now(timezone.utc)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def _safe_theme(value: str | None) -> str:
    theme = (value or 'light').strip().lower()
    return theme if theme in {'light', 'dark'} else 'light'


def _cookie_secure() -> bool:
    host = (request.host or '').lower()
    return not (host.startswith('127.0.0.1') or host.startswith('localhost'))


@bp.route('/organization', methods=['GET', 'POST'])
@login_required
def organization():
    maybe = _require_verified()
    if maybe is not None:
        return maybe

    org_id = getattr(current_user, 'organization_id', None)
    if not org_id:
        # New users signing in via OAuth may not have an org yet.
        # Create a placeholder org and attach it so onboarding can continue.
        try:
            org = Organization(
                name='',
                contact_email=(getattr(current_user, 'email', '') or '').strip().lower() or None,
            )
            db.session.add(org)
            db.session.flush()  # assign org.id without requiring a separate transaction

            user = User.query.get(int(current_user.id))
            if not user:
                db.session.rollback()
                abort(401)
            user.organization_id = int(org.id)
            db.session.commit()
            org_id = int(org.id)
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Failed creating organization during onboarding')
            flash('Unable to start onboarding. Please try again.', 'error')
            return redirect(url_for('main.index'))

    organization = Organization.query.get(int(org_id))
    if not organization:
        abort(404)

    # If org core fields already captured, skip ahead.
    if (
        (organization.name or '').strip()
        and (organization.abn or '').strip()
        and (organization.organization_type or '').strip()
        and (organization.contact_email or '').strip()
        and (organization.address or '').strip()
        and (organization.industry or '').strip()
    ):
        return redirect(url_for('onboarding.billing'))

    form = OnboardingOrganizationForm()

    if request.method == 'GET':
        form.organization_name.data = organization.name
        form.trading_name.data = getattr(organization, 'trading_name', None)
        form.abn.data = organization.abn
        form.organization_type.data = getattr(organization, 'organization_type', '') or ''
        form.contact_email.data = organization.contact_email or (current_user.email or '').strip().lower()
        form.address.data = organization.address
        form.industry.data = getattr(organization, 'industry', '') or ''

        # Default acknowledgements to unchecked if not set yet.
        form.operates_in_australia.data = bool(organization.operates_in_australia) if organization.operates_in_australia is not None else False
        form.platform_disclaimer_ack.data = bool(getattr(organization, 'declarations_accepted_at', None))
        form.responsibility_ack.data = bool(getattr(organization, 'declarations_accepted_at', None))
        form.authority_to_upload_ack.data = bool(getattr(organization, 'declarations_accepted_at', None))
        form.data_processing_ack.data = bool(getattr(organization, 'data_processing_ack_at', None))

    if form.validate_on_submit():
        try:
            organization.name = form.organization_name.data.strip()
            organization.trading_name = (form.trading_name.data or '').strip() or None
            organization.abn = (form.abn.data or '').strip() or None
            organization.organization_type = (form.organization_type.data or '').strip() or None
            organization.industry = (form.industry.data or '').strip() or None
            organization.address = (form.address.data or '').strip() or None
            organization.contact_email = (form.contact_email.data or '').strip().lower() or None

            # Compliance + privacy acknowledgements.
            organization.operates_in_australia = True if form.operates_in_australia.data else False
            now = datetime.now(timezone.utc)
            organization.declarations_accepted_at = now
            organization.declarations_accepted_by_user_id = int(current_user.id)
            organization.data_processing_ack_at = now
            organization.data_processing_ack_by_user_id = int(current_user.id)
            db.session.commit()
            return redirect(url_for('onboarding.billing'))
        except Exception:
            db.session.rollback()
            flash('Failed to create organization. Please try again.', 'error')

    return render_template('onboarding/organization.html', title='Setup Organization', form=form)


@bp.route('/billing', methods=['GET', 'POST'])
@login_required
def billing():
    maybe = _require_verified()
    if maybe is not None:
        return maybe

    org_id = getattr(current_user, 'organization_id', None)
    if not org_id:
        return redirect(url_for('onboarding.organization'))

    organization = Organization.query.get(int(org_id))
    if not organization:
        abort(404)

    form = OnboardingBillingForm()

    if request.method == 'POST' and request.form.get('skip') == '1':
        flash('You can add billing details later. Uploads and reports may be restricted until billing is completed.', 'info')
        return redirect(url_for('onboarding.logo'))

    if request.method == 'GET':
        form.billing_email.data = getattr(organization, 'billing_email', None) or organization.contact_email
        form.billing_address.data = getattr(organization, 'billing_address', None) or organization.address

    if form.validate_on_submit():
        organization.billing_email = (form.billing_email.data or '').strip().lower() or None
        organization.billing_address = (form.billing_address.data or '').strip() or None
        try:
            db.session.commit()
            return redirect(url_for('onboarding.logo'))
        except Exception:
            db.session.rollback()
            flash('Failed to save billing details. Please try again.', 'error')

    return render_template('onboarding/billing.html', title='Billing Details', form=form)


@bp.route('/logo', methods=['GET', 'POST'])
@login_required
def logo():
    maybe = _require_verified()
    if maybe is not None:
        return maybe

    org_id = getattr(current_user, 'organization_id', None)
    if not org_id:
        return redirect(url_for('onboarding.organization'))

    organization = Organization.query.get(org_id)
    if not organization:
        return redirect(url_for('onboarding.organization'))

    # Ensure core + billing details exist before allowing logo step.
    if not organization.onboarding_complete():
        return redirect(url_for('onboarding.organization'))

    form = OnboardingLogoForm()

    if request.method == 'POST' and request.form.get('skip') == '1':
        return redirect(url_for('onboarding.theme'))

    if form.validate_on_submit():
        logo_file = form.logo.data
        if not logo_file or not getattr(logo_file, 'filename', ''):
            return redirect(url_for('onboarding.theme'))

        ext = (logo_file.filename.rsplit('.', 1)[-1] or '').lower()
        safe_ext = ext if ext in {'png', 'jpg', 'jpeg', 'webp'} else 'png'

        import uuid

        unique = uuid.uuid4().hex
        blob_name = f"organizations/{organization.id}/branding/logo_{unique}.{safe_ext}"
        content_type = getattr(logo_file, 'mimetype', None)

        from app.services.azure_storage_service import azure_storage_service

        data = logo_file.read()
        if not azure_storage_service.upload_blob(blob_name, data, content_type=content_type):
            flash('Logo upload failed. Check Azure Storage configuration.', 'error')
            return render_template('onboarding/logo.html', title='Upload Logo', form=form, organization=organization)

        organization.logo_blob_name = blob_name
        organization.logo_content_type = content_type

        try:
            db.session.commit()
            return redirect(url_for('onboarding.theme'))
        except Exception:
            db.session.rollback()
            flash('Failed to save logo. Please try again.', 'error')

    return render_template('onboarding/logo.html', title='Upload Logo', form=form, organization=organization)


@bp.route('/theme', methods=['GET', 'POST'])
@login_required
def theme():
    maybe = _require_verified()
    if maybe is not None:
        return maybe

    org_id = getattr(current_user, 'organization_id', None)
    if not org_id:
        return redirect(url_for('onboarding.organization'))

    form = OnboardingThemeForm()

    if request.method == 'POST' and request.form.get('skip') == '1':
        flash('You can change the theme later in Organization Settings.', 'info')
        _maybe_send_welcome_email(int(current_user.id))
        return redirect(url_for('main.dashboard'))

    if request.method == 'GET':
        form.theme.data = _safe_theme(request.cookies.get('theme', 'light'))

    if form.validate_on_submit():
        theme_value = _safe_theme(form.theme.data)
        response = make_response(redirect(url_for('main.dashboard')))
        response.set_cookie(
            'theme',
            theme_value,
            max_age=60 * 60 * 24 * 365,
            samesite='Lax',
            secure=_cookie_secure(),
        )
        flash('Setup complete. Welcome!', 'success')
        _maybe_send_welcome_email(int(current_user.id))
        return response

    return render_template('onboarding/theme.html', title='Choose Theme', form=form)
