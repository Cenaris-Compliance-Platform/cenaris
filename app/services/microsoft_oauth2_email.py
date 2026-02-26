"""
Microsoft 365 OAuth2 SMTP Authentication Service

This module handles OAuth2 token acquisition for sending emails through Microsoft 365 SMTP
when modern authentication is enabled (which blocks app passwords).

Requires:
    - Azure AD app registration with Mail.Send permission
    - Service principal created in Exchange Online
    - Mailbox permission granted to the app
"""

import os
import logging
import smtplib
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

import msal


logger = logging.getLogger(__name__)


class MicrosoftOAuth2EmailService:
    """Service for sending emails via Microsoft 365 SMTP with OAuth2 authentication."""
    
    # Microsoft 365 OAuth2 endpoints
    AUTHORITY_URL = "https://login.microsoftonline.com/{tenant_id}"
    SCOPE = ["https://outlook.office365.com/.default"]
    SMTP_SERVER = "smtp.office365.com"
    SMTP_PORT = 587
    
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        sender_email: str
    ):
        """
        Initialize OAuth2 email service.
        
        Args:
            client_id: Azure AD application (client) ID
            client_secret: Azure AD client secret
            tenant_id: Azure AD directory (tenant) ID
            sender_email: Email address to send from (e.g., adam@cenaris.com.au)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.sender_email = sender_email
        self.authority = self.AUTHORITY_URL.format(tenant_id=tenant_id)
        
        # Create MSAL confidential client app
        self.app = msal.ConfidentialClientApplication(
            client_id=self.client_id,
            client_credential=self.client_secret,
            authority=self.authority
        )
    
    def _acquire_token(self) -> Optional[str]:
        """
        Acquire OAuth2 access token from Microsoft Identity Platform.
        
        Returns:
            Access token string, or None if acquisition failed
        """
        try:
            # Try to get token from cache first
            result = self.app.acquire_token_silent(self.SCOPE, account=None)
            
            # If no cached token, acquire new one
            if not result:
                logger.info("No cached OAuth2 token found, acquiring new token...")
                result = self.app.acquire_token_for_client(scopes=self.SCOPE)
            
            if "access_token" in result:
                logger.info("OAuth2 token acquired successfully")
                return result["access_token"]
            else:
                error = result.get("error")
                error_description = result.get("error_description")
                logger.error(
                    "Failed to acquire OAuth2 token: %s - %s",
                    error,
                    error_description
                )
                return None
                
        except Exception as e:
            logger.exception("Exception while acquiring OAuth2 token: %s", e)
            return None
    
    def _generate_oauth2_string(self, username: str, access_token: str) -> str:
        """
        Generate OAuth2 authentication string for SMTP.
        
        Args:
            username: Email address (e.g., adam@cenaris.com.au)
            access_token: OAuth2 access token
        
        Returns:
            Base64-encoded OAuth2 auth string
        """
        auth_string = f"user={username}\x01auth=Bearer {access_token}\x01\x01"
        return base64.b64encode(auth_string.encode()).decode()
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        body_html: Optional[str] = None
    ) -> bool:
        """
        Send email using Microsoft 365 SMTP with OAuth2 authentication.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Plain text email body
            body_html: Optional HTML email body
        
        Returns:
            True if email sent successfully, False otherwise
        """
        # Acquire OAuth2 access token
        access_token = self._acquire_token()
        if not access_token:
            logger.error("Cannot send email: Failed to acquire OAuth2 token")
            return False
        
        # Create email message
        if body_html:
            msg = MIMEMultipart('alternative')
            msg.attach(MIMEText(body, 'plain'))
            msg.attach(MIMEText(body_html, 'html'))
        else:
            msg = MIMEText(body, 'plain')
        
        msg['Subject'] = subject
        msg['From'] = self.sender_email
        msg['To'] = to_email
        
        # Generate OAuth2 auth string
        oauth2_string = self._generate_oauth2_string(self.sender_email, access_token)
        
        # Send via SMTP with OAuth2
        try:
            with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT) as server:
                server.set_debuglevel(0)  # Set to 1 for debug output
                server.ehlo()
                server.starttls()
                server.ehlo()
                
                # Authenticate with OAuth2
                server.docmd('AUTH', 'XOAUTH2 ' + oauth2_string)
                
                # Send email
                server.send_message(msg)
                
            logger.info("Email sent successfully via OAuth2 to %s", to_email)
            return True
            
        except smtplib.SMTPAuthenticationError as e:
            logger.error("OAuth2 SMTP authentication failed: %s", e)
            return False
        except smtplib.SMTPException as e:
            logger.error("SMTP error while sending email: %s", e)
            return False
        except Exception as e:
            logger.exception("Unexpected error sending email via OAuth2: %s", e)
            return False


def create_oauth2_email_service() -> Optional[MicrosoftOAuth2EmailService]:
    """
    Factory function to create OAuth2 email service from environment variables.
    
    Environment variables required:
        - MICROSOFT_SMTP_CLIENT_ID: Azure AD application (client) ID
        - MICROSOFT_SMTP_CLIENT_SECRET: Azure AD client secret
        - MICROSOFT_SMTP_TENANT_ID: Azure AD directory (tenant) ID
        - MAIL_USERNAME: Sender email address (e.g., adam@cenaris.com.au)
    
    Returns:
        Configured MicrosoftOAuth2EmailService instance, or None if config missing
    """
    client_id = os.environ.get('MICROSOFT_SMTP_CLIENT_ID')
    client_secret = os.environ.get('MICROSOFT_SMTP_CLIENT_SECRET')
    tenant_id = os.environ.get('MICROSOFT_SMTP_TENANT_ID')
    sender_email = os.environ.get('MAIL_USERNAME')
    
    if not all([client_id, client_secret, tenant_id, sender_email]):
        logger.warning(
            "OAuth2 email service not configured. Missing environment variables: "
            "MICROSOFT_SMTP_CLIENT_ID, MICROSOFT_SMTP_CLIENT_SECRET, "
            "MICROSOFT_SMTP_TENANT_ID, or MAIL_USERNAME"
        )
        return None
    
    return MicrosoftOAuth2EmailService(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
        sender_email=sender_email
    )
