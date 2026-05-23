from __future__ import annotations


def test_bulk_delete_selected_documents_requires_exact_confirmation(client, app, db_session, seed_org_user, monkeypatch):
    from app.models import Document
    from tests.conftest import login

    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        document = Document(
            filename='delete-me.pdf',
            blob_name='org_1/delete-me.pdf',
            file_size=256,
            content_type='application/pdf',
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

        def delete_file(self, blob_name):
            return {'success': True}

    import app.services.azure_storage as azure_storage_module

    monkeypatch.setattr(azure_storage_module, 'AzureBlobStorageService', FakeStorage)

    resp = login(client)
    assert resp.status_code in {302, 303}

    delete_resp = client.post(
        '/documents/delete-selected',
        data={'doc_ids': [str(doc_id)], 'confirmation_text': 'delete'},
        follow_redirects=False,
    )
    assert delete_resp.status_code in {302, 303}

    with app.app_context():
        document = db_session.session.get(Document, int(doc_id))
        assert document is not None
        assert document.is_active is True


def test_bulk_delete_selected_documents_soft_deletes_multiple_docs(client, app, db_session, seed_org_user, monkeypatch):
    from app.models import Document
    from tests.conftest import login

    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        doc_a = Document(
            filename='delete-a.pdf',
            blob_name='org_1/delete-a.pdf',
            file_size=256,
            content_type='application/pdf',
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            is_active=True,
        )
        doc_b = Document(
            filename='delete-b.pdf',
            blob_name='org_1/delete-b.pdf',
            file_size=256,
            content_type='application/pdf',
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            is_active=True,
        )
        db_session.session.add(doc_a)
        db_session.session.add(doc_b)
        db_session.session.commit()
        doc_ids = [int(doc_a.id), int(doc_b.id)]

    class FakeStorage:
        def __init__(self, *args, **kwargs):
            pass

        def delete_file(self, blob_name):
            return {'success': True}

    import app.services.azure_storage as azure_storage_module

    monkeypatch.setattr(azure_storage_module, 'AzureBlobStorageService', FakeStorage)

    resp = login(client)
    assert resp.status_code in {302, 303}

    delete_resp = client.post(
        '/documents/delete-selected',
        data={'doc_ids': [str(doc_ids[0]), str(doc_ids[1])], 'confirmation_text': 'DELETE'},
        follow_redirects=False,
    )
    assert delete_resp.status_code in {302, 303}

    with app.app_context():
        docs = (
            Document.query
            .filter(Document.id.in_(doc_ids))
            .order_by(Document.id.asc())
            .all()
        )
        assert len(docs) == 2
        assert all(d.is_active is False for d in docs)