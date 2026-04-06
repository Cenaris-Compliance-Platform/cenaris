from datetime import datetime, timezone
from datetime import timedelta

from app import db
from app.models import (
    ComplianceFrameworkVersion,
    ComplianceRequirement,
    Organization,
    OrganizationMembership,
    OrganizationRequirementAssessment,
    RequirementEvidenceLink,
    Document,
    User,
)


def _create_org() -> Organization:
    org = Organization(
        name="Route Test Org",
        abn="12345678901",
        organization_type="Company",
        contact_email="route@example.com",
        address="1 Route St",
        industry="Other",
        operates_in_australia=True,
        declarations_accepted_at=datetime.now(timezone.utc),
        data_processing_ack_at=datetime.now(timezone.utc),
    )
    db.session.add(org)
    db.session.flush()
    return org


def _create_admin_user(org_id: int) -> User:
    user = User(email="route-user@example.com", email_verified=True, is_active=True, organization_id=org_id)
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


def _seed_requirements(org_id: int):
    framework = ComplianceFrameworkVersion(
        organization_id=org_id,
        jurisdiction="AU",
        scheme="NDIS",
        version_label="v2026.01",
        is_active=True,
    )
    db.session.add(framework)
    db.session.flush()

    req_green = ComplianceRequirement(
        framework_version_id=int(framework.id),
        requirement_id="REQ-GREEN",
        quality_indicator_code="QI.G",
        outcome_code="OUT.G",
        outcome_text="Green outcome",
    )
    req_red = ComplianceRequirement(
        framework_version_id=int(framework.id),
        requirement_id="REQ-RED",
        quality_indicator_code="QI.R",
        outcome_code="OUT.R",
        outcome_text="Red outcome",
    )
    db.session.add(req_green)
    db.session.add(req_red)
    db.session.flush()

    db.session.add(
        OrganizationRequirementAssessment(
            organization_id=org_id,
            requirement_id=int(req_green.id),
            computed_score=3,
            computed_flag="green",
            evidence_status_system="Present",
            evidence_status_implementation="Present",
            evidence_status_workforce="Present",
            evidence_status_participant="Present",
        )
    )
    db.session.add(
        OrganizationRequirementAssessment(
            organization_id=org_id,
            requirement_id=int(req_red.id),
            computed_score=1,
            computed_flag="red",
            evidence_status_system="Missing",
            evidence_status_implementation="Missing",
            evidence_status_workforce="Missing",
            evidence_status_participant="Missing",
        )
    )


def _login(client):
    resp = client.post(
        "/auth/login",
        data={"email": "route-user@example.com", "password": "Passw0rd1", "remember_me": "y"},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code in {302, 303}


def test_compliance_requirements_route_renders_seeded_data(client, app):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        _seed_requirements(int(org.id))
        db.session.commit()

    _login(client)
    response = client.get("/compliance-requirements")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "REQ-GREEN" in body
    assert "REQ-RED" in body


def test_compliance_requirements_route_applies_flag_filter(client, app):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        _seed_requirements(int(org.id))
        db.session.commit()

    _login(client)
    response = client.get("/compliance-requirements?status=red")

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "REQ-RED" in body
    assert "REQ-GREEN" not in body


def test_compliance_requirements_route_applies_bucket_filter(client, app):
    with app.app_context():
        org = _create_org()
        user = _create_admin_user(int(org.id))
        _seed_requirements(int(org.id))

        req_green = ComplianceRequirement.query.filter_by(requirement_id='REQ-GREEN').first()
        assert req_green is not None

        doc = Document(
            filename='policy.pdf',
            blob_name='org_1/policy.pdf',
            file_size=100,
            content_type='application/pdf',
            uploaded_by=int(user.id),
            organization_id=int(org.id),
            is_active=True,
        )
        db.session.add(doc)
        db.session.flush()

        db.session.add(
            RequirementEvidenceLink(
                organization_id=int(org.id),
                requirement_id=int(req_green.id),
                document_id=int(doc.id),
                evidence_bucket='system',
                linked_by_user_id=int(user.id),
            )
        )
        db.session.commit()

    _login(client)
    response = client.get('/compliance-requirements?bucket=system')

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'REQ-GREEN' in body


def test_compliance_requirements_route_applies_due_filter_unscheduled(client, app):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        _seed_requirements(int(org.id))
        db.session.commit()

    _login(client)
    response = client.get('/compliance-requirements?due=unscheduled')

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Awaiting first assessment' in body or 'No review schedule' in body


def test_compliance_requirements_route_renders_monthly_snapshot_and_queues(client, app):
    with app.app_context():
        org = _create_org()
        user = _create_admin_user(int(org.id))

        framework = ComplianceFrameworkVersion(
            organization_id=int(org.id),
            jurisdiction='AU',
            scheme='NDIS',
            version_label='v2026.02',
            is_active=True,
        )
        db.session.add(framework)
        db.session.flush()

        requirement = ComplianceRequirement(
            framework_version_id=int(framework.id),
            requirement_id='REQ-MONTHLY',
            module_name='Governance',
            review_frequency='monthly',
            evidence_owner_role='Practice Manager',
        )
        db.session.add(requirement)
        db.session.flush()

        assessed_at = datetime.now(timezone.utc) - timedelta(days=40)
        db.session.add(
            OrganizationRequirementAssessment(
                organization_id=int(org.id),
                requirement_id=int(requirement.id),
                computed_score=1,
                computed_flag='High risk gap',
                last_assessed_at=assessed_at,
            )
        )

        doc = Document(
            filename='monthly-policy.pdf',
            blob_name='org_1/monthly-policy.pdf',
            file_size=120,
            content_type='application/pdf',
            uploaded_by=int(user.id),
            organization_id=int(org.id),
            is_active=True,
            uploaded_at=datetime.now(timezone.utc) - timedelta(days=5),
        )
        db.session.add(doc)
        db.session.flush()

        db.session.add(
            RequirementEvidenceLink(
                organization_id=int(org.id),
                requirement_id=int(requirement.id),
                document_id=int(doc.id),
                evidence_bucket='system',
                linked_by_user_id=int(user.id),
                linked_at=datetime.now(timezone.utc) - timedelta(days=2),
            )
        )

        db.session.commit()

    _login(client)
    response = client.get('/compliance-requirements')

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Monthly Operations Snapshot' in body
    assert 'Owner Action Queue' in body
    assert 'Upcoming Review Queue' in body
    assert 'REQ-MONTHLY' in body
