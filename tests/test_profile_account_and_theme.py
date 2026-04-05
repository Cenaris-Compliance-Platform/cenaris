from __future__ import annotations


def test_onboarding_theme_post_redirects_to_dashboard_and_sets_cookie(client, app, seed_org_user):
    from tests.conftest import login

    resp = login(client)
    assert resp.status_code in {302, 303}

    post_resp = client.post('/onboarding/theme', data={'theme': 'dark'}, follow_redirects=False)

    assert post_resp.status_code in {302, 303}
    location = post_resp.headers.get('Location') or ''
    assert '/dashboard' in location
    set_cookie = post_resp.headers.get('Set-Cookie') or ''
    assert 'theme=dark' in set_cookie


def test_profile_delete_account_requires_delete_keyword(client, app, seed_org_user):
    from app.models import User
    from tests.conftest import login

    resp = login(client)
    assert resp.status_code in {302, 303}

    delete_resp = client.post(
        '/profile/delete-account',
        data={'confirm_text': 'NOPE', 'password': 'Passw0rd1'},
        follow_redirects=True,
    )

    assert delete_resp.status_code == 200
    assert b'Type DELETE to confirm account deletion.' in delete_resp.data

    with app.app_context():
        user = User.query.filter_by(email='user@example.com').first()
        assert user is not None
        assert bool(user.is_active) is True


def test_profile_delete_account_deactivates_user_when_not_last_admin(client, app, db_session, seed_org_user):
    from app.models import OrganizationMembership, User
    from tests.conftest import login

    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        second_admin = User(email='second-admin@example.com', email_verified=True, is_active=True)
        second_admin.set_password('Passw0rd1')
        second_admin.organization_id = int(org_id)
        db_session.session.add(second_admin)
        db_session.session.flush()

        db_session.session.add(
            OrganizationMembership(
                organization_id=int(org_id),
                user_id=int(second_admin.id),
                role='Admin',
                is_active=True,
            )
        )
        db_session.session.commit()

    resp = login(client)
    assert resp.status_code in {302, 303}

    delete_resp = client.post(
        '/profile/delete-account',
        data={'confirm_text': 'DELETE', 'password': 'Passw0rd1'},
        follow_redirects=False,
    )

    assert delete_resp.status_code in {302, 303}
    assert (delete_resp.headers.get('Location') or '').endswith('/')

    with app.app_context():
        user = db_session.session.get(User, int(user_id))
        assert user is not None
        assert bool(user.is_active) is False
        assert (user.email or '').startswith(f'deleted+{int(user_id)}+')
        assert (user.password_hash or '') == ''

        active_memberships = OrganizationMembership.query.filter_by(user_id=int(user_id), is_active=True).count()
        assert int(active_memberships) == 0


def test_profile_delete_account_allows_sso_style_account_without_password(client, app, db_session, seed_org_user):
    from app.models import OrganizationMembership, User

    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        second_admin = User(email='sso-second-admin@example.com', email_verified=True, is_active=True)
        second_admin.set_password('Passw0rd1')
        second_admin.organization_id = int(org_id)
        db_session.session.add(second_admin)
        db_session.session.flush()
        db_session.session.add(
            OrganizationMembership(
                organization_id=int(org_id),
                user_id=int(second_admin.id),
                role='Admin',
                is_active=True,
            )
        )
        # Simulate OAuth-only account by removing local password hash.
        primary_user = db_session.session.get(User, int(user_id))
        primary_user.password_hash = None
        db_session.session.commit()

    # Password login should not be required for OAuth-style users in this delete flow test.
    with client.session_transaction() as sess:
        sess['_user_id'] = str(int(user_id))
        sess['_fresh'] = True

    delete_resp = client.post(
        '/profile/delete-account',
        data={'confirm_text': 'DELETE', 'password': ''},
        follow_redirects=False,
    )

    assert delete_resp.status_code in {302, 303}
    assert (delete_resp.headers.get('Location') or '').endswith('/')

    with app.app_context():
        user = db_session.session.get(User, int(user_id))
        assert user is not None
        assert bool(user.is_active) is False


def test_signup_can_reuse_email_after_account_deletion(client, app, db_session, seed_org_user):
    from app.models import OrganizationMembership, User
    from tests.conftest import login

    org_id, user_id, _membership_id = seed_org_user
    deleted_email = 'user@example.com'

    with app.app_context():
        second_admin = User(email='reuse-second-admin@example.com', email_verified=True, is_active=True)
        second_admin.set_password('Passw0rd1')
        second_admin.organization_id = int(org_id)
        db_session.session.add(second_admin)
        db_session.session.flush()
        db_session.session.add(
            OrganizationMembership(
                organization_id=int(org_id),
                user_id=int(second_admin.id),
                role='Admin',
                is_active=True,
            )
        )
        db_session.session.commit()

    resp = login(client)
    assert resp.status_code in {302, 303}

    delete_resp = client.post(
        '/profile/delete-account',
        data={'confirm_text': 'DELETE', 'password': 'Passw0rd1'},
        follow_redirects=False,
    )
    assert delete_resp.status_code in {302, 303}

    # Turnstile may be enabled by environment settings; disable for deterministic signup test behavior.
    old_turnstile_secret = app.config.get('TURNSTILE_SECRET_KEY')
    app.config['TURNSTILE_SECRET_KEY'] = ''
    try:
        signup_resp = client.post(
            '/auth/signup',
            data={
                'organization_name': 'Recreated Org',
                'abn': '12345678901',
                'acn': '',
                'first_name': 'New',
                'last_name': 'Owner',
                'title': 'Director',
                'mobile_number': '0400000000',
                'work_phone': '',
                'time_zone': 'Australia/Sydney',
                'email': deleted_email,
                'password': 'Passw0rd1',
                'password_confirm': 'Passw0rd1',
                'accept_terms': 'y',
            },
            follow_redirects=False,
        )
    finally:
        app.config['TURNSTILE_SECRET_KEY'] = old_turnstile_secret

    assert signup_resp.status_code in {302, 303}
    location = signup_resp.headers.get('Location') or ''
    assert '/onboarding/' in location or '/auth/verify-email' in location
