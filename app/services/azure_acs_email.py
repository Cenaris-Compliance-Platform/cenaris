import os
import logging
from typing import Optional
from azure.communication.email import EmailClient
from azure.identity import DefaultAzureCredential

logger = logging.getLogger(__name__)

class AzureACSEmailService:
    """Service for sending emails via Azure Communication Services (ACS)."""

    def __init__(
        self,
        connection_string: Optional[str] = None,
        endpoint: Optional[str] = None,
        sender_email: Optional[str] = None
    ):
        """
        Initialize ACS email service.

        Args:
            connection_string: ACS connection string (optional if using endpoint + identity)
            endpoint: ACS endpoint URL (e.g., https://<resource-name>.communication.azure.com/)
            sender_email: Verified sender email address in ACS
        """
        self.sender_email = sender_email or os.environ.get('ACS_SENDER_EMAIL')
        
        try:
            if connection_string:
                self.client = EmailClient.from_connection_string(connection_string)
            elif endpoint:
                # Use Managed Identity / DefaultAzureCredential
                self.client = EmailClient(endpoint, DefaultAzureCredential())
            else:
                # Try connection string from env
                conn_str = os.environ.get('ACS_CONNECTION_STRING')
                if conn_str:
                    self.client = EmailClient.from_connection_string(conn_str)
                else:
                    self.client = None
                    logger.warning("AzureACSEmailService: No connection string or endpoint provided.")
        except Exception as e:
            self.client = None
            logger.error(f"Failed to initialize AzureACSEmailService: {e}")

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        body_html: Optional[str] = None
    ) -> bool:
        """
        Send email using ACS.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text email body
            body_html: Optional HTML email body

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.client:
            logger.error("ACS Email client not initialized.")
            return False

        if not self.sender_email:
            logger.error("ACS Sender email not configured.")
            return False

        message = {
            "senderAddress": self.sender_email,
            "content": {
                "subject": subject,
                "plainText": body,
                "html": body_html if body_html else body
            },
            "recipients": {
                "to": [{"address": to_email}]
            }
        }

        try:
            poller = self.client.begin_send(message)
            result = poller.result()
            logger.info(f"Email sent successfully via ACS to {to_email}. Message ID: {result.get('messageId')}")
            return True
        except Exception as e:
            logger.exception(f"Failed to send email via ACS to {to_email}: {e}")
            return False

def create_acs_email_service() -> Optional[AzureACSEmailService]:
    """
    Factory function to create AzureACSEmailService from environment variables.
    """
    conn_str = os.environ.get('ACS_CONNECTION_STRING')
    endpoint = os.environ.get('ACS_ENDPOINT')
    sender_email = os.environ.get('ACS_SENDER_EMAIL')

    if not (conn_str or endpoint) or not sender_email:
        return None

    return AzureACSEmailService(
        connection_string=conn_str,
        endpoint=endpoint,
        sender_email=sender_email
    )
