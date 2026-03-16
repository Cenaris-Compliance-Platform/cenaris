from __future__ import annotations


def test_dashboard_nav_shows_ai_review_but_hides_legacy_ai_links(client, app, seed_org_user):
    from tests.conftest import login

    resp = login(client)
    assert resp.status_code in {302, 303}

    dashboard_resp = client.get('/dashboard', follow_redirects=True)
    assert dashboard_resp.status_code == 200
    assert b'Evidence Repository' in dashboard_resp.data
    assert b'AI Review' in dashboard_resp.data
    assert b'AI Evidence' not in dashboard_resp.data
    assert b'AI Demo' not in dashboard_resp.data


def test_legacy_ai_evidence_routes_redirect_to_primary_document_flow(client, app, db_session, seed_org_user):
    from app.models import Document
    from tests.conftest import login

    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        document = Document(
            filename='legacy-ai-evidence.pdf',
            blob_name='org_1/legacy-ai-evidence.pdf',
            file_size=512,
            content_type='application/pdf',
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            is_active=True,
        )
        db_session.session.add(document)
        db_session.session.commit()
        doc_id = int(document.id)

    resp = login(client)
    assert resp.status_code in {302, 303}

    list_resp = client.get('/ai-evidence', follow_redirects=False)
    assert list_resp.status_code in {302, 303}
    assert list_resp.headers.get('Location', '').endswith('/evidence-repository')

    detail_resp = client.get(f'/ai-evidence/{doc_id}', follow_redirects=False)
    assert detail_resp.status_code in {302, 303}
    assert detail_resp.headers.get('Location', '').endswith(f'/document/{doc_id}/details')