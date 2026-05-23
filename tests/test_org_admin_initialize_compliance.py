from datetime import datetime, timezone

from app import db
from app.models import ComplianceRequirement, Organization, OrganizationMembership, User


def _create_org() -> Organization:
    org = Organization(
        name="Init Compliance Org",
        abn="12345678901",
        organization_type="Company",
        contact_email="init@example.com",
        address="1 Init Street",
        industry="Other",
        operates_in_australia=True,
        declarations_accepted_at=datetime.now(timezone.utc),
        data_processing_ack_at=datetime.now(timezone.utc),
    )
    db.session.add(org)
    db.session.flush()
    return org


def _create_admin_user(org_id: int) -> User:
    user = User(email="init-admin@example.com", email_verified=True, is_active=True, organization_id=org_id)
    user.set_password("Passw0rd1")
    db.session.add(user)
    db.session.flush()

    membership = OrganizationMembership(
        organization_id=org_id,
        user_id=int(user.id),
        role="Admin",
        is_active=True,
    )
    db.session.add(membership)
    db.session.flush()
    return user


def _login(client):
    resp = client.post(
        "/auth/login",
        data={"email": "init-admin@example.com", "password": "Passw0rd1", "remember_me": "y"},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code in {302, 303}


def test_org_admin_initialize_compliance_data(client, app):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        db.session.commit()
        org_id = int(org.id)

    _login(client)

    response = client.post(
        "/org/admin/compliance/initialize",
        data={"submit": "Initialize NDIS Data"},
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}

    with app.app_context():
        count = (
            ComplianceRequirement.query
            .join(ComplianceRequirement.framework_version)
            .filter_by(organization_id=org_id)
            .count()
        )
        assert count > 0
