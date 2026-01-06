from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import login


def test_org_switch_between_multiple_orgs(app, client, db_session, seed_org_user):
    from app.models import Organization, OrganizationMembership

    _org1_id, user_id, _m1_id = seed_org_user
    remote_addr = "10.0.0.10"

    with app.app_context():
        org2 = Organization(name="Org B")
        # Make org2 onboarding-complete too
        org2.abn = "98765432109"
        org2.organization_type = "Company"
        org2.contact_email = "contact2@example.com"
        org2.address = "2 Test St"
        org2.industry = "Other"
        org2.operates_in_australia = True
        org2.declarations_accepted_at = datetime.now(timezone.utc)
        org2.data_processing_ack_at = datetime.now(timezone.utc)

        db_session.session.add(org2)
        db_session.session.flush()

        db_session.session.add(
            OrganizationMembership(organization_id=org2.id, user_id=int(user_id), role="User", is_active=True)
        )
        db_session.session.commit()

        org2_id = int(org2.id)

    resp = login(client, remote_addr=remote_addr)
    assert resp.status_code == 302

    # Switch active org
    resp2 = client.post(
        "/org/switch",
        data={"organization_id": str(org2_id)},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": remote_addr},
    )
    assert resp2.status_code == 302

    with app.app_context():
        from app.models import User

        refreshed = db_session.session.get(User, int(user_id))
        assert int(refreshed.organization_id) == int(org2_id)


def test_pending_invites_resend_cooldown_and_revoke(app, client, db_session, seed_org_user):
    from app.models import OrganizationMembership, User

    org_id, _admin_id, _m_id = seed_org_user
    remote_addr = "10.0.0.11"

    assert login(client, remote_addr=remote_addr).status_code == 302

    with app.app_context():
        from app.services.rbac import ensure_rbac_seeded_for_org, BUILTIN_ROLE_KEYS
        from app.models import RBACRole

        ensure_rbac_seeded_for_org(int(org_id))
        db_session.session.commit()
        member_role = (
            RBACRole.query
            .filter_by(organization_id=int(org_id), name=BUILTIN_ROLE_KEYS.MEMBER)
            .first()
        )
        member_role_id = str(int(member_role.id)) if member_role else ''

    # Invite a new user
    resp = client.post(
        "/org/admin/invite",
        data={
            "email": "invited@example.com",
            "role": member_role_id,
            "new_department_name": "General",
            "new_department_color": "primary",
        },
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": remote_addr},
    )
    assert resp.status_code == 302

    with app.app_context():
        invited_user = User.query.filter_by(email="invited@example.com").first()
        assert invited_user is not None
        assert invited_user.password_hash is None

        membership = OrganizationMembership.query.filter_by(user_id=invited_user.id).first()
        assert membership is not None
        assert membership.invited_at is not None
        assert membership.invite_last_sent_at is not None
        assert int(membership.invite_send_count or 0) == 1

        membership_id = membership.id

    # Resend immediately (cooldown should prevent increment)
    resp2 = client.post(
        "/org/admin/invite/resend",
        data={"membership_id": str(membership_id)},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": remote_addr},
    )
    assert resp2.status_code == 302

    with app.app_context():
        membership = db_session.session.get(OrganizationMembership, int(membership_id))
        assert int(membership.invite_send_count or 0) == 1

        # Move last_sent back beyond cooldown and resend should increment
        membership.invite_last_sent_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        db_session.session.commit()

    resp3 = client.post(
        "/org/admin/invite/resend",
        data={"membership_id": str(membership_id)},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": remote_addr},
    )
    assert resp3.status_code == 302

    with app.app_context():
        membership = db_session.session.get(OrganizationMembership, int(membership_id))
        assert int(membership.invite_send_count or 0) == 2

    # Revoke invite
    resp4 = client.post(
        "/org/admin/invite/revoke",
        data={"membership_id": str(membership_id)},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": remote_addr},
    )
    assert resp4.status_code == 302

    with app.app_context():
        membership = db_session.session.get(OrganizationMembership, int(membership_id))
        assert membership.is_active is False
        assert membership.invite_revoked_at is not None


def test_login_activity_logged(app, client, db_session, seed_org_user):
    from app.models import LoginEvent

    _org_id, _user_id, _m_id = seed_org_user

    # Failed login
    resp1 = client.post(
        "/auth/login",
        data={"email": "user@example.com", "password": "wrong"},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": "10.0.0.12"},
    )
    assert resp1.status_code in {200, 302}

    # Successful login
    resp2 = login(client, remote_addr="10.0.0.12")
    assert resp2.status_code == 302

    with app.app_context():
        evts = LoginEvent.query.order_by(LoginEvent.created_at.desc()).limit(5).all()
        assert any(e.provider == "password" and e.success is False for e in evts)
        assert any(e.provider == "password" and e.success is True for e in evts)


