# Security and Authentication

## Overview
Cenaris uses organization-scoped authentication and permission checks to keep data isolated and to prevent one organization from seeing another organization’s records.

## Authentication Flow
### Browser Login
- Users sign in through the Flask auth flow.
- The session is managed by Flask-Login.
- The active user context is then tied to an organization.

### API Authentication
- The public API supports JWT bearer tokens.
- It also supports API keys for machine-to-machine usage.
- API keys are stored hashed, not in plaintext.

## Organization Isolation
- Most document, requirement, and reporting queries are filtered by organization ID.
- API access also checks the user’s organization membership.
- This prevents cross-tenant reads and writes.

## Authorization Controls
- Routes check permissions before privileged actions.
- Admin-only actions are restricted to users with the right organization permissions.
- The app checks roles and membership state before allowing operations.

## Security Measures Already Implemented
- Strong session and token handling.
- API key hashing at rest.
- JWT expiration and invalidation support.
- Rate limiting on sensitive endpoints.
- Webhook signature validation for outgoing events.
- Secure document download and preview checks.
- Blob and database access are scoped to the current organization.

## AI Review Specific Protections
- AI review results are conservative when text extraction is weak.
- Positive scores are reduced when evidence is missing or citations are absent.
- Irrelevant document detection helps block resumes and invoices from being treated like compliance evidence.
- Reviewer feedback is logged for later analysis.

## Public API Security
- `/api/v1` uses versioning.
- Authentication can be JWT or API key based.
- Tenant boundaries are enforced in the API layer.
- Rate limits reduce abuse and accidental overload.

## Operational Advice
- Keep the secret key private.
- Use HTTPS in deployment.
- Rotate API keys when needed.
- Watch for repeated 401, 403, and rate-limit events.
- Review feedback patterns to catch scoring weaknesses early.
