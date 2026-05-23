from datetime import datetime, timedelta, timezone

from app import db
from app.models import (
    ComplianceFrameworkVersion,
    ComplianceRequirement,
    Document,
    LoginEvent,
    OrganizationRequirementAssessment,
    RequirementEvidenceLink,
)


def _login(client):
    resp = client.post(
        '/auth/login',
        data={'email': 'user@example.com', 'password': 'Passw0rd1', 'remember_me': 'y'},
        follow_redirects=False,
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert resp.status_code in {302, 303}


def _seed_analytics_data(app, org_id: int, user_id: int):
    with app.app_context():
        framework = ComplianceFrameworkVersion(
            organization_id=int(org_id),
            jurisdiction='AU',
            scheme='NDIS',
            version_label='v1.0',
            is_active=True,
        )
        db.session.add(framework)
        db.session.flush()

        req_a = ComplianceRequirement(framework_version_id=int(framework.id), requirement_id='REQ-1')
        req_b = ComplianceRequirement(framework_version_id=int(framework.id), requirement_id='REQ-2')
        db.session.add_all([req_a, req_b])
        db.session.flush()

        now = datetime.now(timezone.utc)
        db.session.add_all([
            OrganizationRequirementAssessment(
                organization_id=int(org_id),
                requirement_id=int(req_a.id),
                computed_score=2,
                computed_flag='OK',
                last_assessed_at=now - timedelta(days=10),
                updated_at=now - timedelta(days=8),
            ),
            OrganizationRequirementAssessment(
                organization_id=int(org_id),
                requirement_id=int(req_b.id),
                computed_score=1,
                computed_flag='High risk gap',
                last_assessed_at=now - timedelta(days=4),
                updated_at=now - timedelta(days=3),
            ),
        ])

        doc = Document(
            filename='evidence.pdf',
            blob_name='test/evidence.pdf',
            file_size=1024,
            content_type='application/pdf',
            uploaded_at=now - timedelta(days=12),
            ai_status='OK',
            ai_confidence=0.82,
            ai_question='Does this document demonstrate compliance?',
            ai_summary='The document includes clear policy statements and implementation records.',
            ai_analysis_at=now - timedelta(days=2),
            is_active=True,
            uploaded_by=int(user_id),
            organization_id=int(org_id),
        )
        db.session.add(doc)
        db.session.flush()

        db.session.add(
            RequirementEvidenceLink(
                organization_id=int(org_id),
                requirement_id=int(req_a.id),
                document_id=int(doc.id),
                evidence_bucket='system',
                linked_by_user_id=int(user_id),
                linked_at=now - timedelta(days=16),
            )
        )

        db.session.add_all([
            LoginEvent(
                user_id=int(user_id),
                email='user@example.com',
                provider='password',
                success=True,
                created_at=now - timedelta(days=6),
            ),
            LoginEvent(
                user_id=int(user_id),
                email='user@example.com',
                provider='password',
                success=False,
                reason='bad-password',
                created_at=now - timedelta(days=5),
            ),
        ])

        db.session.commit()


def test_analytics_dashboard_page_loads(client, app, seed_org_user):
    org_id, user_id, _membership_id = seed_org_user
    _seed_analytics_data(app, org_id, user_id)
    _login(client)

    response = client.get('/analytics')
    assert response.status_code == 200
    assert b'Analytics Dashboard' in response.data
    assert b'Framework Analytics' in response.data
    assert b'Analyzed Documents' in response.data
    assert b'Analyzed Files' in response.data
    assert b'Analyzed Documents History' in response.data
    assert b'View details' in response.data


def test_analytics_export_xlsx(client, app, seed_org_user):
    org_id, user_id, _membership_id = seed_org_user
    _seed_analytics_data(app, org_id, user_id)
    _login(client)

    response = client.get('/analytics/export.xlsx')
    assert response.status_code == 200
    assert 'spreadsheetml.sheet' in (response.headers.get('Content-Type') or '')
    assert response.data[:2] == b'PK'


def test_analytics_export_pdf(client, app, seed_org_user):
    org_id, user_id, _membership_id = seed_org_user
    _seed_analytics_data(app, org_id, user_id)
    _login(client)

    response = client.get('/analytics/export.pdf')
    assert response.status_code == 200
    assert 'application/pdf' in (response.headers.get('Content-Type') or '')
    assert response.data[:4] == b'%PDF'
