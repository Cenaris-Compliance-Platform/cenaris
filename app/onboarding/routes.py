from flask import render_template, redirect, url_for, flash, request, make_response, abort
from flask_login import login_required, current_user

from app.onboarding import bp
from app.onboarding.forms import OnboardingOrganizationForm, OnboardingLogoForm, OnboardingThemeForm
from app import db
from app.models import Organization, User


def _safe_theme(value: str | None) -> str:
    theme = (value or 'light').strip().lower()
    return theme if theme in {'light', 'dark'} else 'light'


def _cookie_secure() -> bool:
    host = (request.host or '').lower()
    return not (host.startswith('127.0.0.1') or host.startswith('localhost'))


@bp.route('/organization', methods=['GET', 'POST'])
@login_required
def organization():
    # If already onboarded, skip ahead.
    if getattr(current_user, 'organization_id', None):
        return redirect(url_for('onboarding.logo'))

    form = OnboardingOrganizationForm()

    if form.validate_on_submit():
        org_name = form.organization_name.data.strip()
        email = (current_user.email or '').strip().lower()

        organization = Organization(
            name=org_name,
            abn=(form.abn.data or '').strip() or None,
            address=(form.address.data or '').strip() or None,
            contact_email=((form.contact_email.data or '').strip().lower() or email or None),
        )
        db.session.add(organization)
        db.session.flush()

        user: User = User.query.get(int(current_user.id))
        if not user:
            db.session.rollback()
            abort(401)

        user.organization_id = organization.id
        # First org creator becomes Admin
        user.role = 'Admin'

        try:
            db.session.commit()
            return redirect(url_for('onboarding.logo'))
        except Exception:
            db.session.rollback()
            flash('Failed to create organization. Please try again.', 'error')

    return render_template('onboarding/organization.html', title='Setup Organization', form=form)


@bp.route('/logo', methods=['GET', 'POST'])
@login_required
def logo():
    org_id = getattr(current_user, 'organization_id', None)
    if not org_id:
        return redirect(url_for('onboarding.organization'))

    organization = Organization.query.get(org_id)
    if not organization:
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
    org_id = getattr(current_user, 'organization_id', None)
    if not org_id:
        return redirect(url_for('onboarding.organization'))

    form = OnboardingThemeForm()

    if request.method == 'POST' and request.form.get('skip') == '1':
        flash('You can change the theme later in Organization Settings.', 'info')
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
        return response

    return render_template('onboarding/theme.html', title='Choose Theme', form=form)
