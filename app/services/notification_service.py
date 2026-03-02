from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import current_app, render_template, url_for
from flask_mail import Message

from app import db, mail
from app.models import AdminNotification, Organization, OrganizationMembership, User
from app.services.microsoft_oauth2_email import create_oauth2_email_service


class NotificationService:
    ALLOWED_SEVERITIES = {'info', 'warning', 'critical'}

    def create_admin_notification(
        self,
        *,
        organization_id: int,
        event_type: str,
        title: str,
        message: str,
        severity: str = 'info',
        actor_user_id: int | None = None,
        link_url: str | None = None,
        payload: dict | None = None,
        send_email: bool = False,
    ) -> AdminNotification:
        normalized_severity = (severity or 'info').strip().lower()
        if normalized_severity not in self.ALLOWED_SEVERITIES:
            normalized_severity = 'info'

        notification = AdminNotification(
            organization_id=int(organization_id),
            actor_user_id=int(actor_user_id) if actor_user_id else None,
            event_type=(event_type or '').strip() or 'system_event',
            title=(title or '').strip() or 'System notification',
            message=(message or '').strip() or 'An event occurred.',
            severity=normalized_severity,
            link_url=(link_url or '').strip() or None,
            payload_json=json.dumps(payload or {}, ensure_ascii=False),
            is_read=False,
        )

        db.session.add(notification)
        db.session.commit()

        if send_email:
            try:
                self.send_notification_email_to_org_admins(notification)
                notification.email_sent_at = datetime.now(timezone.utc)
                db.session.commit()
            except Exception:
                db.session.rollback()
                current_app.logger.exception('Failed sending notification email for notification %s', notification.id)

        return notification

    def list_admin_notifications(self, *, organization_id: int, unread_only: bool = False, limit: int = 100) -> list[AdminNotification]:
        q = AdminNotification.query.filter_by(organization_id=int(organization_id)).order_by(AdminNotification.created_at.desc())
        if unread_only:
            q = q.filter(AdminNotification.is_read.is_(False))
        return q.limit(max(1, min(int(limit), 500))).all()

    def unread_count(self, *, organization_id: int) -> int:
        return int(
            AdminNotification.query.filter_by(organization_id=int(organization_id), is_read=False).count()
        )

    def mark_read(self, *, notification_id: int, user_id: int, organization_id: int) -> bool:
        notification = AdminNotification.query.filter_by(
            id=int(notification_id),
            organization_id=int(organization_id),
        ).first()
        if not notification:
            return False
        if notification.is_read:
            return True

        notification.is_read = True
        notification.read_at = datetime.now(timezone.utc)
        notification.read_by_user_id = int(user_id)
        db.session.commit()
        return True

    def mark_all_read(self, *, organization_id: int, user_id: int) -> int:
        notifications = AdminNotification.query.filter_by(
            organization_id=int(organization_id),
            is_read=False,
        ).all()
        now = datetime.now(timezone.utc)
        for n in notifications:
            n.is_read = True
            n.read_at = now
            n.read_by_user_id = int(user_id)

        db.session.commit()
        return len(notifications)

    def build_monthly_summary(self, *, organization_id: int, year: int, month: int) -> dict:
        from calendar import monthrange

        start = datetime(int(year), int(month), 1, tzinfo=timezone.utc)
        day_count = monthrange(int(year), int(month))[1]
        end = datetime(int(year), int(month), int(day_count), 23, 59, 59, tzinfo=timezone.utc)

        rows = (
            AdminNotification.query
            .filter(AdminNotification.organization_id == int(organization_id))
            .filter(AdminNotification.created_at >= start)
            .filter(AdminNotification.created_at <= end)
            .order_by(AdminNotification.created_at.desc())
            .all()
        )

        severity_counts = {'critical': 0, 'warning': 0, 'info': 0}
        event_counts: dict[str, int] = {}
        for row in rows:
            sev = (row.severity or 'info').strip().lower()
            severity_counts[sev] = int(severity_counts.get(sev, 0)) + 1
            key = (row.event_type or 'system_event').strip() or 'system_event'
            event_counts[key] = int(event_counts.get(key, 0)) + 1

        top_events = sorted(event_counts.items(), key=lambda pair: pair[1], reverse=True)[:5]

        return {
            'year': int(year),
            'month': int(month),
            'total': len(rows),
            'severity_counts': severity_counts,
            'top_events': top_events,
            'recent': rows[:10],
        }

    def send_monthly_digest(self, *, organization_id: int, year: int, month: int) -> int:
        summary = self.build_monthly_summary(organization_id=int(organization_id), year=int(year), month=int(month))
        recipients = self._monthly_digest_recipients(int(organization_id))
        if not recipients:
            return 0

        subject = f'Cenaris Monthly Notification Summary ({year}-{str(month).zfill(2)})'
        text_body = (
            f"Monthly notification summary for {year}-{str(month).zfill(2)}\n\n"
            f"Total events: {summary['total']}\n"
            f"Critical: {summary['severity_counts'].get('critical', 0)}\n"
            f"Warning: {summary['severity_counts'].get('warning', 0)}\n"
            f"Info: {summary['severity_counts'].get('info', 0)}\n"
        )
        html_body = render_template('email/monthly_notifications_digest.html', summary=summary)

        sent = 0
        for recipient in recipients:
            if self._send_email_html(recipient, subject, text_body, html_body):
                sent += 1

        return sent

    def send_monthly_report_setup_confirmation(self, *, recipient_email: str, organization_name: str) -> bool:
        recipient = (recipient_email or '').strip()
        if not recipient:
            return False

        org_name = (organization_name or '').strip() or 'your organisation'
        manage_settings_url = None
        try:
            manage_settings_url = url_for('main.organization_settings', _external=True)
        except Exception:
            manage_settings_url = None

        subject = 'Cenaris Monthly Report Delivery Enabled'
        text_body = (
            f"Hi,\n\n"
            f"This email confirms that monthly report delivery has been set up for {org_name} in Cenaris.\n"
            f"You will receive monthly reports at this email address.\n"
            f"Manage settings: {manage_settings_url}\n\n" if manage_settings_url else
            f"You will receive monthly reports at this email address.\n\n"
            f"If this was not expected, please contact your organisation admin."
        )
        html_body = render_template(
            'email/monthly_report_setup_confirmation.html',
            organization_name=org_name,
            recipient_email=recipient,
            manage_settings_url=manage_settings_url,
        )

        return bool(self._send_email_html(recipient, subject, text_body, html_body))

    def _monthly_digest_recipients(self, organization_id: int) -> list[str]:
        organization = db.session.get(Organization, int(organization_id))
        if not organization or not bool(getattr(organization, 'monthly_report_enabled', False)):
            return []

        recipient = (getattr(organization, 'monthly_report_recipient_email', '') or '').strip()
        if not recipient:
            current_app.logger.info(
                'Monthly digest is enabled for org %s but no recipient email is configured.',
                int(organization_id),
            )
            return []

        return [recipient]

    def send_notification_email_to_org_admins(self, notification: AdminNotification) -> int:
        recipients = self._org_admin_recipients(int(notification.organization_id))
        if not recipients:
            return 0

        subject = f'Cenaris Alert: {notification.title}'
        text_body = notification.message
        html_body = (
            f'<p><strong>{notification.title}</strong></p>'
            f'<p>{notification.message}</p>'
            f'<p>Severity: {(notification.severity or "info").upper()}</p>'
        )

        sent = 0
        for recipient in recipients:
            if self._send_email_html(recipient, subject, text_body, html_body):
                sent += 1

        return sent

    def _org_admin_recipients(self, organization_id: int) -> list[str]:
        memberships = (
            OrganizationMembership.query
            .filter_by(organization_id=int(organization_id), is_active=True)
            .all()
        )

        recipients: list[str] = []
        for membership in memberships:
            if not membership.user_id:
                continue
            user = db.session.get(User, int(membership.user_id))
            if not user or not user.email:
                continue
            if user.has_permission('users.manage', org_id=int(organization_id)):
                recipients.append((user.email or '').strip())

        deduped: list[str] = []
        seen: set[str] = set()
        for email in recipients:
            key = email.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(email)
        return deduped

    def _send_email_html(self, to_email: str, subject: str, body: str, html: str) -> bool:
        oauth2_service = create_oauth2_email_service()
        if oauth2_service:
            try:
                return bool(oauth2_service.send_email(to_email, subject, body, body_html=html))
            except Exception:
                current_app.logger.exception('OAuth2 email send failed for %s', to_email)

        has_server = bool(current_app.config.get('MAIL_SERVER'))
        has_sender = bool(current_app.config.get('MAIL_DEFAULT_SENDER'))
        has_username = bool(current_app.config.get('MAIL_USERNAME'))
        has_password = bool(current_app.config.get('MAIL_PASSWORD'))
        if not (has_server and has_sender and has_username and has_password):
            current_app.logger.info('MAIL not configured; skipping notification email to %s', to_email)
            return False

        try:
            msg = Message(subject=subject, recipients=[to_email], body=body, html=html)
            mail.send(msg)
            return True
        except Exception:
            current_app.logger.exception('SMTP email send failed for %s', to_email)
            return False


notification_service = NotificationService()
