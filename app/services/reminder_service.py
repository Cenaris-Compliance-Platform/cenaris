from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable

from flask import current_app

from app import db
from app.models import ComplianceRequirement, Organization, RequirementReminder, User
from app.services.audit_log_service import audit_log_service
from app.services.notification_service import notification_service


class ReminderService:
    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _recipient_emails(self, reminder: RequirementReminder) -> list[str]:
        if reminder.recipient_user_id:
            user = db.session.get(User, int(reminder.recipient_user_id))
            if user and user.email:
                return [user.email]

        if reminder.recipient_email:
            return [reminder.recipient_email]

        return notification_service.org_admin_recipients(int(reminder.organization_id))

    def _format_due_label(self, requirement: ComplianceRequirement) -> str:
        raw = (getattr(requirement, 'review_frequency', None) or '').strip()
        return raw or 'Review schedule not specified'

    def send_due_reminders(self, *, organization_id: int | None = None, dry_run: bool = False) -> int:
        now = self._now()
        q = RequirementReminder.query.filter(
            RequirementReminder.is_active.is_(True),
            RequirementReminder.next_send_at.isnot(None),
            RequirementReminder.next_send_at <= now,
        )
        if organization_id is not None:
            q = q.filter(RequirementReminder.organization_id == int(organization_id))

        reminders = q.order_by(RequirementReminder.next_send_at.asc()).all()
        if not reminders:
            return 0

        sent_total = 0
        for reminder in reminders:
            requirement = db.session.get(ComplianceRequirement, int(reminder.requirement_id))
            organization = db.session.get(Organization, int(reminder.organization_id))
            if not requirement or not organization:
                continue

            recipients = self._recipient_emails(reminder)
            if not recipients:
                current_app.logger.info('No reminder recipients for org %s requirement %s', organization.id, requirement.id)
                continue

            requirement_label = (requirement.requirement_id or requirement.quality_indicator_code or 'Requirement').strip()
            subject = f'Cenaris Reminder: Review {requirement_label}'
            due_label = self._format_due_label(requirement)
            text_body = (
                f"This is a reminder to review evidence for {requirement_label} in {organization.name}.\n"
                f"Review cadence: {due_label}.\n"
            )
            html_body = (
                f"<p>This is a reminder to review evidence for <strong>{requirement_label}</strong> in {organization.name}.</p>"
                f"<p>Review cadence: {due_label}.</p>"
            )

            if not dry_run:
                for recipient in recipients:
                    notification_service.send_basic_email(
                        to_email=recipient,
                        subject=subject,
                        text_body=text_body,
                        html_body=html_body,
                    )

                notification_service.create_admin_notification(
                    organization_id=int(organization.id),
                    event_type='requirement_reminder',
                    title=f'Reminder sent for {requirement_label}',
                    message=text_body.strip(),
                    severity='info',
                    actor_user_id=reminder.created_by_user_id,
                    send_email=False,
                )

                reminder.last_sent_at = now
                reminder.next_send_at = now + timedelta(days=max(1, int(reminder.frequency_days)))
                db.session.commit()

                audit_log_service.record_event(
                    organization_id=int(organization.id),
                    event_type='reminder.sent',
                    actor_user_id=reminder.created_by_user_id,
                    entity_type='requirement_reminder',
                    entity_id=str(reminder.id),
                    message=f'Reminder sent for {requirement_label}',
                    payload={
                        'requirement_id': int(requirement.id),
                        'recipients': recipients,
                    },
                )

            sent_total += len(recipients)

        return sent_total


reminder_service = ReminderService()
