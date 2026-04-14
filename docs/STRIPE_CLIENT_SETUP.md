# Stripe Billing Setup (Client Handoff)

Purpose: complete Stripe setup and send back the exact keys/IDs required by Cenaris.

Important:
- Start in Stripe **Test mode** first.
- Do not share screenshots of secret keys. Share the values as text securely.

## 1) Exact URLs To Use

Use these exact values:

- Webhook URL (Azure):
  `https://cenaris-dev-aue-app-hbhradhzf6aaabgp.australiaeast-01.azurewebsites.net/billing/webhook`

- APP_BASE_URL (Azure):
  `https://cenaris-dev-aue-app-hbhradhzf6aaabgp.australiaeast-01.azurewebsites.net`

Local URL is only for developer machines and is not used by Stripe cloud callbacks:
- `http://localhost:8080/billing/webhook`

## 2) Create Products And Prices In Stripe

Currency: AUD

Create these products and recurring prices:

1. `Cenaris Starter`
	- Monthly: A$149
	- Yearly: A$1,430

2. `Cenaris Team`
	- Monthly: A$349
	- Yearly: A$3,350

3. `Cenaris Scale`
	- Monthly: A$699
	- Yearly: A$6,710

4. `Cenaris Enterprise`
	- Monthly: A$1,499
	- Yearly: A$14,390

Optional add-on pricing reference:
- Additional framework: A$99/month (Enterprise: A$79/month)

## 3) Create Webhook In Stripe

In Stripe Dashboard:

1. Go to Developers -> Webhooks -> Add endpoint
2. Endpoint URL:
	`https://cenaris-dev-aue-app-hbhradhzf6aaabgp.australiaeast-01.azurewebsites.net/billing/webhook`
3. Select these events:
	- `checkout.session.completed`
	- `customer.subscription.created`
	- `customer.subscription.updated`
	- `customer.subscription.deleted`
	- `invoice.paid`
	- `invoice.payment_failed`
4. Save and copy the Signing secret

This signing secret is required as:
- `STRIPE_WEBHOOK_SECRET`

## 4) Keys/IDs You Must Send Back

Please send these exact values:

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_PRICE_ID_STARTER`
- `STRIPE_PRICE_ID_TEAM`
- `STRIPE_PRICE_ID_SCALE`
- `STRIPE_PRICE_ID_ENTERPRISE`
- `APP_BASE_URL`

Optional backward-compatibility key:
- `STRIPE_PRICE_ID_GROWTH` (maps to Team)

## 5) Test-Mode Sandbox Plans (Recommended)

For quick low-risk testing in Stripe **Test mode only**:

- `Sandbox Free` at A$0/month
- `Sandbox Smoke` at A$1/month

Do not add these sandbox plans in live mode.

## 6) Copy/Paste Response Template For Client

Please fill and return:

```text
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_ID_STARTER=
STRIPE_PRICE_ID_TEAM=
STRIPE_PRICE_ID_SCALE=
STRIPE_PRICE_ID_ENTERPRISE=
APP_BASE_URL=https://cenaris-dev-aue-app-hbhradhzf6aaabgp.australiaeast-01.azurewebsites.net

# Optional
STRIPE_PRICE_ID_GROWTH=
```

## 7) Final Validation After Configuration

1. Complete one checkout in Stripe Test mode.
2. Confirm webhook event is delivered successfully (2xx) in Stripe event logs.
3. Confirm Cenaris updates subscription status and plan access.
