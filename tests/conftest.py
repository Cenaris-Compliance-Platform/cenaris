import os
from datetime import datetime, timezone

import pytest


@pytest.fixture()
def app(tmp_path):
    # Configure a per-test SQLite DB file so state persists across requests.
    db_path = tmp_path / "test_app.sqlite"
    db_uri = f"sqlite:///{db_path.as_posix()}"

    os.environ["TEST_DATABASE_URL"] = db_uri
    os.environ["FLASK_CONFIG"] = "testing"

    from app import create_app, db

    flask_app = create_app("testing")
    flask_app.config.update(
        SQLALCHEMY_DATABASE_URI=db_uri,
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        WTF_CSRF_CHECK_DEFAULT=False,
    )

    with flask_app.app_context():
        db.drop_all()
        db.create_all()

    yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db_session(app):
    from app import db

    with app.app_context():
        yield db


def _complete_org(org):
    # Satisfy Organization.onboarding_complete()
    org.abn = org.abn or "12345678901"
    org.organization_type = org.organization_type or "Company"
    org.contact_email = org.contact_email or "contact@example.com"
    org.address = org.address or "1 Test St"
    org.industry = org.industry or "Other"
    org.operates_in_australia = True
    org.declarations_accepted_at = datetime.now(timezone.utc)
    org.data_processing_ack_at = datetime.now(timezone.utc)
    return org


@pytest.fixture()
def seed_org_user(app, db_session):
    """Create an onboarding-complete org + verified user + membership."""
    from app.models import Organization, OrganizationMembership, User

    with app.app_context():
        org = _complete_org(Organization(name="Org A"))
        user = User(email="user@example.com", email_verified=True, is_active=True)
        user.set_password("Passw0rd1")
        user.organization_id = 1  # updated after flush

        db_session.session.add(org)
        db_session.session.flush()
        user.organization_id = org.id
        db_session.session.add(user)
        db_session.session.flush()

        m = OrganizationMembership(organization_id=org.id, user_id=user.id, role="Admin", is_active=True)
        db_session.session.add(m)

        # Seed RBAC and attach org-admin role_id for this membership.
        try:
            from app.services.rbac import ensure_rbac_seeded_for_org, BUILTIN_ROLE_KEYS
            from app.models import RBACRole

            ensure_rbac_seeded_for_org(int(org.id))
            db_session.session.flush()
            admin_role = (
                RBACRole.query
                .filter_by(organization_id=int(org.id), name=BUILTIN_ROLE_KEYS.ORG_ADMIN)
                .first()
            )
            m.role_id = int(admin_role.id) if admin_role else None
        except Exception:
            m.role_id = None

        db_session.session.commit()

        return int(org.id), int(user.id), int(m.id)


def login(client, email="user@example.com", password="Passw0rd1", remote_addr="127.0.0.1"):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password, "remember_me": "y"},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": remote_addr} if remote_addr else None,
    )
