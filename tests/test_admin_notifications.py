from __future__ import annotations

from pathlib import Path


def test_notifications_page_admin_only(client, app, db_session, seed_org_user):
    from app.models import OrganizationMembership, User

    org_id, _admin_user_id, _membership_id = seed_org_user

    with app.app_context():
        member = User(email='member@example.com', email_verified=True, is_active=True)
        member.set_password('Passw0rd1')
        member.organization_id = int(org_id)
        db_session.session.add(member)
        db_session.session.flush()

        db_session.session.add(
            OrganizationMembership(
                organization_id=int(org_id),
                user_id=int(member.id),
                role='User',
                is_active=True,
            )
        )
        db_session.session.commit()

    login_resp = client.post(
        '/auth/login',
        data={'email': 'member@example.com', 'password': 'Passw0rd1', 'remember_me': 'y'},
        follow_redirects=False,
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert login_resp.status_code in {302, 303}

    resp = client.get('/notifications', follow_redirects=False)
    assert resp.status_code == 403


def test_upload_creates_admin_notification(client, app, db_session, seed_org_user, monkeypatch):
    from app.models import AdminNotification

    org_id, _user_id, _membership_id = seed_org_user

    login_resp = client.post(
        '/auth/login',
        data={'email': 'user@example.com', 'password': 'Passw0rd1', 'remember_me': 'y'},
        follow_redirects=False,
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert login_resp.status_code in {302, 303}

    class FakeStorage:
        def is_configured(self):
            return True

        def generate_blob_name(self, original_filename, user_id, organization_id=None):
            return f"org_{organization_id}/user_{user_id}/{original_filename}"

        def upload_file(self, file_stream, file_path, content_type=None, metadata=None):
            file_stream.read(32)
            return {'success': True, 'file_path': file_path, 'storage_type': 'Blob_Storage'}

        def delete_file(self, blob_name):
            return True

    import app.upload.routes as upload_routes

    monkeypatch.setattr(upload_routes, 'AzureBlobStorageService', FakeStorage)

    test_pdf = Path('tests') / 'test_files' / 'test_doc.pdf'
    with test_pdf.open('rb') as f:
        resp = client.post(
            '/upload',
            data={'file': (f, 'test_doc.pdf')},
            content_type='multipart/form-data',
            follow_redirects=False,
        )

    assert resp.status_code in {302, 303}

    with app.app_context():
        latest = (
            AdminNotification.query
            .filter_by(organization_id=int(org_id), event_type='document_uploaded')
            .order_by(AdminNotification.id.desc())
            .first()
        )
        assert latest is not None
        assert latest.severity == 'info'
        assert latest.is_read is False
        assert 'uploaded' in (latest.message or '').lower()


def test_admin_can_save_monthly_report_settings(client, app, db_session, seed_org_user):
    from app.models import Organization

    org_id, _user_id, _membership_id = seed_org_user

    login_resp = client.post(
        '/auth/login',
        data={'email': 'user@example.com', 'password': 'Passw0rd1', 'remember_me': 'y'},
        follow_redirects=False,
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert login_resp.status_code in {302, 303}

    resp = client.post(
        '/organization/settings',
        data={
            'form_name': 'monthly_reports',
            'monthly_report_enabled': 'y',
            'monthly_report_recipient_email': 'reports@example.com',
        },
        follow_redirects=False,
    )
    assert resp.status_code in {302, 303}

    with app.app_context():
        org = db_session.session.get(Organization, int(org_id))
        assert org is not None
        assert org.monthly_report_enabled is True
        assert org.monthly_report_recipient_email == 'reports@example.com'


def test_monthly_digest_honors_org_delivery_settings(app, db_session, seed_org_user, monkeypatch):
    from app.models import AdminNotification, Organization
    from app.services.notification_service import notification_service

    org_id, _user_id, _membership_id = seed_org_user

    delivered: list[tuple[str, str]] = []

    def _fake_send(to_email: str, subject: str, body: str, html: str) -> bool:
        delivered.append((to_email, subject))
        return True

    monkeypatch.setattr(notification_service, '_send_email_html', _fake_send)

    with app.app_context():
        db_session.session.add(
            AdminNotification(
                organization_id=int(org_id),
                event_type='document_uploaded',
                title='A document was uploaded',
                message='Test notification',
                severity='info',
                is_read=False,
            )
        )
        db_session.session.commit()

        sent_disabled = notification_service.send_monthly_digest(
            organization_id=int(org_id),
            year=2026,
            month=3,
        )
        assert sent_disabled == 0

        org = db_session.session.get(Organization, int(org_id))
        org.monthly_report_enabled = True
        org.monthly_report_recipient_email = 'digest@example.com'
        db_session.session.commit()

        sent_enabled = notification_service.send_monthly_digest(
            organization_id=int(org_id),
            year=2026,
            month=3,
        )
        assert sent_enabled == 1
        assert delivered[-1][0] == 'digest@example.com'


def test_monthly_report_settings_sends_setup_confirmation(client, app, seed_org_user, monkeypatch):
    from app.services.notification_service import notification_service

    login_resp = client.post(
        '/auth/login',
        data={'email': 'user@example.com', 'password': 'Passw0rd1', 'remember_me': 'y'},
        follow_redirects=False,
        environ_base={'REMOTE_ADDR': '127.0.0.1'},
    )
    assert login_resp.status_code in {302, 303}

    sent_to: list[str] = []

    def _fake_setup_email(*, recipient_email: str, organization_name: str) -> bool:
        sent_to.append(recipient_email)
        return True

    monkeypatch.setattr(notification_service, 'send_monthly_report_setup_confirmation', _fake_setup_email)

    resp = client.post(
        '/organization/settings',
        data={
            'form_name': 'monthly_reports',
            'monthly_report_enabled': 'y',
            'monthly_report_recipient_email': 'setup-confirm@example.com',
        },
        follow_redirects=False,
    )
    assert resp.status_code in {302, 303}
    assert sent_to == ['setup-confirm@example.com']
