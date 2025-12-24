"""Quick smoke test for Organization Settings split forms.

Creates an in-memory app/db, inserts an org + admin member, then exercises
GET /organization/settings and two separate POST submissions (profile + billing).

Run: python _smoke_org_settings.py
"""

import os
import uuid


def main() -> None:
    # IMPORTANT: config.py reads env vars at import time.
    # Force a local SQLite DB before importing the Flask app so we don't hang on Postgres.
    os.environ.setdefault('TEST_DATABASE_URL', 'sqlite:///smoke_org_settings.db')

    from app import create_app, db
    from app.models import Organization, OrganizationMembership, User
    from flask import jsonify
    from flask_login import current_user
    from flask_login import FlaskLoginClient

    print('SMOKE: starting', flush=True)
    app = create_app('testing')
    # Use Flask-Login's testing client so we can authenticate without posting to /auth/login.
    app.test_client_class = FlaskLoginClient

    @app.get('/_smoke/whoami')
    def _smoke_whoami():
        org_id = getattr(current_user, 'organization_id', None)
        uid = getattr(current_user, 'id', None)
        membership_exists = False
        if uid and org_id:
            membership_exists = bool(
                OrganizationMembership.query.filter_by(
                    user_id=int(uid), organization_id=int(org_id), is_active=True
                ).first()
            )
        return jsonify(
            {
                'authenticated': bool(getattr(current_user, 'is_authenticated', False)),
                'user_id': uid,
                'organization_id': org_id,
                'membership_exists': membership_exists,
            }
        )

    print(
        f"SMOKE: config WTF_CSRF_ENABLED={app.config.get('WTF_CSRF_ENABLED')!r} "
        f"TESTING={app.config.get('TESTING')!r} SQLALCHEMY_DATABASE_URI={app.config.get('SQLALCHEMY_DATABASE_URI')!r}",
        flush=True,
    )

    print('SMOKE: app created', flush=True)

    with app.app_context():
        print('SMOKE: app_context entered', flush=True)
        db.create_all()

        from datetime import datetime, timezone

        # Uses whatever DB your dev config points at (often Postgres). Keep it
        # safe/idempotent by using unique rows and cleaning up afterward.
        suffix = uuid.uuid4().hex[:10]
        email = f"smoke_admin_{suffix}@example.com"

        org = None
        user = None
        membership = None

        try:
            print('SMOKE: creating org/user/membership', flush=True)
            # Make the org onboarding-complete so main blueprint doesn't redirect
            # /organization/settings to the onboarding wizard.
            org = Organization(
                name=f"Smoke Test Org {suffix}",
                abn='123',
                organization_type='Test',
                contact_email='contact@example.com',
                address='1 Test St',
                industry='Test',
                operates_in_australia=True,
            )
            db.session.add(org)
            db.session.commit()

            user = User(email=email, email_verified=True, is_active=True, organization_id=org.id)
            user.set_password('password')
            db.session.add(user)
            db.session.commit()

            org.declarations_accepted_at = datetime.now(timezone.utc)
            org.declarations_accepted_by_user_id = int(user.id)
            org.data_processing_ack_at = datetime.now(timezone.utc)
            org.data_processing_ack_by_user_id = int(user.id)
            db.session.commit()

            membership = OrganizationMembership(
                organization_id=org.id,
                user_id=user.id,
                role='Admin',
                is_active=True,
            )
            db.session.add(membership)
            db.session.commit()

            # Sanity-check the DB user record before going through /auth/login.
            db_user = User.query.filter_by(email=email.lower().strip()).first()
            print(f"SMOKE: db_user_found={bool(db_user)}", flush=True)
            if db_user:
                print(
                    f"SMOKE: db_user_is_active={db_user.is_active} "
                    f"email_verified={getattr(db_user, 'email_verified', None)} "
                    f"organization_id={getattr(db_user, 'organization_id', None)}",
                    flush=True,
                )
                print(f"SMOKE: password_check={db_user.check_password('password')}", flush=True)
                mcount = OrganizationMembership.query.filter_by(user_id=int(db_user.id), is_active=True).count()
                print(f"SMOKE: active_memberships_for_user={mcount}", flush=True)

            print('SMOKE: session primed; hitting GET', flush=True)

            client = app.test_client(user=user)

            who = client.get('/_smoke/whoami')
            try:
                print(f"SMOKE: whoami={who.get_json()}", flush=True)
            except Exception:
                print(f"SMOKE: whoami_status={who.status_code}", flush=True)

            resp = client.get('/organization/settings')
            if resp.status_code != 200:
                loc = resp.headers.get('Location')
                raise AssertionError(
                    f"GET /organization/settings expected 200, got {resp.status_code}; Location={loc}"
                )

            print('SMOKE: POST profile', flush=True)

            # Validate the form in isolation to understand why the handler might not redirect.
            from app.main.forms import OrganizationProfileSettingsForm
            with app.test_request_context(
                '/organization/settings',
                method='POST',
                data={
                    'form_name': 'profile',
                    'name': f"Smoke Test Org Updated {suffix}",
                    'abn': '123',
                    'address': '1 Test St',
                    'contact_email': 'contact@example.com',
                },
            ):
                f = OrganizationProfileSettingsForm()
                ok = f.validate()
                print(
                    f"SMOKE: profile_form.validate={ok} errors={f.errors} "
                    f"WTF_CSRF_ENABLED={app.config.get('WTF_CSRF_ENABLED')!r}",
                    flush=True,
                )

            resp = client.post(
                '/organization/settings',
                data={
                    'form_name': 'profile',
                    'name': f"Smoke Test Org Updated {suffix}",
                    'abn': '123',
                    'address': '1 Test St',
                    'contact_email': 'contact@example.com',
                },
                follow_redirects=False,
            )
            assert resp.status_code in (302, 303), f"POST profile expected redirect, got {resp.status_code}"

            print('SMOKE: POST billing', flush=True)

            resp = client.post(
                '/organization/settings',
                data={
                    'form_name': 'billing',
                    'billing_email': 'billing@example.com',
                    'billing_address': 'Accounts Payable, 1 Test St',
                },
                follow_redirects=False,
            )
            assert resp.status_code in (302, 303), f"POST billing expected redirect, got {resp.status_code}"

            print('SMOKE: POST invalid billing', flush=True)

            resp = client.post(
                '/organization/settings',
                data={
                    'form_name': 'billing',
                    'billing_email': 'billing2@example.com',
                    'billing_address': '',
                },
                follow_redirects=False,
            )
            assert resp.status_code == 200, f"POST invalid billing expected 200, got {resp.status_code}"
        finally:
            try:
                print('SMOKE: cleanup', flush=True)
                if membership is not None:
                    db.session.delete(membership)
                if user is not None:
                    db.session.delete(user)
                if org is not None:
                    db.session.delete(org)
                db.session.commit()
            except Exception:
                db.session.rollback()

    print('OK: organization settings split-form smoke test passed')


if __name__ == '__main__':
    main()
