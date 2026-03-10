import io
import os
from datetime import datetime, timezone

from app import create_app, db
from app.models import Organization, OrganizationMembership, User

os.environ['FLASK_CONFIG'] = 'testing'
app = create_app()

with app.app_context():
    db.create_all()

    org = Organization.query.filter_by(name='AI Demo Mode Check Org').first()
    if not org:
        org = Organization(name='AI Demo Mode Check Org')
        db.session.add(org)
        db.session.flush()

    org.contact_email = 'org@example.com'
    org.address = 'x'
    org.industry = 'NDIS'
    org.abn = '123'
    org.organization_type = 'Provider'
    org.operates_in_australia = True
    org.declarations_accepted_at = datetime.now(timezone.utc)
    org.data_processing_ack_at = datetime.now(timezone.utc)

    user = User.query.filter_by(email='ai-demo-mode-check@example.com').first()
    if not user:
        user = User(email='ai-demo-mode-check@example.com', full_name='AI Demo Check', is_active=True)
        user.set_password('Password123!')
        db.session.add(user)
        db.session.flush()

    user.organization_id = int(org.id)
    user.email_verified = True

    membership = OrganizationMembership.query.filter_by(user_id=int(user.id), organization_id=int(org.id)).first()
    if not membership:
        membership = OrganizationMembership(user_id=int(user.id), organization_id=int(org.id), role='Admin', is_active=True)
        db.session.add(membership)
    else:
        membership.role = 'Admin'
        membership.is_active = True

    db.session.commit()

    client = app.test_client()
    with client.session_transaction() as sess:
        sess['_user_id'] = str(user.id)
        sess['_fresh'] = True
        sess['session_version'] = int(getattr(user, 'session_version', 1) or 1)
        sess['auth_time'] = int(datetime.now(timezone.utc).timestamp())

    text = (
        b'Incident Management and Participant Safety Policy. '
        b'Purpose: Define incident identification, reporting, triage, investigation, and participant communication. '
        b'Participants are informed using preferred language and communication mode. '
        b'Investigation and corrective actions are documented with owners and due dates. '
        b'Monitoring is completed monthly by governance committee.'
    )
    question = 'Does this document define incident reporting timeline, escalation, participant communication, corrective actions, and governance review?'

    for mode in ['balanced', 'strict']:
        response = client.post(
            '/api/ai/demo/analyze',
            data={
                'question': question,
                'mode': mode,
                'file': (io.BytesIO(text), 'sample_strong_incident_policy.txt'),
            },
            content_type='multipart/form-data',
            follow_redirects=False,
        )
        payload = response.get_json(silent=True) or {}
        summary = (payload.get('summary') or '').strip()
        print('MODE', mode, 'STATUS', payload.get('status'), 'CONF', payload.get('confidence'), 'SUMMARY_LEN', len(summary))
