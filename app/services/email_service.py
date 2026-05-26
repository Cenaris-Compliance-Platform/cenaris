import logging
import os
from typing import Optional, List
from flask import current_app
from flask_mail import Message

from app import mail
from app.services.azure_acs_email import create_acs_email_service
from app.services.microsoft_oauth2_email import create_oauth2_email_service

logger = logging.getLogger(__name__)

class EmailService:
    """
    Centralized email service for Cenaris.
    Prioritizes Azure Communication Services (ACS), then Microsoft OAuth2, then SMTP.
    """

    def __init__(self):
        self._acs_service = None
        self._oauth2_service = None

    def _get_acs_service(self):
        if not self._acs_service:
            conn_str = os.environ.get('ACS_CONNECTION_STRING')
            sender = os.environ.get('ACS_SENDER_EMAIL')
            
            if not conn_str or not sender:
                current_app.logger.warning(f"ACS Email missing config: CONN_STR={'SET' if conn_str else 'MISSING'}, SENDER={'SET' if sender else 'MISSING'}")
                return None
                
            from app.services.azure_acs_email import AzureACSEmailService
            self._acs_service = AzureACSEmailService(conn_str, sender)
        return self._acs_service

    def _get_oauth2_service(self):
        if self._oauth2_service is None:
            self._oauth2_service = create_oauth2_email_service()
        return self._oauth2_service

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html_body: Optional[str] = None
    ) -> bool:
        """
        Send an email using the best available provider.
        """
        # Allow forcing provider via env var for safe cutover testing: 'auto'|'acs'|'oauth2'|'smtp'
        provider_pref = (os.environ.get('EMAIL_PROVIDER') or 'auto').strip().lower()
        if provider_pref not in {'auto', 'acs', 'oauth2', 'smtp'}:
            provider_pref = 'auto'
        # 1. Try Azure Communication Services (ACS)
        if provider_pref in {'auto', 'acs'}:
            acs = self._get_acs_service()
            if acs:
                logger.info(f"Attempting to send email to {to_email} via ACS")
                if acs.send_email(to_email, subject, body, body_html=html_body):
                    return True
                logger.warning("ACS email failed")
            else:
                logger.info("ACS not configured or unavailable")
            if provider_pref == 'acs':
                logger.info("EMAIL_PROVIDER=acs specified; not falling back")
                return False

        # 2. Try Microsoft OAuth2
        if provider_pref in {'auto', 'oauth2'}:
            oauth2 = self._get_oauth2_service()
            if oauth2:
                logger.info(f"Attempting to send email to {to_email} via Microsoft OAuth2")
                if oauth2.send_email(to_email, subject, body, body_html=html_body):
                    return True
                logger.warning("Microsoft OAuth2 email failed")
            else:
                logger.info("Microsoft OAuth2 not configured or unavailable")
            if provider_pref == 'oauth2':
                logger.info("EMAIL_PROVIDER=oauth2 specified; not falling back")
                return False

        # 3. Fallback to Flask-Mail (SMTP)
        if provider_pref in {'auto', 'smtp'}:
            return self._send_via_smtp(to_email, subject, body, html_body)
        logger.info("EMAIL_PROVIDER configured to skip SMTP fallback; email not sent")
        return False

    def _send_via_smtp(self, to_email: str, subject: str, body: str, html_body: Optional[str] = None) -> bool:
        """Fallback SMTP sender using Flask-Mail."""
        # Check if SMTP is configured
        has_server = bool(current_app.config.get('MAIL_SERVER'))
        has_sender = bool(current_app.config.get('MAIL_DEFAULT_SENDER'))
        if not (has_server and has_sender):
            logger.warning(f"SMTP not configured. Could not send email to {to_email}")
            # In development, we log the email content if no provider is available
            if current_app.debug or current_app.testing:
                logger.info(f"DEBUG EMAIL [To: {to_email}, Subject: {subject}]\nBody: {body}")
            return False

        try:
            msg = Message(
                subject=subject,
                recipients=[to_email],
                body=body,
                html=html_body
            )
            mail.send(msg)
            logger.info(f"Email sent successfully via SMTP to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email via SMTP to {to_email}: {e}")
            return False

# Global email service instance
email_service = EmailService()
