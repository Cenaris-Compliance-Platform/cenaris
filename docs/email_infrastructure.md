# Cenaris Email Infrastructure Guide

This document outlines the email implementation for the Cenaris platform, transitioning from legacy SMTP to a provider-agnostic system primarily powered by **Azure Communication Services (ACS)**.

## 1. Core Implementation
The email system is centralized in `app/services/email_service.py`. It uses a provider pattern that automatically detects the best available method:
1.  **Azure ACS**: Primary provider for production (Azure App Service).
2.  **Microsoft OAuth2**: Alternative provider for Outlook/Office365 accounts.
3.  **Legacy SMTP**: Fallback provider for local development or traditional mail servers.

### Key Files:
- `app/services/email_service.py`: Orchestrates provider selection.
- `app/services/azure_acs_email.py`: Handles direct integration with Azure ACS.
- `app/auth/routes.py`: Contains logic for user-facing emails (Password Reset, Signup).

## 2. Where Emails are Sent
The following features trigger email dispatch:

| Feature | Trigger Function | Template |
| :--- | :--- | :--- |
| **Password Reset** | `_send_password_reset_email` | `email/password_reset.html` |
| **Signup Verification**| `_send_email_verification_email`| `email/verify_email.html` |
| **System Alerts** | `alert_service.alert_critical_error`| Dynamic (HTML/Text) |
| **Admin Notifications**| `notification_service.send_email` | Dynamic (HTML/Text) |

## 3. Environment Configuration
For the live Azure environment, the following **Application Settings** must be configured:

| Variable | Description |
| :--- | :--- |
| `ACS_CONNECTION_STRING` | The full connection string from your Azure Communication Service resource. |
| `ACS_SENDER_EMAIL` | The verified sender address (e.g., `DoNotReply@...azurecomm.net`). |
| `TURNSTILE_SITE_KEY` | Cloudflare site key for CAPTCHA. |
| `TURNSTILE_SECRET_KEY` | Cloudflare secret key for backend validation. |

## 4. Security & Deliverability
- **CSP Headers**: Content Security Policy in `app/__init__.py` has been updated to allow `challenges.cloudflare.com` for Turnstile.
- **Spam Prevention**: To improve deliverability, ensure the **Display Name** is set in the Azure Portal under "Sender Usernames".
- **Local Dev**: On Windows local machines, background monitoring threads are disabled to prevent socket crashes (WinError 10038).

## 5. Troubleshooting
Check the **Azure Log Stream** for the following tags:
- `[INFO] Attempting to send email via ACS`: Confirms the service found your credentials.
- `[INFO] Email sent successfully`: Confirms Azure accepted the message.
- `[WARNING] MAIL configuration not found`: Indicates missing environment variables.
