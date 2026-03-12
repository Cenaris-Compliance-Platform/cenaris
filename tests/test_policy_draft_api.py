from datetime import datetime, timezone

from app import db
from app.models import AIUsageEvent, Organization, OrganizationMembership, User


def _create_org() -> Organization:
    org = Organization(
        name="Policy Draft Org",
        abn="12345678901",
        organization_type="Company",
        contact_email="policydraft@example.com",
        address="1 Draft Street",
        industry="Other",
        operates_in_australia=True,
        declarations_accepted_at=datetime.now(timezone.utc),
        data_processing_ack_at=datetime.now(timezone.utc),
    )
    db.session.add(org)
    db.session.flush()
    return org


def _create_admin_user(org_id: int) -> User:
    user = User(email="policy-draft-admin@example.com", email_verified=True, is_active=True, organization_id=org_id)
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
        data={"email": "policy-draft-admin@example.com", "password": "Passw0rd1", "remember_me": "y"},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code in {302, 303}


def test_policy_draft_api_returns_draft(client, app, monkeypatch):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        db.session.commit()

    _login(client)

    from app.services.rag_query_service import RagCitation, RagQueryResult
    import app.main.routes as routes

    def _fake_rag_query(*, corpus_path, query_text, requirement_id=None, top_k=3):
        return RagQueryResult(
            answer="Retrieved relevant NDIS source passages for this query. Review citations below before final compliance judgment.",
            citations=[
                RagCitation(
                    chunk_id="page2_off0_abc",
                    source_id="ndis-practice-standards",
                    page_number=2,
                    score=8.2,
                    text="Providers must maintain documented incident procedures.",
                )
            ],
        )

    monkeypatch.setattr(routes.rag_query_service, "query", _fake_rag_query)

    response = client.post(
        "/api/policy/draft",
        json={
            "policy_type": "Incident Management Policy",
            "query": "Need a draft for incident reporting and escalation",
            "requirement_id": "REQ-LINK-1",
            "top_k": 2,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert "Incident Management Policy" in payload["draft_text"]
    assert "Retrieved NDIS Citations" in payload["draft_text"]
    assert len(payload["citations"]) == 1

    with app.app_context():
        event = AIUsageEvent.query.filter_by(event='policy_draft').order_by(AIUsageEvent.id.desc()).first()
        assert event is not None
        assert event.mode == 'deterministic'
        assert event.provider == 'local'


def test_policy_draft_api_requires_policy_type(client, app):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        db.session.commit()

    _login(client)

    response = client.post(
        "/api/policy/draft",
        json={
            "query": "draft please",
            "requirement_id": "REQ-LINK-1",
        },
    )

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert "policy_type is required" in payload["error"]


def test_policy_draft_api_uses_llm_mode_when_enabled(client, app, monkeypatch):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        app.config['POLICY_DRAFT_USE_LLM'] = True
        app.config['AI_ENVIRONMENT'] = 'production'
        app.config['AZURE_OPENAI_ENDPOINT'] = 'https://example.openai.azure.com'
        app.config['AZURE_OPENAI_API_KEY'] = 'fake-key'
        app.config['AZURE_OPENAI_CHAT_DEPLOYMENT_WRITER'] = 'gpt-4.1'
        db.session.commit()

    _login(client)

    from app.services.rag_query_service import RagCitation, RagQueryResult
    import app.main.routes as routes

    def _fake_rag_query(*, corpus_path, query_text, requirement_id=None, top_k=3):
        return RagQueryResult(
            answer='Retrieved relevant NDIS source passages for this query. Review citations below before final compliance judgment.',
            citations=[
                RagCitation(
                    chunk_id='page5_off0_xyz',
                    source_id='ndis-practice-standards',
                    page_number=5,
                    score=7.1,
                    text='Policy must define escalation and reporting pathways.',
                )
            ],
        )

    from app.services.azure_openai_policy_service import AzurePolicyDraftResponse

    def _fake_llm_generate(**kwargs):
        return AzurePolicyDraftResponse(
            draft_text='LLM POLICY DRAFT OUTPUT',
            disclaimer='Draft generated for compliance support only. This is not legal advice or certification. A qualified reviewer must approve before use.',
            deployment='gpt-4.1',
            usage={'prompt_tokens': 100, 'completion_tokens': 200, 'total_tokens': 300},
        )

    monkeypatch.setattr(routes.rag_query_service, 'query', _fake_rag_query)
    monkeypatch.setattr(routes.azure_openai_policy_service, 'generate_policy_draft', _fake_llm_generate)

    response = client.post(
        '/api/policy/draft',
        json={
            'policy_type': 'Incident Management Policy',
            'query': 'Need incident policy draft',
            'requirement_id': 'REQ-LINK-1',
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['draft_mode'] == 'llm'
    assert payload['draft_text'] == 'LLM POLICY DRAFT OUTPUT'
    assert payload['llm']['provider'] == 'azure-openai'
    assert payload['llm']['usage']['total_tokens'] == 300

    with app.app_context():
        event = AIUsageEvent.query.filter_by(event='policy_draft').order_by(AIUsageEvent.id.desc()).first()
        assert event is not None
        assert event.mode == 'llm'
        assert event.provider == 'azure-openai'
        assert event.total_tokens == 300


def test_policy_draft_api_blocks_llm_in_dev_by_default(client, app, monkeypatch):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        app.config['POLICY_DRAFT_USE_LLM'] = True
        app.config['AI_ENVIRONMENT'] = 'development'
        app.config['AI_POLICY_LLM_ALLOW_IN_DEVELOPMENT'] = False
        app.config['AZURE_OPENAI_ENDPOINT'] = 'https://example.openai.azure.com'
        app.config['AZURE_OPENAI_API_KEY'] = 'fake-key'
        app.config['AZURE_OPENAI_CHAT_DEPLOYMENT_WRITER'] = 'gpt-4.1'
        db.session.commit()

    _login(client)

    from app.services.rag_query_service import RagCitation, RagQueryResult
    import app.main.routes as routes

    def _fake_rag_query(*, corpus_path, query_text, requirement_id=None, top_k=3):
        return RagQueryResult(
            answer='Retrieved relevant NDIS source passages for this query. Review citations below before final compliance judgment.',
            citations=[
                RagCitation(
                    chunk_id='page5_off0_xyz',
                    source_id='ndis-practice-standards',
                    page_number=5,
                    score=7.1,
                    text='Policy must define escalation and reporting pathways.',
                )
            ],
        )

    monkeypatch.setattr(routes.rag_query_service, 'query', _fake_rag_query)

    response = client.post(
        '/api/policy/draft',
        json={
            'policy_type': 'Incident Management Policy',
            'query': 'Need incident policy draft',
            'requirement_id': 'REQ-LINK-1',
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['draft_mode'] == 'deterministic'
    assert any('disabled outside production' in msg for msg in payload['warnings'])
