from datetime import datetime, timezone, timedelta

from app import db
from app.models import AIUsageEvent, Organization, OrganizationMembership, User


def _seed_org_user(app):
    with app.app_context():
        org = Organization(
            name='Retention Org',
            abn='12345678901',
            organization_type='Company',
            contact_email='retention@example.com',
            address='1 Retention Street',
            industry='Other',
            operates_in_australia=True,
            declarations_accepted_at=datetime.now(timezone.utc),
            data_processing_ack_at=datetime.now(timezone.utc),
        )
        db.session.add(org)
        db.session.flush()

        user = User(email='retention-admin@example.com', email_verified=True, is_active=True, organization_id=int(org.id))
        user.set_password('Passw0rd1')
        db.session.add(user)
        db.session.flush()

        membership = OrganizationMembership(
            organization_id=int(org.id),
            user_id=int(user.id),
            role='Admin',
            is_active=True,
        )
        db.session.add(membership)
        db.session.commit()

        return int(org.id), int(user.id)


def test_prune_ai_usage_events_dry_run(app):
    org_id, user_id = _seed_org_user(app)

    with app.app_context():
        now = datetime.now(timezone.utc)
        db.session.add(
            AIUsageEvent(
                organization_id=org_id,
                user_id=user_id,
                event='rag_query',
                mode='retrieval',
                provider='local',
                model='lexical-rag',
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=5,
                created_at=now - timedelta(days=120),
            )
        )
        db.session.add(
            AIUsageEvent(
                organization_id=org_id,
                user_id=user_id,
                event='policy_draft',
                mode='deterministic',
                provider='local',
                model='deterministic',
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                latency_ms=5,
                created_at=now - timedelta(days=1),
            )
        )
        db.session.commit()

    runner = app.test_cli_runner()
    result = runner.invoke(args=['prune-ai-usage-events', '--days', '90', '--dry-run'])

    assert result.exit_code == 0
    assert 'Candidate rows: 1' in result.output

    with app.app_context():
        assert AIUsageEvent.query.count() == 2


def test_prune_ai_usage_events_deletes_old_rows(app):
    org_id, user_id = _seed_org_user(app)

    with app.app_context():
        now = datetime.now(timezone.utc)
        old_event = AIUsageEvent(
            organization_id=org_id,
            user_id=user_id,
            event='rag_query',
            mode='retrieval',
            provider='local',
            model='lexical-rag',
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=5,
            created_at=now - timedelta(days=120),
        )
        new_event = AIUsageEvent(
            organization_id=org_id,
            user_id=user_id,
            event='policy_draft',
            mode='deterministic',
            provider='local',
            model='deterministic',
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            latency_ms=5,
            created_at=now - timedelta(days=1),
        )
        db.session.add(old_event)
        db.session.add(new_event)
        db.session.commit()
        new_event_id = int(new_event.id)

    runner = app.test_cli_runner()
    result = runner.invoke(args=['prune-ai-usage-events', '--days', '90', '--yes'])

    assert result.exit_code == 0
    assert 'Deleted AI usage rows: 1' in result.output

    with app.app_context():
        remaining_ids = {int(row.id) for row in AIUsageEvent.query.all()}
        assert new_event_id in remaining_ids
        assert len(remaining_ids) == 1