def test_cannot_demote_last_admin_role(app, client, db_session, seed_org_user):
    from app.models import OrganizationMembership

    org_id, _user_id, membership_id = seed_org_user
    remote_addr = "10.0.0.99"

    assert login(client, remote_addr=remote_addr).status_code == 302

    with app.app_context():
        from app.services.rbac import ensure_rbac_seeded_for_org, BUILTIN_ROLE_KEYS
        from app.models import RBACRole

        ensure_rbac_seeded_for_org(int(org_id))
        db_session.session.commit()

        admin_role = (
            RBACRole.query
            .filter_by(organization_id=int(org_id), name=BUILTIN_ROLE_KEYS.ORG_ADMIN)
            .first()
        )
        member_role = (
            RBACRole.query
            .filter_by(organization_id=int(org_id), name=BUILTIN_ROLE_KEYS.MEMBER)
            .first()
        )
        assert admin_role is not None
        assert member_role is not None

        m = db_session.session.get(OrganizationMembership, int(membership_id))
        assert m is not None
        original_role_id = int(m.role_id) if m.role_id else None

    # Attempt to demote the only admin to Member.
    resp = client.post(
        "/org/admin/members/role",
        data={"membership_id": str(membership_id), "role_id": str(int(member_role.id))},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": remote_addr},
    )
    assert resp.status_code == 302

    with app.app_context():
        m2 = db_session.session.get(OrganizationMembership, int(membership_id))
        assert m2 is not None
        assert int(m2.role_id) == int(original_role_id)


def test_rate_limiting_on_login(app, client):
    # Send many login attempts quickly (non-existent users avoids user lockout side-effects)
    last = None
    for i in range(11):
        last = client.post(
            "/auth/login",
            data={"email": f"nope{i}@example.com", "password": "bad"},
            follow_redirects=False,
            environ_base={"REMOTE_ADDR": "10.0.0.13"},
        )

    assert last is not None
    assert last.status_code == 429


def test_account_lockout_after_failures(app, client, db_session, seed_org_user):
    from app.models import User

    _org_id, _user_id, _m_id = seed_org_user
    remote_addr = "10.0.0.14"

    # 5 failed attempts should lock the account
    for _ in range(5):
        r = client.post(
            "/auth/login",
            data={"email": "user@example.com", "password": "wrong"},
            follow_redirects=False,
            environ_base={"REMOTE_ADDR": remote_addr},
        )
        assert r.status_code in {200, 302}

    with app.app_context():
        u = User.query.filter_by(email="user@example.com").first()
        assert u.locked_until is not None
        locked_until = u.locked_until
        if getattr(locked_until, 'tzinfo', None) is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        assert locked_until > datetime.now(timezone.utc)

    # Correct password should still be blocked while locked
    r2 = login(client, remote_addr=remote_addr)
    assert r2.status_code == 200


def test_ip_based_suspicious_blocking(app, client, monkeypatch):
    from app.auth import routes as auth_routes
    from app.models import SuspiciousIP

    # Lower thresholds so we can test without fighting the rate limiter.
    monkeypatch.setattr(auth_routes, "_SUSPICIOUS_IP_FAILURE_THRESHOLD", 3)
    monkeypatch.setattr(auth_routes, "_SUSPICIOUS_IP_BLOCK_SECONDS", 60)

    for i in range(3):
        r = client.post(
            "/auth/login",
            data={"email": f"bad{i}@example.com", "password": "bad"},
            follow_redirects=False,
            environ_base={"REMOTE_ADDR": "10.0.0.15"},
        )
        assert r.status_code in {200, 302}

    with app.app_context():
        ip = SuspiciousIP.query.first()
        assert ip is not None
        assert ip.blocked_until is not None

    # Next attempt should be blocked by IP rule
    r2 = client.post(
        "/auth/login",
        data={"email": "anything@example.com", "password": "bad"},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": "10.0.0.15"},
    )
    assert r2.status_code == 200


def test_force_logout_on_password_change(app, client, db_session, seed_org_user):
    import time
    from app.models import User

    _org_id, _user_id, _m_id = seed_org_user

    remote_addr = "10.0.0.16"

    assert login(client, remote_addr=remote_addr).status_code == 302

    # Wait to ensure password change timestamp is clearly after login
    time.sleep(2.5)

    with app.app_context():
        u = User.query.filter_by(email="user@example.com").first()
        u.set_password("Newpass1")
        db_session.session.commit()

    # Any subsequent request should redirect to login due to password change
    r = client.get("/dashboard", follow_redirects=False, environ_base={"REMOTE_ADDR": remote_addr})
    assert r.status_code == 302
    assert "/auth/login" in (r.headers.get("Location") or "")


def test_csrf_blocks_post_when_enabled(tmp_path):
    import os

    db_path = tmp_path / "csrf.sqlite"
    db_uri = f"sqlite:///{db_path.as_posix()}"

    os.environ["TEST_DATABASE_URL"] = db_uri
    os.environ["FLASK_CONFIG"] = "testing"

    from app import create_app, db

    app = create_app("testing")
    app.config.update(
        SQLALCHEMY_DATABASE_URI=db_uri,
        TESTING=True,
        WTF_CSRF_ENABLED=True,
        WTF_CSRF_CHECK_DEFAULT=True,
    )

    with app.app_context():
        db.drop_all()
        db.create_all()

    client = app.test_client()

    # POST without csrf_token should be rejected
    resp = client.post("/auth/logout", data={}, follow_redirects=False)
    assert resp.status_code == 400
