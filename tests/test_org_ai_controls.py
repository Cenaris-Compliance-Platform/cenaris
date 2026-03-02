from app import db
from app.models import AIUsageEvent, OrganizationAISettings
from datetime import datetime, timezone, timedelta


def _login(client):
    resp = client.post(
        '/auth/login',
        data={'email': 'user@example.com', 'password': 'Passw0rd1', 'remember_me': 'y'},
        follow_redirects=False,
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert resp.status_code in {302, 303}


def test_org_ai_controls_page_loads_for_admin(client, app, seed_org_user):
    _org_id, _user_id, _membership_id = seed_org_user
    _login(client)

    response = client.get('/organization/ai-controls')
    assert response.status_code == 200
    assert b'AI Controls' in response.data


def test_org_ai_controls_save_persists_settings(client, app, seed_org_user):
    org_id, _user_id, _membership_id = seed_org_user
    _login(client)

    response = client.post(
        '/organization/ai-controls',
        data={
            'policy_draft_use_llm': 'y',
            'max_query_chars': '700',
            'max_top_k': '4',
            'max_citation_text_chars': '350',
            'max_answer_chars': '1500',
            'max_policy_draft_chars': '4000',
            'rag_rate_limit': '15 per minute',
            'policy_rate_limit': '6 per minute',
            'submit': 'Save AI Controls',
        },
        follow_redirects=False,
    )

    assert response.status_code in {302, 303}

    with app.app_context():
        settings = OrganizationAISettings.query.filter_by(organization_id=int(org_id)).first()
        assert settings is not None
        assert settings.policy_draft_use_llm is True
        assert settings.max_query_chars == 700
        assert settings.max_top_k == 4
        assert settings.max_citation_text_chars == 350
        assert settings.max_answer_chars == 1500
        assert settings.max_policy_draft_chars == 4000
        assert settings.rag_rate_limit == '15 per minute'
        assert settings.policy_rate_limit == '6 per minute'


def test_rag_query_uses_org_ai_settings_override(client, app, seed_org_user, monkeypatch):
    org_id, _user_id, _membership_id = seed_org_user

    with app.app_context():
        settings = OrganizationAISettings(
            organization_id=int(org_id),
            max_query_chars=8,
            max_top_k=1,
            max_citation_text_chars=500,
            max_answer_chars=500,
            max_policy_draft_chars=1000,
            rag_rate_limit='20 per minute',
            policy_rate_limit='10 per minute',
        )
        db.session.add(settings)
        db.session.commit()

    _login(client)

    from app.services.rag_query_service import RagCitation, RagQueryResult
    import app.main.routes as routes

    def _fake_query(*, corpus_path, query_text, requirement_id=None, top_k=3):
        assert query_text == 'incident'
        assert top_k == 1
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

    response = client.post('/api/rag/query', json={'query': 'incident management', 'top_k': 9})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['limits']['top_k'] == 1


def test_org_ai_usage_csv_export(client, app, seed_org_user):
    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        db.session.add(
            AIUsageEvent(
                organization_id=int(org_id),
                user_id=int(user_id),
                event='policy_draft',
                mode='llm',
                provider='azure-openai',
                model='gpt-4.1',
                prompt_tokens=120,
                completion_tokens=80,
                total_tokens=200,
                latency_ms=450,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.session.commit()

    _login(client)

    response = client.get('/organization/ai-controls/usage.csv')
    assert response.status_code == 200
    assert 'text/csv' in (response.headers.get('Content-Type') or '')
    body = response.get_data(as_text=True)
    assert 'event,mode,provider,model' in body
    assert 'policy_draft,llm,azure-openai,gpt-4.1' in body


def test_system_logs_shows_ai_events(client, app, seed_org_user):
    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        db.session.add(
            AIUsageEvent(
                organization_id=int(org_id),
                user_id=int(user_id),
                event='rag_query',
                mode='retrieval',
                provider='local',
                model='lexical-rag',
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=32,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.session.commit()

    _login(client)

    response = client.get('/system-logs?log_type=ai&time_range=24h')
    assert response.status_code == 200
    assert b'AI Events' in response.data
    assert b'rag_query' in response.data


def test_org_ai_controls_usage_filter_by_event(client, app, seed_org_user):
    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        db.session.add(
            AIUsageEvent(
                organization_id=int(org_id),
                user_id=int(user_id),
                event='policy_draft',
                mode='llm',
                provider='azure-openai',
                model='gpt-4.1',
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                latency_ms=100,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.session.add(
            AIUsageEvent(
                organization_id=int(org_id),
                user_id=int(user_id),
                event='rag_query',
                mode='retrieval',
                provider='local',
                model='lexical-rag',
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=20,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.session.commit()

    _login(client)

    response = client.get('/organization/ai-controls?event=policy_draft&time_range=all')
    assert response.status_code == 200
    assert b'policy_draft' in response.data
    assert b'lexical-rag' not in response.data


def test_org_ai_controls_csv_respects_filters(client, app, seed_org_user):
    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        db.session.add(
            AIUsageEvent(
                organization_id=int(org_id),
                user_id=int(user_id),
                event='policy_draft',
                mode='llm',
                provider='azure-openai',
                model='gpt-4.1',
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                latency_ms=100,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.session.add(
            AIUsageEvent(
                organization_id=int(org_id),
                user_id=int(user_id),
                event='rag_query',
                mode='retrieval',
                provider='local',
                model='lexical-rag',
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=20,
                created_at=datetime.now(timezone.utc),
            )
        )
        db.session.commit()

    _login(client)

    response = client.get('/organization/ai-controls/usage.csv?event=policy_draft&time_range=all')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'policy_draft,llm,azure-openai,gpt-4.1' in body
    assert 'rag_query,retrieval,local,lexical-rag' not in body


def test_org_ai_controls_usage_pagination(client, app, seed_org_user):
    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        base = datetime.now(timezone.utc)
        for idx in range(30):
            db.session.add(
                AIUsageEvent(
                    organization_id=int(org_id),
                    user_id=int(user_id),
                    event=f'event_{idx}',
                    mode='retrieval',
                    provider='local',
                    model='lexical-rag',
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    latency_ms=10,
                    created_at=base.replace(microsecond=0),
                )
            )
            base = base.replace(microsecond=0)
        db.session.commit()

    _login(client)

    response = client.get('/organization/ai-controls?time_range=all&page=2')
    assert response.status_code == 200
    assert b'Page 2 of 2' in response.data


def test_org_ai_retention_run_dry_run_does_not_delete(client, app, seed_org_user):
    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        old_event = AIUsageEvent(
            organization_id=int(org_id),
            user_id=int(user_id),
            event='rag_query',
            mode='retrieval',
            provider='local',
            model='lexical-rag',
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=10,
            created_at=datetime.now(timezone.utc) - timedelta(days=120),
        )
        db.session.add(old_event)
        db.session.commit()
        old_event_id = int(old_event.id)

    _login(client)

    response = client.post(
        '/organization/ai-controls/retention-run',
        data={'days': '30', 'dry_run': 'y', 'submit': 'Run Retention'},
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}

    with app.app_context():
        assert db.session.get(AIUsageEvent, old_event_id) is not None


def test_org_ai_retention_run_deletes_old_rows(client, app, seed_org_user):
    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        old_event = AIUsageEvent(
            organization_id=int(org_id),
            user_id=int(user_id),
            event='rag_query',
            mode='retrieval',
            provider='local',
            model='lexical-rag',
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=10,
            created_at=datetime.now(timezone.utc) - timedelta(days=120),
        )
        recent_event = AIUsageEvent(
            organization_id=int(org_id),
            user_id=int(user_id),
            event='policy_draft',
            mode='deterministic',
            provider='local',
            model='deterministic',
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=10,
            created_at=datetime.now(timezone.utc) - timedelta(days=2),
        )
        db.session.add(old_event)
        db.session.add(recent_event)
        db.session.commit()
        old_event_id = int(old_event.id)
        recent_event_id = int(recent_event.id)

    _login(client)

    response = client.post(
        '/organization/ai-controls/retention-run',
        data={'days': '30', 'submit': 'Run Retention'},
        follow_redirects=False,
    )
    assert response.status_code in {302, 303}

    with app.app_context():
        assert db.session.get(AIUsageEvent, old_event_id) is None
        assert db.session.get(AIUsageEvent, recent_event_id) is not None
