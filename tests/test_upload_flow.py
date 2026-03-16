from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone


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
        assert docs[0].ai_status is None
        assert docs[0].extracted_text is None


def test_dashboard_shows_auto_analysis_results(client, app, db_session, seed_org_user):
    """Dashboard should show uploaded-document review results in the standard user flow."""
    from app.models import Document
    from tests.conftest import login

    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        doc = Document(
            filename='reviewed_policy.pdf',
            blob_name='org_1/reviewed_policy.pdf',
            file_size=2048,
            content_type='application/pdf',
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            extracted_text='policy review text',
            search_text='reviewed_policy.pdf policy review text',
            ai_status='High risk gap',
            ai_confidence=0.41,
            ai_focus_area='Complaints Management',
            ai_summary='1) Why this status\nEvidence is partial.\n\n2) Missing evidence\nInvestigation and review are unclear.\n\n3) Recommended next action\nAdd clearer operational detail.',
            ai_analysis_at=datetime.now(timezone.utc),
            is_active=True,
        )
        db_session.session.add(doc)
        db_session.session.commit()

    resp = login(client)
    assert resp.status_code in {302, 303}

    dashboard_resp = client.get('/dashboard', follow_redirects=True)
    assert dashboard_resp.status_code == 200
    assert b'Recent Evidence Reviews' in dashboard_resp.data
    assert b'reviewed_policy.pdf' in dashboard_resp.data
    assert b'Complaints Management' in dashboard_resp.data


def test_manual_analyze_document_updates_review_and_links(client, app, db_session, seed_org_user, monkeypatch):
    from app.models import ComplianceFrameworkVersion, ComplianceRequirement, Document, RequirementEvidenceLink
    from tests.conftest import login
    import app.main.routes as main_routes
    import app.services.azure_storage as azure_storage_module

    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        framework = ComplianceFrameworkVersion(
            organization_id=None,
            scheme='NDIS',
            version_label='v1.0',
            is_active=True,
        )
        db_session.session.add(framework)
        db_session.session.flush()

        requirement = ComplianceRequirement(
            framework_version_id=int(framework.id),
            requirement_id='NDIS-CM-1',
            module_name='Complaints Management',
            standard_name='Complaints',
            outcome_text='Complaint handling and resolution',
            system_evidence_required='Policy and process for complaints management.',
        )
        document = Document(
            filename='complaints.pdf',
            blob_name='org_1/complaints.pdf',
            file_size=1024,
            content_type='application/pdf',
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            is_active=True,
        )
        db_session.session.add(requirement)
        db_session.session.add(document)
        db_session.session.commit()
        doc_id = int(document.id)
        requirement_id = int(requirement.id)

    class FakeStorage:
        def __init__(self, *args, **kwargs):
            pass

        def download_file(self, blob_name):
            return {'success': True, 'data': b'complaints process document text'}

    class FakeAnalysisService:
        def analyze_document_bytes(self, *, filename, raw_bytes, organization_id=None):
            return {
                'success': True,
                'status': 'OK',
                'confidence': 0.71,
                'focus_area': 'Complaints Management',
                'question': 'Does this document support complaints handling requirements?',
                'summary': '1) Why this status\nThe document describes complaints intake and resolution.\n\n2) Missing evidence\nPeriodic review evidence is still missing.\n\n3) Recommended next action\nAdd review cadence and monitoring evidence.',
                'provider': 'deterministic',
                'model_used': 'deterministic',
                'retrieval_mode': 'hybrid',
                'extracted_text': 'complaints process document text',
                'matched_requirements': [
                    {
                        'requirement_db_id': requirement_id,
                        'requirement_id': 'NDIS-CM-1',
                        'label': 'Complaints Management',
                        'evidence_bucket': 'system',
                        'rationale_note': 'Matched complaints management wording.',
                    }
                ],
            }

    monkeypatch.setattr(azure_storage_module, 'AzureBlobStorageService', FakeStorage)
    monkeypatch.setattr(main_routes, 'document_analysis_service', FakeAnalysisService())

    resp = login(client)
    assert resp.status_code in {302, 303}

    analyze_resp = client.post(f'/document/{doc_id}/analyze', data={}, follow_redirects=False)
    assert analyze_resp.status_code in {302, 303}

    with app.app_context():
        doc = db_session.session.get(Document, int(doc_id))
        assert doc is not None
        assert doc.ai_status == 'OK'
        assert doc.ai_focus_area == 'Complaints Management'
        assert doc.extracted_text == 'complaints process document text'

        links = RequirementEvidenceLink.query.filter_by(document_id=int(doc_id)).all()
        assert len(links) == 1
        assert int(links[0].requirement_id) == int(requirement_id)


def test_bulk_analyze_selected_documents_updates_multiple_docs(client, app, db_session, seed_org_user, monkeypatch):
    from app.models import Document
    from tests.conftest import login
    import app.main.routes as main_routes
    import app.services.azure_storage as azure_storage_module

    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        doc_a = Document(
            filename='policy_a.pdf',
            blob_name='org_1/policy_a.pdf',
            file_size=1024,
            content_type='application/pdf',
            uploaded_by=int(user_id),
            organization_id=int(org_id),
            is_active=True,
        )
        doc_b = Document(
            filename='policy_b.pdf',
            blob_name='org_1/policy_b.pdf',
            file_size=1024,
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

        def download_file(self, blob_name):
            return {'success': True, 'data': b'bulk document bytes'}

    class FakeAnalysisService:
        def analyze_document_bytes(self, *, filename, raw_bytes, organization_id=None):
            return {
                'success': True,
                'status': 'OK',
                'confidence': 0.66,
                'focus_area': 'General Compliance Evidence',
                'question': 'Does this document provide usable evidence?',
                'summary': '1) Why this status\nCore controls were found.\n\n2) Missing evidence\nSome detail is still required.\n\n3) Recommended next action\nAttach additional supporting records.',
                'provider': 'deterministic',
                'model_used': 'deterministic',
                'retrieval_mode': 'hybrid',
                'extracted_text': 'bulk document extracted text',
                'matched_requirements': [],
            }

    monkeypatch.setattr(azure_storage_module, 'AzureBlobStorageService', FakeStorage)
    monkeypatch.setattr(main_routes, 'document_analysis_service', FakeAnalysisService())

    resp = login(client)
    assert resp.status_code in {302, 303}

    analyze_resp = client.post(
        '/documents/analyze-selected',
        data={'doc_ids': [str(doc_ids[0]), str(doc_ids[1])]},
        follow_redirects=False,
    )
    assert analyze_resp.status_code in {302, 303}

    with app.app_context():
        docs = (
            Document.query
            .filter(Document.id.in_(doc_ids))
            .order_by(Document.id.asc())
            .all()
        )
        assert len(docs) == 2
        assert all((d.ai_status or '') == 'OK' for d in docs)
        assert all((d.extracted_text or '') == 'bulk document extracted text' for d in docs)
