from datetime import datetime, timezone

from app import db
from app.models import (
    ComplianceFrameworkVersion,
    ComplianceRequirement,
    Document,
    Organization,
    OrganizationMembership,
    RequirementEvidenceLink,
    User,
)


def _create_org() -> Organization:
    org = Organization(
        name="Policy Studio Org",
        abn="12345678901",
        organization_type="Company",
        contact_email="policy-studio@example.com",
        address="1 Policy Lane",
        industry="Other",
        operates_in_australia=True,
        declarations_accepted_at=datetime.now(timezone.utc),
        data_processing_ack_at=datetime.now(timezone.utc),
    )
    db.session.add(org)
    db.session.flush()
    return org


def _create_admin_user(org_id: int) -> User:
    user = User(email="policy-studio-admin@example.com", email_verified=True, is_active=True, organization_id=org_id)
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
        version_label="v2026.03",
        is_active=True,
    )
    db.session.add(framework)
    db.session.flush()

    requirement = ComplianceRequirement(
        framework_version_id=int(framework.id),
        requirement_id="REQ-POLICY-1",
        quality_indicator_code="QI-POLICY",
        outcome_code="OUT-POLICY",
        outcome_text="Requirement used by policy studio tests",
    )
    db.session.add(requirement)
    db.session.flush()
    return requirement


def _seed_document(org_id: int, user_id: int) -> Document:
    document = Document(
        filename="incident-policy-source.txt",
        blob_name="org/incident-policy-source.txt",
        file_size=2048,
        content_type="text/plain",
        extracted_text="Incident reporting workflow includes escalation and time-bound follow-up.",
        uploaded_by=user_id,
        organization_id=org_id,
        is_active=True,
    )
    db.session.add(document)
    db.session.flush()
    return document


def _login(client):
    resp = client.post(
        "/auth/login",
        data={"email": "policy-studio-admin@example.com", "password": "Passw0rd1", "remember_me": "y"},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code in {302, 303}


def test_policy_studio_route_loads(client, app):
    with app.app_context():
        org = _create_org()
        user = _create_admin_user(int(org.id))
        _seed_document(int(org.id), int(user.id))
        db.session.commit()

    _login(client)
    response = client.get('/policy-studio')

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Policy Studio' in body
    assert 'From scratch (recommended)' in body


def test_plans_preview_route_loads(client, app):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        db.session.commit()

    _login(client)
    response = client.get('/plans-preview')

    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'Plans & Features (Discussion Draft)' in body
    assert 'Clause Mapping' in body
    assert 'Enterprise' in body


def test_policy_draft_api_supports_document_wide_generation(client, app, monkeypatch):
    with app.app_context():
        org = _create_org()
        user = _create_admin_user(int(org.id))
        requirement = _seed_requirement(int(org.id))
        document = _seed_document(int(org.id), int(user.id))
        db.session.flush()

        db.session.add(
            RequirementEvidenceLink(
                organization_id=int(org.id),
                requirement_id=int(requirement.id),
                document_id=int(document.id),
                evidence_bucket='system',
                rationale_note='Linked for policy studio coverage',
                linked_by_user_id=int(user.id),
            )
        )
        db.session.commit()
        doc_id = int(document.id)

    _login(client)

    from app.services.rag_query_service import RagCitation, RagQueryResult
    import app.main.routes as routes

    def _fake_rag_query(*, corpus_path, query_text, requirement_id=None, top_k=3):
        assert 'Create a comprehensive Incident Management Policy' in query_text
        return RagQueryResult(
            answer='Retrieved relevant NDIS source passages for this query. Review citations below before final compliance judgment.',
            citations=[
                RagCitation(
                    chunk_id='page4_off0_abc',
                    source_id='ndis-practice-standards',
                    page_number=4,
                    score=7.9,
                    text='Providers must maintain documented incident procedures.',
                )
            ],
        )

    monkeypatch.setattr(routes.rag_query_service, 'query', _fake_rag_query)

    response = client.post(
        '/api/policy/draft',
        json={
            'policy_type': 'Incident Management Policy',
            'document_id': doc_id,
            'requirement_scope': 'linked',
            'output_mode': 'full_draft',
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['inputs']['document_id'] == doc_id
    assert payload['inputs']['requirement_scope'] == 'linked'
    assert payload['inputs']['linked_requirements_count'] == 1
    assert 'Incident Management Policy' in payload['draft_text']


def test_policy_export_docx_returns_file(client, app):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        db.session.commit()

    _login(client)
    response = client.post(
        '/api/policy/export-docx',
        json={
            'policy_type': 'Incident Management Policy',
            'draft_text': 'Incident Management Policy\n\nPurpose:\nDefine incident handling steps.\n\n- Log incidents\n- Escalate critical events',
        },
    )

    assert response.status_code == 200
    assert response.headers.get('Content-Type', '').startswith(
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    assert response.data[:2] == b'PK'
