from datetime import datetime, timezone

from app import db
from app.models import (
    ComplianceFrameworkVersion,
    ComplianceRequirement,
    Document,
    Organization,
    OrganizationMembership,
    OrganizationRequirementAssessment,
    RequirementEvidenceLink,
    User,
)


def _create_org() -> Organization:
    org = Organization(
        name="Evidence Link Org",
        abn="12345678901",
        organization_type="Company",
        contact_email="evidence@example.com",
        address="1 Evidence St",
        industry="Other",
        operates_in_australia=True,
        declarations_accepted_at=datetime.now(timezone.utc),
        data_processing_ack_at=datetime.now(timezone.utc),
    )
    db.session.add(org)
    db.session.flush()
    return org


def _create_admin_user(org_id: int) -> User:
    user = User(email="evidence-user@example.com", email_verified=True, is_active=True, organization_id=org_id)
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


def _seed_requirement(org_id: int) -> ComplianceRequirement:
    framework = ComplianceFrameworkVersion(
        organization_id=org_id,
        jurisdiction="AU",
        scheme="NDIS",
        version_label="v2026.02",
        is_active=True,
    )
    db.session.add(framework)
    db.session.flush()

    requirement = ComplianceRequirement(
        framework_version_id=int(framework.id),
        requirement_id="REQ-LINK-1",
        quality_indicator_code="QI-LINK",
        outcome_code="OUT-LINK",
        outcome_text="Requirement for evidence linking",
    )
    db.session.add(requirement)
    db.session.flush()
    return requirement


def _seed_document(org_id: int, user_id: int) -> Document:
    doc = Document(
        filename="policy.pdf",
        blob_name="org/policy.pdf",
        file_size=1234,
        content_type="application/pdf",
        uploaded_by=user_id,
        organization_id=org_id,
        is_active=True,
    )
    db.session.add(doc)
    db.session.flush()
    return doc


def _login(client):
    resp = client.post(
        "/auth/login",
        data={"email": "evidence-user@example.com", "password": "Passw0rd1", "remember_me": "y"},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code in {302, 303}


def test_requirement_detail_route_renders(client, app):
    with app.app_context():
        org = _create_org()
        user = _create_admin_user(int(org.id))
        requirement = _seed_requirement(int(org.id))
        _seed_document(int(org.id), int(user.id))
        db.session.commit()
        requirement_id = int(requirement.id)

    _login(client)
    resp = client.get(f"/compliance-requirements/{requirement_id}")

    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "REQ-LINK-1" in body
    assert "Link Evidence" in body
    assert "Explain with NDIS citations" in body


def test_requirement_link_and_unlink_evidence(client, app):
    with app.app_context():
        org = _create_org()
        user = _create_admin_user(int(org.id))
        requirement = _seed_requirement(int(org.id))
        document = _seed_document(int(org.id), int(user.id))
        db.session.commit()
        org_id = int(org.id)
        requirement_id = int(requirement.id)
        document_id = int(document.id)

    _login(client)

    link_resp = client.post(
        f"/compliance-requirements/{requirement_id}/link",
        data={
            "document_id": document_id,
            "evidence_bucket": "system",
            "rationale_note": "Mapped to policy section 2",
        },
        follow_redirects=False,
    )
    assert link_resp.status_code in {302, 303}

    with app.app_context():
        links = RequirementEvidenceLink.query.filter_by(
            organization_id=org_id,
            requirement_id=requirement_id,
            document_id=document_id,
            evidence_bucket="system",
        ).all()
        assert len(links) == 1
        link_id = int(links[0].id)

        assessment_after_first_link = OrganizationRequirementAssessment.query.filter_by(
            organization_id=org_id,
            requirement_id=requirement_id,
        ).first()
        assert assessment_after_first_link is not None
        assert assessment_after_first_link.computed_score == 1
        assert assessment_after_first_link.computed_flag == "High risk gap"

    second_link_resp = client.post(
        f"/compliance-requirements/{requirement_id}/link",
        data={
            "document_id": document_id,
            "evidence_bucket": "implementation",
            "rationale_note": "Implementation evidence",
        },
        follow_redirects=False,
    )
    assert second_link_resp.status_code in {302, 303}

    with app.app_context():
        assessment_after_second_link = OrganizationRequirementAssessment.query.filter_by(
            organization_id=org_id,
            requirement_id=requirement_id,
        ).first()
        assert assessment_after_second_link is not None
        assert assessment_after_second_link.computed_score == 2
        assert assessment_after_second_link.computed_flag == "OK"

    unlink_resp = client.post(
        f"/compliance-requirements/{requirement_id}/unlink/{link_id}",
        follow_redirects=False,
    )
    assert unlink_resp.status_code in {302, 303}

    with app.app_context():
        links_after = RequirementEvidenceLink.query.filter_by(
            organization_id=org_id,
            requirement_id=requirement_id,
        ).all()
        assert len(links_after) == 1

        assessment_after_unlink = OrganizationRequirementAssessment.query.filter_by(
            organization_id=org_id,
            requirement_id=requirement_id,
        ).first()
        assert assessment_after_unlink is not None
        assert assessment_after_unlink.computed_score == 1
        assert assessment_after_unlink.computed_flag == "High risk gap"
