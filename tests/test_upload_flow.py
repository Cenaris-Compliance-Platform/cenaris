from __future__ import annotations

from pathlib import Path


def test_upload_allows_when_billing_incomplete(client, app, db_session, seed_org_user, monkeypatch):
    """Regression: uploads must not be blocked just because billing is incomplete."""

    from app.models import Document, Organization

    org_id, _user_id, _membership_id = seed_org_user

    # Ensure billing is incomplete for this org.
    with app.app_context():
        org = db_session.session.get(Organization, int(org_id))
        assert org is not None
        org.billing_email = None
        org.billing_address = None
        db_session.session.commit()

    # Login as org admin
    resp = client.post(
        "/auth/login",
        data={"email": "user@example.com", "password": "Passw0rd1", "remember_me": "y"},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code in {302, 303}

    class FakeStorage:
        def is_configured(self):
            return True

        def generate_blob_name(self, original_filename, user_id, organization_id=None):
            # Stable path for assertions.
            return f"org_{organization_id}/user_{user_id}/{original_filename}"

        def upload_file(self, file_stream, file_path, content_type=None, metadata=None):
            # Consume some bytes so we know the stream is readable.
            file_stream.read(32)
            return {"success": True, "file_path": file_path, "storage_type": "Blob_Storage"}

        def delete_file(self, blob_name):
            return True

    import app.upload.routes as upload_routes

    monkeypatch.setattr(upload_routes, "AzureBlobStorageService", FakeStorage)

    test_pdf = Path("tests") / "test_files" / "test_doc.pdf"
    with test_pdf.open("rb") as f:
        resp2 = client.post(
            "/upload",
            data={"file": (f, "test_doc.pdf")},
            content_type="multipart/form-data",
            follow_redirects=False,
        )

    assert resp2.status_code in {302, 303}
    location = resp2.headers.get("Location", "")
    assert "/dashboard" in location
    assert "/onboarding/billing" not in location

    with app.app_context():
        docs = (
            Document.query.filter_by(organization_id=int(org_id), is_active=True)
            .order_by(Document.id.desc())
            .all()
        )
        assert docs
        assert docs[0].filename == "test_doc.pdf"
