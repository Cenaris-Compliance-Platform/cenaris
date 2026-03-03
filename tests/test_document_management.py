from __future__ import annotations

import io
import zipfile
from pathlib import Path

from app.models import Document, DocumentTag
from tests.conftest import login


def test_bulk_upload_multiple_files(client, app, seed_org_user, monkeypatch):
    """Bulk upload accepts multiple files and persists both records."""
    org_id, user_id, _membership_id = seed_org_user

    resp = login(client)
    assert resp.status_code in {302, 303}

    class FakeStorage:
        def is_configured(self):
            return True

        def generate_blob_name(self, original_filename, user_id, organization_id=None):
            return f"org_{organization_id}/user_{user_id}/{original_filename}"

        def upload_file(self, file_stream, file_path, content_type=None, metadata=None):
            file_stream.read(16)
            return {"success": True, "file_path": file_path, "storage_type": "Blob_Storage"}

        def delete_file(self, blob_name):
            return True

    import app.upload.routes as upload_routes

    monkeypatch.setattr(upload_routes, "AzureBlobStorageService", FakeStorage)

    sample_pdf = (Path("tests") / "test_files" / "test_doc.pdf").read_bytes()
    resp2 = client.post(
        "/upload",
        data={
            "files": [
                (io.BytesIO(sample_pdf), "policy_a.pdf"),
                (io.BytesIO(sample_pdf), "policy_b.pdf"),
            ]
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp2.status_code in {302, 303}

    with app.app_context():
        docs = (
            Document.query.filter_by(organization_id=int(org_id), is_active=True)
            .order_by(Document.filename.asc())
            .all()
        )
        names = [d.filename for d in docs]
        assert "policy_a.pdf" in names
        assert "policy_b.pdf" in names
        assert all(int(d.uploaded_by) == int(user_id) for d in docs)


def test_add_remove_tags_and_filter(client, app, db_session, seed_org_user):
    """Document tags can be added/removed and used by repository filters."""
    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        doc = Document(
            filename="controls.pdf",
            blob_name="org_1/controls.pdf",
            file_size=1024,
            content_type="application/pdf",
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            is_active=True,
        )
        db_session.session.add(doc)
        db_session.session.commit()
        doc_id = int(doc.id)

    resp = login(client)
    assert resp.status_code in {302, 303}

    add_resp = client.post(
        f"/document/{doc_id}/tags",
        data={"tags": "policy, ndis"},
        follow_redirects=False,
    )
    assert add_resp.status_code in {302, 303}

    with app.app_context():
        tagged_doc = db_session.session.get(Document, int(doc_id))
        tag_names = sorted([t.name for t in tagged_doc.tags])
        assert tag_names == ["ndis", "policy"]

    # Filter by tag should return the document
    list_resp = client.get("/evidence-repository?tag=policy", follow_redirects=True)
    assert list_resp.status_code == 200
    assert b"controls.pdf" in list_resp.data

    with app.app_context():
        policy_tag = (
            DocumentTag.query
            .filter_by(organization_id=int(org_id), normalized_name="policy")
            .first()
        )
        assert policy_tag is not None
        policy_tag_id = int(policy_tag.id)

    remove_resp = client.post(
        f"/document/{doc_id}/tags/{policy_tag_id}/delete",
        data={},
        follow_redirects=False,
    )
    assert remove_resp.status_code in {302, 303}

    with app.app_context():
        tagged_doc = db_session.session.get(Document, int(doc_id))
        tag_names = sorted([t.name for t in tagged_doc.tags])
        assert tag_names == ["ndis"]


def test_preview_document_streams_supported_type(client, app, db_session, seed_org_user, monkeypatch):
    """Preview endpoint streams supported content inline for authorized users."""
    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        doc = Document(
            filename="preview.pdf",
            blob_name="org_1/preview.pdf",
            file_size=120,
            content_type="application/pdf",
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            is_active=True,
        )
        db_session.session.add(doc)
        db_session.session.commit()
        doc_id = int(doc.id)

    class FakeStorage:
        def download_file(self, blob_name):
            return {"success": True, "data": b"%PDF-1.4\n%fake\n"}

    import app.services.azure_storage as azure_storage_module

    monkeypatch.setattr(azure_storage_module, "AzureBlobStorageService", FakeStorage)

    resp = login(client)
    assert resp.status_code in {302, 303}

    preview_resp = client.get(f"/document/{doc_id}/preview", follow_redirects=False)
    assert preview_resp.status_code == 200
    assert preview_resp.headers.get("X-Content-Type-Options") == "nosniff"
    assert (preview_resp.mimetype or "").startswith("application/pdf")


def test_bulk_zip_download_selected_documents(client, app, db_session, seed_org_user, monkeypatch):
    """Selected docs are downloaded as ZIP with expected filenames."""
    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        doc1 = Document(
            filename="alpha.pdf",
            blob_name="org_1/alpha.pdf",
            file_size=100,
            content_type="application/pdf",
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            is_active=True,
        )
        doc2 = Document(
            filename="beta.pdf",
            blob_name="org_1/beta.pdf",
            file_size=120,
            content_type="application/pdf",
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            is_active=True,
        )
        db_session.session.add_all([doc1, doc2])
        db_session.session.commit()
        doc_ids = [int(doc1.id), int(doc2.id)]

    class FakeStorage:
        def download_file(self, blob_name):
            return {"success": True, "data": f"content:{blob_name}".encode("utf-8")}

    import app.services.azure_storage as azure_storage_module

    monkeypatch.setattr(azure_storage_module, "AzureBlobStorageService", FakeStorage)

    resp = login(client)
    assert resp.status_code in {302, 303}

    zip_resp = client.post(
        "/documents/download-zip",
        data={"doc_ids": [str(doc_ids[0]), str(doc_ids[1])]},
        follow_redirects=False,
    )
    assert zip_resp.status_code == 200
    assert zip_resp.mimetype == "application/zip"

    archive = zipfile.ZipFile(io.BytesIO(zip_resp.data), mode="r")
    names = sorted(archive.namelist())
    assert names == ["alpha.pdf", "beta.pdf"]
