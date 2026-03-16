from __future__ import annotations


def test_ai_review_workspace_shows_selected_repository_documents(client, app, db_session, seed_org_user):
    from app.models import Document
    from tests.conftest import login

    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        doc_a = Document(
            filename='policy-a.txt',
            blob_name='org_1/policy-a.txt',
            file_size=128,
            content_type='text/plain',
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            is_active=True,
        )
        doc_b = Document(
            filename='policy-b.txt',
            blob_name='org_1/policy-b.txt',
            file_size=128,
            content_type='text/plain',
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            is_active=True,
        )
        db_session.session.add(doc_a)
        db_session.session.add(doc_b)
        db_session.session.commit()
        doc_ids = [int(doc_a.id), int(doc_b.id)]

    resp = login(client)
    assert resp.status_code in {302, 303}

    workspace_resp = client.get(f'/ai-demo?doc_ids={doc_ids[0]}&doc_ids={doc_ids[1]}', follow_redirects=True)

    assert workspace_resp.status_code == 200
    assert b'AI Review Workspace' in workspace_resp.data
    assert b'Selected repository documents' in workspace_resp.data
    assert b'policy-a.txt' in workspace_resp.data
    assert b'policy-b.txt' in workspace_resp.data
    assert b'Repository document' in workspace_resp.data


def test_ai_review_api_can_analyze_stored_repository_document(client, app, db_session, seed_org_user, monkeypatch):
    from app.models import Document
    from tests.conftest import login
    from app.services.rag_query_service import RagCitation, RagQueryResult
    import app.main.routes as routes
    import app.services.azure_storage as azure_storage_module

    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        document = Document(
            filename='incident-policy.txt',
            blob_name='org_1/incident-policy.txt',
            file_size=256,
            content_type='text/plain',
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            is_active=True,
        )
        db_session.session.add(document)
        db_session.session.commit()
        doc_id = int(document.id)

    class FakeStorage:
        def __init__(self, *args, **kwargs):
            pass

        def download_file(self, blob_name):
            return {
                'success': True,
                'data': b'Incident reporting steps, escalation pathway, participant communication, and review cadence are defined.',
            }

    def fake_query(*, corpus_path, query_text, requirement_id=None, top_k=3):
        return RagQueryResult(
            answer='ok',
            citations=[
                RagCitation(
                    chunk_id='chunk-1',
                    source_id='ndis',
                    page_number=2,
                    score=1.2,
                    text='Incident management systems must document reporting and escalation.',
                )
            ],
            retrieval_mode='hybrid',
        )

    monkeypatch.setattr(azure_storage_module, 'AzureBlobStorageService', FakeStorage)
    monkeypatch.setattr(routes.rag_query_service, 'query', fake_query)
    monkeypatch.setattr(
        routes,
        '_openrouter_demo_summary',
        lambda **kwargs: (
            '1) Why this status\nCore controls were found.\n\n2) Missing evidence\nSome implementation proof may still be required.\n\n3) Recommended next action\nVerify supporting records.',
            None,
            'test-model',
        ),
    )

    resp = login(client)
    assert resp.status_code in {302, 303}

    analyze_resp = client.post(
        '/api/ai/demo/analyze',
        data={'stored_doc_id': str(doc_id), 'question': 'Does this document support incident readiness?'},
        follow_redirects=False,
    )

    assert analyze_resp.status_code == 200
    payload = analyze_resp.get_json()
    assert payload['success'] is True
    assert payload['meta']['source'] == 'repository'
    assert payload['meta']['stored_doc_id'] == doc_id
    assert payload['meta']['filename'] == 'incident-policy.txt'
    assert len(payload['citations']) == 1