from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from flask import current_app

from app import db
from app.models import AuditEvent


class AuditLogService:
    def record_event(
        self,
        *,
        organization_id: int,
        event_type: str,
        actor_user_id: int | None = None,
        entity_type: str | None = None,
        entity_id: str | None = None,
        message: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AuditEvent | None:
        if not organization_id or not event_type:
            return None

        event = AuditEvent(
            organization_id=int(organization_id),
            actor_user_id=int(actor_user_id) if actor_user_id else None,
            event_type=(event_type or '').strip() or 'event',
            entity_type=(entity_type or '').strip() or None,
            entity_id=(str(entity_id) if entity_id is not None else None),
            message=(message or '').strip() or None,
            payload_json=json.dumps(payload or {}, ensure_ascii=False),
            created_at=datetime.now(timezone.utc),
        )

        try:
            db.session.add(event)
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Failed writing audit event %s for org %s', event_type, organization_id)
            return None

        return event


audit_log_service = AuditLogService()
