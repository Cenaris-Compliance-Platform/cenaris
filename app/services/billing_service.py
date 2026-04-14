from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import datetime, timezone
from typing import Any

import requests
from flask import current_app

from app import db
from app.models import Organization, StripeBillingWebhookEvent


class BillingService:
    PLAN_CODES = {'starter', 'team', 'scale', 'enterprise'}
    PLAN_ALIASES = {
        'growth': 'team',
    }
    PLAN_RANK = {
        'starter': 1,
        'team': 2,
        'scale': 3,
        'enterprise': 4,
    }
    FEATURE_MIN_PLAN = {
        'task_workflow': 'team',
        'risk_register': 'team',
        'multi_site_reporting': 'scale',
        'ai_tagging': 'scale',
        'regulatory_updates': 'scale',
        'sso_api': 'enterprise',
    }

    def _email_set(self, config_key: str, default_csv: str) -> set[str]:
        raw = (current_app.config.get(config_key) or default_csv or '').strip()
        values = [item.strip().lower() for item in raw.split(',') if item.strip()]
        return set(values)

    def is_super_admin_email(self, email: str | None) -> bool:
        e = (email or '').strip().lower()
        if not e:
            return False
        emails = self._email_set('SUPER_ADMIN_EMAILS', 'muhammadhaiderali2710@gmail.com')
        return e in emails

    def is_internal_team_email(self, email: str | None) -> bool:
        e = (email or '').strip().lower()
        if not e:
            return False
        emails = self._email_set('INTERNAL_TEAM_EMAILS', 'muhammadhaideraliroy2710@gmail.com')
        return e in emails

    def normalize_plan_code(self, plan_code: str | None) -> str:
        raw = (plan_code or '').strip().lower()
        raw = self.PLAN_ALIASES.get(raw, raw)
        return raw if raw in self.PLAN_CODES else 'starter'

    def plan_meets_minimum(self, plan_code: str | None, minimum_plan_code: str | None) -> bool:
        plan = self.normalize_plan_code(plan_code)
        minimum = self.normalize_plan_code(minimum_plan_code)
        return int(self.PLAN_RANK.get(plan, 0)) >= int(self.PLAN_RANK.get(minimum, 0))

    def has_feature(self, plan_code: str | None, feature_key: str) -> bool:
        feature = (feature_key or '').strip().lower()
        minimum = self.FEATURE_MIN_PLAN.get(feature)
        if not minimum:
            return True
        return self.plan_meets_minimum(plan_code, minimum)

    def _now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def _safe_dt(self, unix_ts: Any) -> datetime | None:
        try:
            ts = int(unix_ts)
            if ts <= 0:
                return None
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except Exception:
            return None

    def _base_url(self) -> str:
        configured = (current_app.config.get('APP_BASE_URL') or '').strip()
        if configured:
            return configured.rstrip('/')
        try:
            from flask import request

            return request.host_url.rstrip('/')
        except Exception:
            return ''

    def _stripe_secret_key(self) -> str:
        return (current_app.config.get('STRIPE_SECRET_KEY') or '').strip()

    def _webhook_secret(self) -> str:
        return (current_app.config.get('STRIPE_WEBHOOK_SECRET') or '').strip()

    def _price_id_for_plan(self, plan_code: str) -> str:
        plan = self.normalize_plan_code(plan_code)
        key_map = {
            'starter': 'STRIPE_PRICE_ID_STARTER',
            'team': 'STRIPE_PRICE_ID_TEAM',
            'scale': 'STRIPE_PRICE_ID_SCALE',
            'enterprise': 'STRIPE_PRICE_ID_ENTERPRISE',
        }
        config_key = key_map.get(plan)
        if not config_key:
            return ''
        value = (current_app.config.get(config_key) or '').strip()
        # Backward compatibility with earlier naming before Team/Scale split.
        if plan == 'team' and not value:
            value = (current_app.config.get('STRIPE_PRICE_ID_GROWTH') or '').strip()
        return value

    def stripe_enabled(self) -> bool:
        return bool(self._stripe_secret_key())

    def plan_catalog(self) -> dict[str, dict[str, Any]]:
        return {
            'starter': {
                'label': 'Starter',
                'description': 'Core compliance workflow for early teams.',
                'stripe_price_id_config': 'STRIPE_PRICE_ID_STARTER',
                'price_monthly_aud': 149,
                'price_annual_aud': 1430,
            },
            'team': {
                'label': 'Team',
                'description': 'Collaboration and governance upgrades for scaling teams.',
                'stripe_price_id_config': 'STRIPE_PRICE_ID_TEAM (or STRIPE_PRICE_ID_GROWTH)',
                'price_monthly_aud': 349,
                'price_annual_aud': 3350,
            },
            'scale': {
                'label': 'Scale',
                'description': 'Operational scale features including advanced reporting and AI tagging.',
                'stripe_price_id_config': 'STRIPE_PRICE_ID_SCALE',
                'price_monthly_aud': 699,
                'price_annual_aud': 6710,
            },
            'enterprise': {
                'label': 'Enterprise',
                'description': 'Advanced controls and integrations for complex organizations.',
                'stripe_price_id_config': 'STRIPE_PRICE_ID_ENTERPRISE',
                'price_monthly_aud': 1499,
                'price_annual_aud': 14390,
            },
        }

    def resolve_entitlements(self, organization: Organization, *, actor_email: str | None = None) -> dict[str, Any]:
        now = self._now_utc()
        internal_override = bool(getattr(organization, 'billing_internal_override', False))
        demo_until = getattr(organization, 'billing_demo_override_until', None)
        demo_override_active = bool(demo_until and demo_until >= now)
        internal_team = self.is_internal_team_email(actor_email)

        billing_status = ((getattr(organization, 'billing_status', None) or '').strip().lower())
        subscription_ok = billing_status in {'active', 'trialing'}

        source = 'subscription' if subscription_ok else 'none'
        has_access = subscription_ok

        if internal_team:
            source = 'internal_team'
            has_access = True
        elif internal_override:
            source = 'internal_override'
            has_access = True
        elif demo_override_active:
            source = 'demo_override'
            has_access = True

        plan_code_raw = (
            (getattr(organization, 'billing_plan_code', None) or '').strip().lower()
            or (getattr(organization, 'subscription_tier', None) or '').strip().lower()
        )
        plan_code = self.normalize_plan_code(plan_code_raw)
        if internal_team and not (plan_code in {'team', 'scale', 'enterprise'}):
            plan_code = 'enterprise'

        feature_access = {
            key: self.has_feature(plan_code, key)
            for key in self.FEATURE_MIN_PLAN.keys()
        }

        return {
            'plan_code': plan_code,
            'plan_label': plan_code.capitalize(),
            'has_access': bool(has_access),
            'source': source,
            'billing_status': billing_status or 'inactive',
            'stripe_enabled': self.stripe_enabled(),
            'internal_override': internal_override,
            'internal_team': internal_team,
            'demo_override_active': demo_override_active,
            'demo_override_until': demo_until,
            'cancel_at_period_end': bool(getattr(organization, 'billing_cancel_at_period_end', False)),
            'current_period_end': getattr(organization, 'billing_current_period_end', None),
            'trial_ends_at': getattr(organization, 'billing_trial_ends_at', None),
            'customer_id': getattr(organization, 'stripe_customer_id', None),
            'subscription_id': getattr(organization, 'stripe_subscription_id', None),
            'feature_access': feature_access,
        }

    def _stripe_request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        secret = self._stripe_secret_key()
        if not secret:
            raise RuntimeError('Stripe is not configured.')

        response = requests.request(
            method=method,
            url=f'https://api.stripe.com/v1/{path.lstrip("/")}',
            headers={'Authorization': f'Bearer {secret}'},
            data=payload,
            timeout=20,
        )

        if response.status_code >= 400:
            current_app.logger.error('Stripe API error %s: %s', response.status_code, response.text[:500])
            raise RuntimeError('Stripe API request failed.')

        try:
            return response.json() or {}
        except Exception as exc:
            raise RuntimeError('Invalid response from Stripe API.') from exc

    def _ensure_customer(self, organization: Organization) -> str:
        existing = (getattr(organization, 'stripe_customer_id', None) or '').strip()
        if existing:
            return existing

        email = (getattr(organization, 'billing_email', None) or getattr(organization, 'contact_email', None) or '').strip()
        payload: dict[str, Any] = {
            'name': (organization.name or '').strip() or f'Organization {organization.id}',
            'metadata[org_id]': str(int(organization.id)),
        }
        if email:
            payload['email'] = email

        customer = self._stripe_request('POST', 'customers', payload)
        customer_id = (customer.get('id') or '').strip()
        if not customer_id:
            raise RuntimeError('Stripe customer creation failed.')

        organization.stripe_customer_id = customer_id
        db.session.commit()
        return customer_id

    def create_checkout_session(self, organization: Organization, *, plan_code: str) -> str:
        normalized_plan = self.normalize_plan_code(plan_code)
        if normalized_plan not in self.PLAN_CODES:
            raise ValueError('Unsupported plan code.')

        price_id = self._price_id_for_plan(normalized_plan)
        if not price_id:
            raise RuntimeError(f'Stripe price ID is missing for plan: {normalized_plan}.')

        customer_id = self._ensure_customer(organization)
        base_url = self._base_url()
        if not base_url:
            raise RuntimeError('Could not determine application base URL for Stripe redirect.')

        payload = {
            'mode': 'subscription',
            'customer': customer_id,
            'line_items[0][price]': price_id,
            'line_items[0][quantity]': '1',
            'metadata[org_id]': str(int(organization.id)),
            'metadata[plan_code]': normalized_plan,
            'subscription_data[metadata][org_id]': str(int(organization.id)),
            'subscription_data[metadata][plan_code]': normalized_plan,
            'success_url': f'{base_url}/organization/settings?billing=success',
            'cancel_url': f'{base_url}/organization/settings?billing=cancelled',
        }

        session_data = self._stripe_request('POST', 'checkout/sessions', payload)
        checkout_url = (session_data.get('url') or '').strip()
        if not checkout_url:
            raise RuntimeError('Stripe checkout URL was not returned.')

        return checkout_url

    def create_portal_session(self, organization: Organization) -> str:
        if not (getattr(organization, 'stripe_customer_id', None) or '').strip():
            raise RuntimeError('No Stripe customer found for this organization.')

        base_url = self._base_url()
        if not base_url:
            raise RuntimeError('Could not determine application base URL for Stripe redirect.')

        payload = {
            'customer': organization.stripe_customer_id,
            'return_url': f'{base_url}/organization/settings',
        }
        session_data = self._stripe_request('POST', 'billing_portal/sessions', payload)
        portal_url = (session_data.get('url') or '').strip()
        if not portal_url:
            raise RuntimeError('Stripe portal URL was not returned.')

        return portal_url

    def verify_webhook(self, payload: bytes, signature_header: str | None) -> dict[str, Any]:
        secret = self._webhook_secret()
        if not secret:
            raise RuntimeError('Stripe webhook secret is not configured.')

        header = (signature_header or '').strip()
        if not header:
            raise ValueError('Missing Stripe-Signature header.')

        parts = [part.strip() for part in header.split(',') if part.strip()]
        values: dict[str, list[str]] = {}
        for part in parts:
            if '=' not in part:
                continue
            k, v = part.split('=', 1)
            values.setdefault(k.strip(), []).append(v.strip())

        timestamps = values.get('t') or []
        signatures = values.get('v1') or []
        if not timestamps or not signatures:
            raise ValueError('Invalid Stripe-Signature format.')

        timestamp = timestamps[0]
        signed_payload = f'{timestamp}.{payload.decode("utf-8")}'
        expected = hmac.new(
            key=secret.encode('utf-8'),
            msg=signed_payload.encode('utf-8'),
            digestmod=hashlib.sha256,
        ).hexdigest()

        if not any(hmac.compare_digest(expected, sig) for sig in signatures):
            raise ValueError('Invalid Stripe signature.')

        try:
            ts = int(timestamp)
        except Exception as exc:
            raise ValueError('Invalid Stripe signature timestamp.') from exc

        tolerance_seconds = int(current_app.config.get('STRIPE_WEBHOOK_TOLERANCE_SECONDS') or 300)
        if abs(int(time.time()) - ts) > max(30, tolerance_seconds):
            raise ValueError('Stripe webhook timestamp is outside tolerance.')

        try:
            event = json.loads(payload.decode('utf-8'))
        except Exception as exc:
            raise ValueError('Webhook payload is not valid JSON.') from exc

        if not isinstance(event, dict):
            raise ValueError('Webhook payload must be a JSON object.')
        return event

    def _extract_org_from_event_object(self, obj: dict[str, Any]) -> Organization | None:
        metadata = obj.get('metadata') if isinstance(obj.get('metadata'), dict) else {}
        org_id_raw = (metadata.get('org_id') or '').strip() if isinstance(metadata, dict) else ''
        if org_id_raw.isdigit():
            organization = db.session.get(Organization, int(org_id_raw))
            if organization:
                return organization

        customer_id = (obj.get('customer') or '').strip() if isinstance(obj.get('customer'), str) else ''
        if customer_id:
            return Organization.query.filter_by(stripe_customer_id=customer_id).first()

        return None

    def _upsert_subscription_state(self, organization: Organization, subscription_obj: dict[str, Any], *, event_id: str) -> None:
        status = (subscription_obj.get('status') or '').strip().lower()
        metadata = subscription_obj.get('metadata') if isinstance(subscription_obj.get('metadata'), dict) else {}
        plan_code = (metadata.get('plan_code') or '').strip().lower() if isinstance(metadata, dict) else ''
        if plan_code not in self.PLAN_CODES:
            # Try to infer from fallback stored plan when webhook metadata is absent.
            plan_code = ((organization.billing_plan_code or organization.subscription_tier or '')).strip().lower()
            if plan_code not in self.PLAN_CODES:
                plan_code = 'starter'

        organization.billing_status = status or 'inactive'
        organization.billing_plan_code = plan_code
        organization.subscription_tier = plan_code.capitalize()
        organization.stripe_subscription_id = (subscription_obj.get('id') or organization.stripe_subscription_id)
        organization.stripe_customer_id = (subscription_obj.get('customer') or organization.stripe_customer_id)
        organization.billing_current_period_start = self._safe_dt(subscription_obj.get('current_period_start'))
        organization.billing_current_period_end = self._safe_dt(subscription_obj.get('current_period_end'))
        organization.billing_trial_ends_at = self._safe_dt(subscription_obj.get('trial_end'))
        organization.billing_cancel_at_period_end = bool(subscription_obj.get('cancel_at_period_end'))
        organization.billing_last_event_id = event_id
        organization.billing_last_event_at = self._now_utc()

    def apply_webhook_event(self, event: dict[str, Any]) -> bool:
        event_id = (event.get('id') or '').strip()
        event_type = (event.get('type') or '').strip()
        event_obj = ((event.get('data') or {}).get('object') or {}) if isinstance(event.get('data'), dict) else {}
        if not event_id or not event_type or not isinstance(event_obj, dict):
            return False

        already = StripeBillingWebhookEvent.query.filter_by(event_id=event_id).first()
        if already:
            return True

        organization = self._extract_org_from_event_object(event_obj)

        if event_type == 'checkout.session.completed':
            if organization:
                metadata = event_obj.get('metadata') if isinstance(event_obj.get('metadata'), dict) else {}
                plan_code = self.normalize_plan_code((metadata.get('plan_code') or '').strip().lower() if isinstance(metadata, dict) else '')
                organization.stripe_customer_id = (event_obj.get('customer') or organization.stripe_customer_id)
                organization.stripe_subscription_id = (event_obj.get('subscription') or organization.stripe_subscription_id)
                organization.billing_plan_code = plan_code
                organization.subscription_tier = plan_code.capitalize()
                organization.billing_status = 'checkout_completed'
                organization.billing_last_event_id = event_id
                organization.billing_last_event_at = self._now_utc()

        elif event_type in {'customer.subscription.created', 'customer.subscription.updated'}:
            if organization:
                self._upsert_subscription_state(organization, event_obj, event_id=event_id)

        elif event_type in {'customer.subscription.deleted', 'customer.subscription.paused'}:
            if organization:
                organization.billing_status = (event_obj.get('status') or 'canceled').strip().lower()
                organization.billing_cancel_at_period_end = bool(event_obj.get('cancel_at_period_end'))
                organization.billing_last_event_id = event_id
                organization.billing_last_event_at = self._now_utc()

        elif event_type == 'invoice.payment_failed':
            if organization:
                organization.billing_status = 'past_due'
                organization.billing_last_event_id = event_id
                organization.billing_last_event_at = self._now_utc()

        elif event_type == 'invoice.paid':
            if organization:
                if (organization.billing_status or '').strip().lower() not in {'active', 'trialing'}:
                    organization.billing_status = 'active'
                organization.billing_last_event_id = event_id
                organization.billing_last_event_at = self._now_utc()

        db.session.add(
            StripeBillingWebhookEvent(
                event_id=event_id,
                event_type=event_type,
                organization_id=int(organization.id) if organization else None,
                processed_at=self._now_utc(),
            )
        )
        db.session.commit()
        return True


billing_service = BillingService()
