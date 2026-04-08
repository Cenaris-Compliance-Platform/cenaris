from __future__ import annotations


def test_assistant_chat_returns_navigation_actions(client, app, seed_org_user):
    from tests.conftest import login

    resp = login(client)
    assert resp.status_code in {302, 303}

    chat_resp = client.post(
        '/api/assistant/chat',
        json={'message': 'Open AI Review please'},
        follow_redirects=False,
    )

    assert chat_resp.status_code == 200
    payload = chat_resp.get_json()
    assert payload['success'] is True
    assert isinstance(payload.get('actions'), list)
    assert any((action.get('id') == 'open_ai_review') for action in payload['actions'])


def test_assistant_chat_can_mark_all_notifications_read_for_admin(client, app, db_session, seed_org_user):
    from app.models import AdminNotification
    from tests.conftest import login

    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        n1 = AdminNotification(
            organization_id=int(org_id),
            actor_user_id=int(user_id),
            event_type='document_uploaded',
            title='Document uploaded',
            message='A document was uploaded',
            severity='info',
            is_read=False,
        )
        n2 = AdminNotification(
            organization_id=int(org_id),
            actor_user_id=int(user_id),
            event_type='document_uploaded',
            title='Document uploaded',
            message='A second document was uploaded',
            severity='info',
            is_read=False,
        )
        db_session.session.add(n1)
        db_session.session.add(n2)
        db_session.session.commit()

    resp = login(client)
    assert resp.status_code in {302, 303}

    execute_resp = client.post(
        '/api/assistant/chat',
        json={'execute': True, 'action_id': 'mark_all_notifications_read'},
        follow_redirects=False,
    )

    assert execute_resp.status_code == 200
    payload = execute_resp.get_json()
    assert payload['success'] is True
    assert payload['executed_action']['id'] == 'mark_all_notifications_read'
    assert payload['executed_action']['success'] is True
    assert payload['executed_action']['count'] == 2


def test_assistant_chat_explains_linking_evidence_value(client, app, seed_org_user):
    from tests.conftest import login

    resp = login(client)
    assert resp.status_code in {302, 303}

    chat_resp = client.post(
        '/api/assistant/chat',
        json={'message': 'how do i link them and how will it help me what is the use of it ?'},
        follow_redirects=False,
    )

    assert chat_resp.status_code == 200
    payload = chat_resp.get_json()
    assert payload['success'] is True
    reply = (payload.get('reply') or '').lower()
    assert 'ai review already tries to auto-link' in reply
    action_ids = {a.get('id') for a in (payload.get('actions') or [])}
    assert 'open_repository' in action_ids
    assert 'open_requirements' in action_ids


def test_assistant_chat_handles_profile_and_password_question(client, app, seed_org_user):
    from tests.conftest import login

    resp = login(client)
    assert resp.status_code in {302, 303}

    chat_resp = client.post(
        '/api/assistant/chat',
        json={'message': 'Where can I change my name and password?'},
        follow_redirects=False,
    )

    assert chat_resp.status_code == 200
    payload = chat_resp.get_json()
    assert payload['success'] is True
    assert 'name updates' in (payload.get('reply') or '').lower()
    assert any((action.get('id') == 'open_profile') for action in (payload.get('actions') or []))


def test_assistant_chat_uses_ai_when_available(client, app, seed_org_user, monkeypatch):
    from tests.conftest import login
    import app.main.routes as routes

    app.config['ASSISTANT_CHAT_USE_LLM'] = True

    def _fake_ai_reply(**_kwargs):
        return 'Cenaris supports end-to-end workflow guidance across repository, AI review, requirements, policy studio, analytics, and settings.'

    monkeypatch.setattr(routes, '_assistant_generate_ai_reply', _fake_ai_reply)

    resp = login(client)
    assert resp.status_code in {302, 303}

    chat_resp = client.post(
        '/api/assistant/chat',
        json={'message': 'Explain all Cenaris features in detail'},
        follow_redirects=False,
    )

    assert chat_resp.status_code == 200
    payload = chat_resp.get_json()
    assert payload['success'] is True
    assert payload.get('assistant_mode') == 'llm'
    assert 'end-to-end workflow guidance' in (payload.get('reply') or '').lower()
