from datetime import datetime, timezone

from flask import render_template, redirect, url_for, flash, request, make_response, abort, current_app
from flask_login import login_required, current_user

from flask_mail import Message

from app.onboarding import bp
from app.onboarding.forms import OnboardingOrganizationForm, OnboardingBillingForm, OnboardingLogoForm, OnboardingThemeForm
from app import db, mail
from app.models import Organization, User, OrganizationMembership


def _require_verified():
    # Block onboarding until the account's email is verified.
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

    subject = 'Welcome to Cenaris'
    
    # Plain text version
    body = (
        'Welcome to Cenaris! Your organization setup is complete.\n\n'
        f'Dashboard: {dashboard_url}\n\n'
        'You can now upload documents and start managing your compliance evidence.\n\n'
        'Get started by:\n'
        '- Uploading compliance documents\n'
        '- Inviting team members to collaborate\n'
        '- Generating compliance reports\n'
        '- Tracking your compliance status\n'
    )
    
    # HTML version with template
    try:
        from flask import render_template
        html = render_template('email/welcome.html', user=user, dashboard_url=dashboard_url)
    except Exception:
        html = None
    
    try:
        from app.auth.routes import _send_email, _send_email_html
        if html:
            _send_email_html(user.email, subject, body, html)
        else:
            _send_email(user.email, subject, body)
    except Exception:
        current_app.logger.exception('Failed to send welcome email to %s', user.email)
        raise
    return True


def _maybe_send_welcome_email(user_id: int) -> None:
    user: User | None = db.session.get(User, int(user_id))
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
        # Fallback: Create a placeholder org and membership if somehow missing
        # (This should rarely happen now that OAuth creates orgs properly)
        try:
            org = Organization(
                name='',
                contact_email=(getattr(current_user, 'email', '') or '').strip().lower() or None,
            )
            db.session.add(org)
            db.session.flush()

            # Ensure org-scoped RBAC roles exist.
            try:
                from app.services.rbac import ensure_rbac_seeded_for_org, BUILTIN_ROLE_KEYS
                from app.models import RBACRole

                ensure_rbac_seeded_for_org(int(org.id))
                db.session.flush()
                org_admin_role = (
                    RBACRole.query
                    .filter_by(organization_id=int(org.id), name=BUILTIN_ROLE_KEYS.ORG_ADMIN)
                    .first()
                )
                org_admin_role_id = int(org_admin_role.id) if org_admin_role else None
            except Exception:
                org_admin_role_id = None

            user = db.session.get(User, int(current_user.id))
            if not user:
                db.session.rollback()
                abort(401)
            user.organization_id = int(org.id)
            
            # Create the membership record
            membership = OrganizationMembership(
                organization_id=org.id,
                user_id=user.id,
                role='Admin',
                role_id=org_admin_role_id,
                is_active=True,
            )
            db.session.add(membership)
            db.session.commit()
            org_id = int(org.id)
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Failed creating organization during onboarding')
            flash('Unable to start onboarding. Please try again.', 'error')
            return redirect(url_for('main.index'))

    organization = db.session.get(Organization, int(org_id))
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
        form.acn.data = getattr(organization, 'acn', None)
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
        
        # Pre-check terms acceptance if user already accepted (e.g., via signup form)
        form.accept_terms.data = bool(getattr(current_user, 'terms_accepted_at', None))

    if form.validate_on_submit():
        try:
            organization.name = form.organization_name.data.strip()
            organization.trading_name = (form.trading_name.data or '').strip() or None
            organization.abn = (form.abn.data or '').strip() or None
            organization.acn = (form.acn.data or '').strip() or None
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
            
            # Record terms acceptance if not already done (for OAuth users)
            if not getattr(current_user, 'terms_accepted_at', None):
                user = db.session.get(User, int(current_user.id))
                user.terms_accepted_at = now
            
            db.session.commit()
            return redirect(url_for('onboarding.billing'))
        except Exception:
            db.session.rollback()
            flash('Failed to create organisation. Please try again.', 'error')

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

    organization = db.session.get(Organization, int(org_id))
    if not organization:
        abort(404)
    
    # Ensure organization details are complete before proceeding to billing
    if not organization.core_details_complete():
        flash('Please complete your organization details first.', 'info')
        return redirect(url_for('onboarding.organization'))

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

    organization = db.session.get(Organization, int(org_id))
    if not organization:
        return redirect(url_for('onboarding.organization'))

    # Ensure core organization details are complete before logo upload
    if not organization.core_details_complete():
        flash('Please complete your organization details first.', 'info')
        return redirect(url_for('onboarding.organization'))

    form = OnboardingLogoForm()

    if request.method == 'POST' and request.form.get('skip') == '1':
        return redirect(url_for('onboarding.theme'))

    if form.validate_on_submit():
        logo_file = form.logo.data
        if not logo_file or not getattr(logo_file, 'filename', ''):
            flash('No logo file selected. You can skip this step or upload a logo.', 'info')
            return redirect(url_for('onboarding.theme'))

        # Use unified logo upload function from main routes
        from app.main.routes import _update_organization_logo
        success, message = _update_organization_logo(organization, logo_file)
        
        if not success:
            flash(message, 'error')
            return render_template('onboarding/logo.html', title='Upload Logo', form=form, organization=organization)

        try:
            db.session.commit()
            # Refresh the organization object to ensure logo is in session
            db.session.refresh(organization)
            flash(message, 'success')
            return redirect(url_for('onboarding.theme'))
        except Exception as e:
            db.session.rollback()
            # Log the actual error for debugging
            import logging
            logging.error(f"Failed to save logo during onboarding: {e}")
            flash('Failed to save logo. Please try again.', 'error')
            return render_template('onboarding/logo.html', title='Upload Logo', form=form, organization=organization)
    elif request.method == 'POST':
        # Form validation failed - show errors
        if form.logo.errors:
            for error in form.logo.errors:
                flash(f'Logo upload error: {error}', 'error')
        else:
            flash('Please check the form and try again.', 'error')

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
    
    organization = db.session.get(Organization, int(org_id))
    if not organization:
        return redirect(url_for('onboarding.organization'))
    
    # Ensure onboarding steps are complete before allowing theme selection
    if not organization.onboarding_complete():
        flash('Please complete your organisation setup first.', 'info')
        return redirect(url_for('onboarding.organization'))

    form = OnboardingThemeForm()

    if request.method == 'POST' and request.form.get('skip') == '1':
        flash('You can change the theme later in Organisation Settings.', 'info')
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
    
    # Log validation errors for debugging
    if request.method == 'POST' and form.errors:
        current_app.logger.warning(f"Theme form validation failed: {form.errors}")
        flash('Please select a theme to continue.', 'error')

    return render_template('onboarding/theme.html', title='Choose Theme', form=form)
