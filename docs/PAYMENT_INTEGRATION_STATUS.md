# Payment Integration Status - Cenaris

Last updated: 2026-04-14
Environment: Stripe Test Mode + Azure App Service

## 1) What We Are Building

We are building a production-ready subscription billing system for Cenaris using Stripe, with:

- Plan-based subscriptions (Starter, Team, Scale, Enterprise)
- Stripe Checkout for starting subscriptions
- Stripe Billing Portal for self-service management
- Secure webhook processing for subscription lifecycle updates
- Server-side entitlement enforcement (feature gating by plan)
- Internal/super-admin bypass controls for testing and operations

Goal: Make billing automatic, auditable, and tied directly to platform feature access.

## 2) Architecture (Implemented)

- App: Flask + SQLAlchemy + Alembic migrations
- Payments: Stripe REST API via backend service layer
- Billing state source of truth: organization billing fields in DB, updated by webhook events
- Entitlements source: centralized resolver in billing service
- Deployment: Azure App Service (public webhook endpoint)

## 3) What Has Been Implemented

### 3.1 Data Model + DB

Completed:
- Added billing columns on organization record:
  - billing_plan_code
  - billing_status
  - stripe_customer_id
  - stripe_subscription_id
  - billing_current_period_start
  - billing_current_period_end
  - billing_trial_ends_at
  - billing_cancel_at_period_end
  - billing_internal_override
  - billing_demo_override_until
  - billing_last_event_id
  - billing_last_event_at
- Added webhook idempotency table:
  - stripe_billing_webhook_events
- Added migration merge to resolve multi-head state

Result:
- Schema and app models are aligned.

### 3.2 Stripe Service Layer

Completed:
- Plan normalization and alias support (including growth -> team)
- Plan catalog and metadata
- Feature minimum-plan map (entitlement rules)
- Checkout session creation
- Billing portal session creation
- Webhook signature verification (HMAC + timestamp tolerance)
- Webhook event application with idempotency persistence

Supported webhook events:
- checkout.session.completed
- customer.subscription.created
- customer.subscription.updated
- customer.subscription.deleted
- invoice.paid
- invoice.payment_failed

### 3.3 Routes + UI Integration

Completed:
- Billing routes:
  - checkout
  - portal
  - webhook
- Organization settings page billing controls and status
- Plans preview page redesign (modern card/toggle layout)
- Navbar lock/hide behavior based on entitlement state
- Feature/route gating for selected AI/analytics paths

### 3.4 Access Controls for Operations

Completed:
- Super-admin allowlist support
- Internal-team allowlist support
- Internal-team elevated access behavior for testing/support
- Demo/internal override controls in organization settings

### 3.5 Documentation

Completed:
- Client handoff setup document with exact Azure webhook/base URLs
- Exact Stripe event list and required key/ID checklist

## 4) What We Are Doing Right Now

Current step: Stripe dashboard and environment configuration finalization.

In progress:
- Confirming webhook destination and selected events in Stripe test mode
- Collecting/placing final Stripe credentials and price IDs in environment settings
- Performing end-to-end webhook delivery validation (expecting 2xx)

## 5) Progress Estimate

Overall payment integration progress: ~85%

Breakdown:
- Backend billing foundations: 100%
- Database/migrations: 100%
- Billing UI and controls: 95%
- Stripe dashboard setup (test mode): 85%
- End-to-end validation: 70%
- Live-mode cutover readiness: 40%

## 6) Status Check - Webhook Setup

Based on latest Stripe screenshots:
- Endpoint URL: Correct
- Event selection (6 required events): Correct
- Destination created and active: Correct
- Signing secret visible (whsec_...): Correct

No blocking mistake is visible in the shared screens.

## 7) Immediate Next Steps (Critical Path)

1. Put these values into Azure App Settings:
   - STRIPE_SECRET_KEY
   - STRIPE_WEBHOOK_SECRET
   - STRIPE_PRICE_ID_STARTER
   - STRIPE_PRICE_ID_TEAM
   - STRIPE_PRICE_ID_SCALE
   - STRIPE_PRICE_ID_ENTERPRISE
   - APP_BASE_URL

2. Restart Azure app after settings update.

3. Trigger Stripe test events and verify:
   - Stripe delivery status is 2xx
   - App DB/org billing status updates correctly
   - Plan-gated features unlock/lock correctly

4. Run focused tests for admin notifications + billing-related flows.

## 8) Broader Plan For Complete Payment Integration

### Phase A - Finalize Test Mode (now)
- Complete webhook + checkout + portal test cycle
- Validate failed-payment and canceled-subscription behavior
- Verify idempotency by replaying an event safely

### Phase B - Operational Hardening
- Add billing audit views/admin diagnostics
- Add alerts for webhook failures and repeated delivery errors
- Add reconciliation command/report for Stripe vs DB state

### Phase C - Full Entitlement Coverage
- Extend plan gates to every feature in matrix
- Add explicit UX messaging for locked capabilities
- Add plan-upgrade CTA pathways from locked screens

### Phase D - Live Mode Go-Live
- Create live products/prices and live webhook destination
- Configure live keys securely in Azure
- Execute smoke test with controlled real billing scenario
- Enable support runbook and rollback procedures

### Phase E - Post-Go-Live Optimization
- Subscription analytics dashboards
- Churn/failure recovery flows (dunning tuning)
- Pricing experiments and growth instrumentation

## 9) Risks and Controls

Key risks:
- Misconfigured environment variable values
- Wrong price IDs mapped to plan codes
- Webhook delivery failures not noticed quickly
- Drift between Stripe state and local DB state

Mitigations:
- Use strict key checklist and peer verification
- Run end-to-end scenario tests per plan
- Add monitoring/alerts for failed webhook deliveries
- Periodic reconciliation job/report

## 10) Definition of Done (Integration)

Payment integration is considered complete when:
- All required Stripe settings are configured in test and live environments
- Checkout, webhook, and portal flows pass end-to-end
- Billing status correctly drives entitlement gates
- Operational monitoring and runbook are in place
- Team sign-off is completed for go-live
