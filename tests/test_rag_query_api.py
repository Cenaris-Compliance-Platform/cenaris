from datetime import datetime, timezone

from app import db
from app.models import AIUsageEvent, Organization, OrganizationMembership, User


def _create_org() -> Organization:
    org = Organization(
        name="RAG API Org",
        abn="12345678901",
        organization_type="Company",
        contact_email="ragapi@example.com",
        address="1 Rag Street",
        industry="Other",
        operates_in_australia=True,
        declarations_accepted_at=datetime.now(timezone.utc),
        data_processing_ack_at=datetime.now(timezone.utc),
    )
    db.session.add(org)
    db.session.flush()
    return org


def _create_admin_user(org_id: int) -> User:
    user = User(email="rag-api-admin@example.com", email_verified=True, is_active=True, organization_id=org_id)
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
        data={"email": "rag-api-admin@example.com", "password": "Passw0rd1", "remember_me": "y"},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code in {302, 303}


def test_rag_query_api_returns_citations(client, app, monkeypatch):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        db.session.commit()

    _login(client)

    from app.services.rag_query_service import RagCitation, RagQueryResult
    import app.main.routes as routes

    def _fake_query(*, corpus_path, query_text, requirement_id=None, top_k=3):
        assert query_text == "incident management"
        return RagQueryResult(
            answer="Retrieved relevant NDIS source passages for this query. Review citations below before final compliance judgment.",
            citations=[
                RagCitation(
                    chunk_id="page3_off0_x",
                    source_id="ndis-practice-standards",
                    page_number=3,
                    score=9.5,
                    text="Incident management systems must be documented.",
                )
            ],
        )

    monkeypatch.setattr(routes.rag_query_service, "query", _fake_query)

    response = client.post(
        "/api/rag/query",
        json={"query": "incident management", "top_k": 2},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["answer"]
    assert len(payload["citations"]) == 1
    assert payload["citations"][0]["page_number"] == 3

    with app.app_context():
        event = AIUsageEvent.query.filter_by(event='rag_query').order_by(AIUsageEvent.id.desc()).first()
        assert event is not None
        assert event.provider == 'local'
        assert event.model == 'lexical-rag'


def test_rag_query_api_requires_query_or_requirement(client, app):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        db.session.commit()

    _login(client)

    response = client.post("/api/rag/query", json={})

    assert response.status_code == 400
    payload = response.get_json()
    assert payload["success"] is False
    assert "query or requirement_id" in payload["error"]


def test_rag_query_api_clamps_query_and_top_k(client, app, monkeypatch):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        app.config['AI_MAX_QUERY_CHARS'] = 12
        app.config['AI_MAX_TOP_K'] = 2
        db.session.commit()

    _login(client)

    from app.services.rag_query_service import RagCitation, RagQueryResult
    import app.main.routes as routes

    def _fake_query(*, corpus_path, query_text, requirement_id=None, top_k=3):
        assert query_text == 'incident man'
        assert top_k == 2
        return RagQueryResult(
            answer='ok',
            citations=[
                RagCitation(
                    chunk_id='chunk-1',
                    source_id='ndis-practice-standards',
                    page_number=1,
                    score=1.0,
                    text='x',
                )
            ],
        )

    monkeypatch.setattr(routes.rag_query_service, 'query', _fake_query)

    response = client.post('/api/rag/query', json={'query': 'incident management', 'top_k': 99})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['limits']['top_k'] == 2


def test_rag_query_api_rate_limit_applies(client, app, monkeypatch):
    with app.app_context():
        org = _create_org()
        _create_admin_user(int(org.id))
        app.config['AI_RAG_RATE_LIMIT'] = '1 per minute'
        db.session.commit()

    _login(client)

    from app.services.rag_query_service import RagCitation, RagQueryResult
    import app.main.routes as routes

    def _fake_query(*, corpus_path, query_text, requirement_id=None, top_k=3):
        return RagQueryResult(
            answer='ok',
            citations=[
                RagCitation(
                    chunk_id='chunk-1',
                    source_id='ndis-practice-standards',
                    page_number=1,
                    score=1.0,
                    text='x',
                )
            ],
        )

    monkeypatch.setattr(routes.rag_query_service, 'query', _fake_query)

    first = client.post('/api/rag/query', json={'query': 'incident management'})
    second = client.post('/api/rag/query', json={'query': 'incident management'})

    assert first.status_code == 200
    assert second.status_code == 429
