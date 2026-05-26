# Email Integration & Azure ACS Guide

## Overview
Cenaris uses a unified, production-grade email infrastructure managed through a centralized `EmailService`. This service acts as a provider-agnostic abstraction layer, ensuring high availability and zero downtime during provider transitions.

## 1. Provider Hierarchy (Automatic Fallback)
The `EmailService` automatically detects the best available provider in the following order:

1.  **Azure Communication Services (ACS)**: Primary production provider. Used if `ACS_CONNECTION_STRING` is set.
2.  **Microsoft 365 OAuth2**: Secondary fallback. Used if `MICROSOFT_SMTP_CLIENT_ID` is configured.
3.  **Flask-Mail (SMTP)**: Final fallback for local development or legacy SMTP relay.

## 2. Integrated Modules
The following modules have been refactored to use the new centralized email system:

### A. Authentication & User Management
*   **File**: `app/auth/routes.py`
*   **Actions**:
    *   **Password Resets**: Sends secure tokens to users for account recovery.
    *   **Email Verification**: Sends verification links to new signups.
    *   **Invitations**: Sends organization join requests to new team members.

### B. Notification Service
*   **File**: `app/services/notification_service.py`
*   **Actions**:
    *   **Admin Alerts**: Notifies administrators of important system events.
    *   **Monthly Digests**: Sends monthly compliance and activity summaries to organization owners.
    *   **Requirement Reminders**: Notifies users when compliance evidence reviews are due.

### C. System Alert Service
*   **File**: `app/services/alert_service.py`
*   **Actions**:
    *   **Critical Errors**: Immediate notification for database failures or service outages.
    *   **Security Breaches**: Alerts for suspicious login activity or unauthorized access attempts.

## 3. Azure ACS Implementation Details
The integration uses the `azure-communication-email` SDK and supports:
*   **Managed Domains**: Currently using an Azure-managed subdomain (`...azurecomm.net`) for zero-maintenance DNS.
*   **Connection String Auth**: Simplest setup for production reliability.
*   **Entra ID (Managed Identity)**: Ready for secret-free authentication in hardened environments.

## 4. Configuration Requirements
To maintain the integration, ensure the following environment variables are correctly set in the production `.env` or Azure App Settings:

```env
# Primary ACS Config
ACS_CONNECTION_STRING="endpoint=https://<resource>.communication.azure.com/;accesskey=<key>"
ACS_SENDER_EMAIL="DoNotReply@<your-managed-domain>.azurecomm.net"

# Fallback SMTP Config (Adam's M365)
MAIL_SERVER=smtp.office365.com
MAIL_PORT=587
MAIL_USERNAME=adam@cenaris.com.au
MAIL_PASSWORD=<app-password>
```

## 6. Staged Cutover / Provider Selection

Use the `EMAIL_PROVIDER` environment variable to control provider behavior during migration and testing:

- `EMAIL_PROVIDER=auto` (default): automatic selection with fallback ACS -> OAuth2 -> SMTP
- `EMAIL_PROVIDER=acs`: force ACS only (no fallback)
- `EMAIL_PROVIDER=oauth2`: force Microsoft OAuth2 only
- `EMAIL_PROVIDER=smtp`: force SMTP (Flask-Mail) only

Recommended staged approach:

1. Deploy these changes to staging with `EMAIL_PROVIDER=auto` and verify normal email flows.
2. Set `EMAIL_PROVIDER=acs` in staging and run `scripts/email_smoke_test.py` for each email type.
3. After 24–48 hours of monitoring, set `EMAIL_PROVIDER=acs` in production and test.
4. When confident, remove fallback providers and `Flask-Mail` dependency.

Always monitor App Service logs for `Email provider selection` and `Attempting to send email via ACS` messages during testing.

## 5. Testing & Verification
To verify the email system via the command line:
```powershell
flask shell
>>> from app.services.email_service import email_service
>>> email_service.send_email("test@example.com", "Cenaris System Test", "ACS is now online.")
```
