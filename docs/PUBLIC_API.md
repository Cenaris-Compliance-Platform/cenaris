# Public API Guide

This document describes the Cenaris public API under `/api/v1`.

## Why This API Exists

The public API lets Cenaris integrate with external systems (portals, scripts, workflow tools) without browser automation.

Key reasons:
- Enable machine-to-machine access (API key + JWT)
- Support integration workflows for documents and reports
- Allow safe automation while keeping tenant boundaries (organization isolation)
- Provide stable versioned contracts (`/api/v1`) for future changes

## Base URL and Versioning

- Base path: `/api/v1`
- Version discovery: `GET /api/v1/versions`
- OpenAPI JSON: `GET /api/v1/docs/openapi.json`
- Swagger UI: `GET /api/v1/docs`

## Authentication

Supported methods:
- Bearer JWT (`Authorization: Bearer <token>`)
- API key (`X-API-Key: <secret>`)

### JWT Flow
1. `POST /api/v1/auth/login` with email/password to obtain `access_token` and `refresh_token`
2. Use `access_token` as Bearer token on API calls
3. Refresh expired access token via `POST /api/v1/auth/refresh`
4. Invalidate issued tokens via `POST /api/v1/auth/logout`

### API Key Flow
1. Create key using `POST /api/v1/api-keys`
2. Store returned `secret` safely (it is shown only once)
3. Send `X-API-Key` header on requests

## Tenant Isolation (Organization Safety)

The API is organization-scoped by design:
- JWT tokens are issued with an `org_id` claim.
- API keys are stored with a fixed `organization_id`.
- CRUD queries filter by `organization_id` before returning or mutating data.
- API key owner must still be active and have active membership in the same org.

This prevents cross-organization reads/writes when used correctly.

## Rate Limits

Examples:
- Login: `20 per minute`
- Refresh: `30 per minute`
- Upload: `60 per minute`

All API limits are enforced through Flask-Limiter per credential/IP key.

## Endpoint Summary

### Auth
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`

### Organizations
- `GET /api/v1/organizations`
- `POST /api/v1/organizations`
- `GET /api/v1/organizations/{org_id}`
- `PATCH /api/v1/organizations/{org_id}`
- `DELETE /api/v1/organizations/{org_id}`

### Documents
- `GET /api/v1/documents`
- `POST /api/v1/documents` (multipart form with `file`)
- `GET /api/v1/documents/{doc_id}`
- `PATCH /api/v1/documents/{doc_id}`
- `DELETE /api/v1/documents/{doc_id}`
- `GET /api/v1/documents/{doc_id}/download`

### Compliance
- `GET /api/v1/compliance/summary`

### Reports
- `GET /api/v1/reports/generate/{report_type}`
- Supported `report_type`: `gap-analysis`, `accreditation-plan`, `audit-pack`

### API Keys
- `GET /api/v1/api-keys`
- `POST /api/v1/api-keys`
- `DELETE /api/v1/api-keys/{key_id}`

### Webhooks
- `GET /api/v1/webhooks`
- `POST /api/v1/webhooks`
- `DELETE /api/v1/webhooks/{webhook_id}`
- `POST /api/v1/webhooks/{webhook_id}/test`

## Webhook Security

Outgoing webhook requests include:
- `X-Cenaris-Event`
- `X-Cenaris-Signature` (HMAC SHA256 of payload using endpoint secret)

Recommendations:
- Verify signatures on the receiver side
- Use HTTPS targets in non-debug environments
- Rotate webhook secrets when needed

## Security Considerations and Controls

Implemented controls:
- JWT expiration and session-version invalidation
- API key hashing at rest (no plaintext key storage)
- Permission checks before privileged operations
- Organization scoping on all business data queries
- Rate limiting and credential-aware limiter keys
- Webhook delivery logging for traceability

Operational recommendations:
- Keep `SECRET_KEY` strong and private
- Enable HTTPS everywhere in deployment
- Rotate API keys periodically
- Monitor repeated 401/403 and rate-limit events
- Limit API key creation to trusted admin users
