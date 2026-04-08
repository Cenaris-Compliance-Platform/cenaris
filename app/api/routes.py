from __future__ import annotations

import hashlib
import hmac
import io
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any

import jwt
import requests
from flask import Response, current_app, g, jsonify, request, send_file, url_for

from app import db, limiter
from app.api import bp
from app.models import (
    APIKey,
    ComplianceFrameworkVersion,
    ComplianceRequirement,
    Document,
    Organization,
    OrganizationMembership,
    OrganizationRequirementAssessment,
    RequirementEvidenceLink,
    User,
    WebhookDelivery,
    WebhookEndpoint,
)
from app.services.azure_data_service import azure_data_service
from app.services.azure_storage import AzureBlobStorageService
from app.services.file_validation import FileValidationService
from app.services.report_generator import report_generator


ALLOWED_WEBHOOK_EVENTS = {
    'organization.created',
    'organization.updated',
    'organization.deleted',
    'document.created',
    'document.updated',
    'document.deleted',
    'report.generated',
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _error(message: str, status: int = 400) -> tuple[Response, int]:
    return jsonify({'success': False, 'error': message}), status


def _api_rate_limit_key() -> str:
    api_key = (request.headers.get('X-API-Key') or '').strip()
    if api_key:
        return f"api_key:{hashlib.sha256(api_key.encode('utf-8')).hexdigest()[:16]}"

    auth_header = (request.headers.get('Authorization') or '').strip()
    if auth_header.lower().startswith('bearer '):
        token = auth_header.split(' ', 1)[1].strip()
        if token:
            return f"bearer:{hashlib.sha256(token.encode('utf-8')).hexdigest()[:16]}"

    return request.remote_addr or 'unknown'


def _jwt_secret() -> str:
    secret = str(current_app.config.get('SECRET_KEY') or '').strip()
    if not secret:
        raise RuntimeError('SECRET_KEY is not configured for JWT signing')
    return secret


def _issue_jwt(*, user: User, org_id: int, token_type: str, ttl_minutes: int) -> str:
    now = _utcnow()
    payload = {
        'sub': str(user.id),
        'org_id': int(org_id),
        'type': token_type,
        'sv': int(getattr(user, 'session_version', 1) or 1),
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(minutes=max(1, int(ttl_minutes)))).timestamp()),
        'jti': secrets.token_hex(12),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm='HS256')


def _decode_jwt(token: str, *, expected_type: str) -> dict[str, Any]:
    payload = jwt.decode(token, _jwt_secret(), algorithms=['HS256'])
    if (payload.get('type') or '').strip() != expected_type:
        raise jwt.InvalidTokenError('Invalid token type')
    return payload


def _active_org_for_user(user: User, requested_org_id: int | None = None) -> int | None:
    if requested_org_id is not None:
        membership = (
            OrganizationMembership.query
            .filter_by(user_id=int(user.id), organization_id=int(requested_org_id), is_active=True)
            .first()
        )
        return int(requested_org_id) if membership else None

    if getattr(user, 'organization_id', None):
        membership = (
            OrganizationMembership.query
            .filter_by(user_id=int(user.id), organization_id=int(user.organization_id), is_active=True)
            .first()
        )
        if membership:
            return int(user.organization_id)

    first_membership = (
        OrganizationMembership.query
        .filter_by(user_id=int(user.id), is_active=True)
        .order_by(OrganizationMembership.organization_id.asc())
        .first()
    )
    return int(first_membership.organization_id) if first_membership else None


def _require_api_auth(permission: str | None = None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            auth_header = (request.headers.get('Authorization') or '').strip()
            api_key_value = (request.headers.get('X-API-Key') or '').strip()

            auth_type: str | None = None
            user: User | None = None
            org_id: int | None = None
            api_key: APIKey | None = None

            if auth_header.lower().startswith('bearer '):
                token = auth_header.split(' ', 1)[1].strip()
                if not token:
                    return _error('Missing bearer token', 401)
                try:
                    payload = _decode_jwt(token, expected_type='access')
                except jwt.ExpiredSignatureError:
                    return _error('Access token expired', 401)
                except jwt.InvalidTokenError:
                    return _error('Invalid access token', 401)

                user = db.session.get(User, int(payload.get('sub') or 0))
                if not user or not bool(getattr(user, 'is_active', False)):
                    return _error('Unauthorized', 401)

                payload_sv = int(payload.get('sv') or 0)
                current_sv = int(getattr(user, 'session_version', 1) or 1)
                if payload_sv != current_sv:
                    return _error('Token no longer valid. Re-authenticate.', 401)

                org_id = _active_org_for_user(user, requested_org_id=int(payload.get('org_id') or 0) or None)
                if not org_id:
                    return _error('No active organization for this token', 403)

                auth_type = 'jwt'
            elif api_key_value:
                key_hash = hashlib.sha256(api_key_value.encode('utf-8')).hexdigest()
                api_key = APIKey.query.filter_by(key_hash=key_hash, is_active=True).first()
                if not api_key:
                    return _error('Invalid API key', 401)

                org_id = int(api_key.organization_id)
                user = db.session.get(User, int(api_key.created_by_user_id or 0)) if api_key.created_by_user_id else None
                if user and not bool(getattr(user, 'is_active', False)):
                    return _error('API key owner is inactive', 403)

                # API keys are organization-scoped and bound to an active membership.
                # If membership was removed, key access must stop immediately.
                if user:
                    owner_membership = (
                        OrganizationMembership.query
                        .filter_by(user_id=int(user.id), organization_id=int(org_id), is_active=True)
                        .first()
                    )
                    if not owner_membership:
                        return _error('API key owner no longer has access to this organization', 403)

                api_key.last_used_at = _utcnow()
                db.session.commit()
                auth_type = 'api_key'
            else:
                return _error('Authentication required: Bearer token or X-API-Key', 401)

            if not org_id:
                return _error('Active organization is required', 403)

            if permission:
                # API key auth inherits creator permissions when available.
                if not user or not user.has_permission(permission, org_id=int(org_id)):
                    return _error('Forbidden', 403)

            g.api_auth_type = auth_type
            g.api_user = user
            g.api_org_id = int(org_id)
            g.api_key = api_key
            return func(*args, **kwargs)

        return wrapper

    return decorator


def _organization_payload(org: Organization) -> dict[str, Any]:
    return {
        'id': int(org.id),
        'name': org.name,
        'trading_name': org.trading_name,
        'abn': org.abn,
        'acn': org.acn,
        'organization_type': org.organization_type,
        'contact_email': org.contact_email,
        'contact_number': org.contact_number,
        'address': org.address,
        'industry': org.industry,
        'billing_email': org.billing_email,
        'billing_address': org.billing_address,
        'subscription_tier': org.subscription_tier,
        'created_at': org.created_at.isoformat() if org.created_at else None,
    }


def _document_payload(doc: Document) -> dict[str, Any]:
    return {
        'id': int(doc.id),
        'filename': doc.filename,
        'file_size': int(doc.file_size or 0),
        'content_type': doc.content_type,
        'is_active': bool(doc.is_active),
        'uploaded_at': doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        'uploaded_by': int(doc.uploaded_by) if doc.uploaded_by else None,
    }


def _emit_webhook(*, org_id: int, event_type: str, payload: dict[str, Any]) -> None:
    if event_type not in ALLOWED_WEBHOOK_EVENTS:
        return

    endpoints = (
        WebhookEndpoint.query
        .filter_by(organization_id=int(org_id), is_active=True)
        .order_by(WebhookEndpoint.id.asc())
        .all()
    )
    if not endpoints:
        return

    serialized_payload = json.dumps(payload, separators=(',', ':'), ensure_ascii=True)

    for endpoint in endpoints:
        subscribed_raw = (endpoint.events_csv or '*').strip()
        subscribed = {item.strip() for item in subscribed_raw.split(',') if item.strip()}
        if '*' not in subscribed and event_type not in subscribed:
            continue

        signature = hmac.new(
            str(endpoint.secret or '').encode('utf-8'),
            serialized_payload.encode('utf-8'),
            hashlib.sha256,
        ).hexdigest()

        success = False
        status_code = None
        excerpt = None
        try:
            response = requests.post(
                endpoint.target_url,
                data=serialized_payload,
                headers={
                    'Content-Type': 'application/json',
                    'X-Cenaris-Event': event_type,
                    'X-Cenaris-Signature': signature,
                },
                timeout=5,
            )
            status_code = int(response.status_code)
            success = 200 <= response.status_code < 300
            excerpt = (response.text or '')[:500] or None
        except Exception as e:
            excerpt = str(e)[:500]

        delivery = WebhookDelivery(
            webhook_endpoint_id=int(endpoint.id),
            event_type=event_type,
            payload_json=serialized_payload,
            success=success,
            status_code=status_code,
            response_excerpt=excerpt,
        )
        db.session.add(delivery)

    db.session.commit()


@bp.route('/versions', methods=['GET'])
def api_versions():
    return jsonify({
        'success': True,
        'versions': ['v1'],
        'default': 'v1',
        'docs_url': url_for('api_v1.api_docs', _external=False),
    })


@bp.route('/docs/openapi.json', methods=['GET'])
def api_openapi():
    spec = {
        'openapi': '3.0.3',
        'info': {
            'title': 'Cenaris Public API',
            'version': '1.0.0',
            'description': 'Public API for authentication, organisations, documents, compliance, reports, API keys, and webhooks.',
        },
        'servers': [{'url': '/api/v1'}],
        'components': {
            'securitySchemes': {
                'bearerAuth': {'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT'},
                'apiKeyAuth': {'type': 'apiKey', 'in': 'header', 'name': 'X-API-Key'},
            }
        },
        'security': [{'bearerAuth': []}, {'apiKeyAuth': []}],
        'paths': {
            '/auth/login': {'post': {'summary': 'Login and receive access/refresh JWT tokens'}},
            '/auth/refresh': {'post': {'summary': 'Refresh access token'}},
            '/auth/logout': {'post': {'summary': 'Invalidate active user tokens by session version bump'}},
            '/organizations': {'get': {'summary': 'List organizations'}, 'post': {'summary': 'Create organization'}},
            '/organizations/{org_id}': {'get': {'summary': 'Get organization'}, 'patch': {'summary': 'Update organization'}, 'delete': {'summary': 'Delete organization'}},
            '/documents': {'get': {'summary': 'List documents'}, 'post': {'summary': 'Upload document'}},
            '/documents/{doc_id}': {'get': {'summary': 'Get document'}, 'patch': {'summary': 'Update document'}, 'delete': {'summary': 'Delete document'}},
            '/documents/{doc_id}/download': {'get': {'summary': 'Download document'}},
            '/compliance/summary': {'get': {'summary': 'Get compliance summary metrics'}},
            '/reports/generate/{report_type}': {'get': {'summary': 'Generate report PDF'}},
            '/api-keys': {'get': {'summary': 'List API keys'}, 'post': {'summary': 'Create API key'}},
            '/api-keys/{key_id}': {'delete': {'summary': 'Revoke API key'}},
            '/webhooks': {'get': {'summary': 'List webhook endpoints'}, 'post': {'summary': 'Create webhook endpoint'}},
            '/webhooks/{webhook_id}': {'delete': {'summary': 'Delete webhook endpoint'}},
            '/webhooks/{webhook_id}/test': {'post': {'summary': 'Send test webhook event'}},
        },
    }
    return jsonify(spec)


@bp.route('/docs', methods=['GET'])
def api_docs():
    return Response(
        """
<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>Cenaris Public API Docs</title>
    <link rel=\"stylesheet\" href=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui.css\" />
  </head>
  <body>
    <div id=\"swagger-ui\"></div>
    <script src=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js\"></script>
    <script>
      window.ui = SwaggerUIBundle({
        url: '/api/v1/docs/openapi.json',
        dom_id: '#swagger-ui'
      });
    </script>
  </body>
</html>
        """.strip(),
        mimetype='text/html',
    )


@bp.route('/auth/login', methods=['POST'])
@limiter.limit('20 per minute', key_func=_api_rate_limit_key)
def api_login():
    payload = request.get_json(silent=True) or {}
    email = (payload.get('email') or '').strip().lower()
    password = payload.get('password') or ''
    requested_org = payload.get('organization_id')

    if not email or not password:
        return _error('email and password are required', 400)

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return _error('Invalid credentials', 401)

    if not bool(getattr(user, 'is_active', False)):
        return _error('User account is inactive', 403)

    requested_org_id = int(requested_org) if str(requested_org).isdigit() else None
    org_id = _active_org_for_user(user, requested_org_id=requested_org_id)
    if not org_id:
        return _error('No active organization for this user', 403)

    access_ttl = int(current_app.config.get('API_JWT_ACCESS_MINUTES') or 30)
    refresh_ttl = int(current_app.config.get('API_JWT_REFRESH_MINUTES') or 60 * 24 * 30)

    access_token = _issue_jwt(user=user, org_id=int(org_id), token_type='access', ttl_minutes=access_ttl)
    refresh_token = _issue_jwt(user=user, org_id=int(org_id), token_type='refresh', ttl_minutes=refresh_ttl)

    return jsonify({
        'success': True,
        'token_type': 'Bearer',
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_in': access_ttl * 60,
        'organization_id': int(org_id),
        'user': {
            'id': int(user.id),
            'email': user.email,
            'name': user.display_name(),
        },
    })


@bp.route('/auth/refresh', methods=['POST'])
@limiter.limit('30 per minute', key_func=_api_rate_limit_key)
def api_refresh():
    payload = request.get_json(silent=True) or {}
    refresh_token = (payload.get('refresh_token') or '').strip()

    if not refresh_token:
        auth_header = (request.headers.get('Authorization') or '').strip()
        if auth_header.lower().startswith('bearer '):
            refresh_token = auth_header.split(' ', 1)[1].strip()

    if not refresh_token:
        return _error('refresh_token is required', 400)

    try:
        token_payload = _decode_jwt(refresh_token, expected_type='refresh')
    except jwt.ExpiredSignatureError:
        return _error('Refresh token expired', 401)
    except jwt.InvalidTokenError:
        return _error('Invalid refresh token', 401)

    user = db.session.get(User, int(token_payload.get('sub') or 0))
    if not user or not bool(getattr(user, 'is_active', False)):
        return _error('Unauthorized', 401)

    payload_sv = int(token_payload.get('sv') or 0)
    current_sv = int(getattr(user, 'session_version', 1) or 1)
    if payload_sv != current_sv:
        return _error('Token no longer valid. Re-authenticate.', 401)

    org_id = _active_org_for_user(user, requested_org_id=int(token_payload.get('org_id') or 0) or None)
    if not org_id:
        return _error('No active organization for this user', 403)

    access_ttl = int(current_app.config.get('API_JWT_ACCESS_MINUTES') or 30)
    refresh_ttl = int(current_app.config.get('API_JWT_REFRESH_MINUTES') or 60 * 24 * 30)

    return jsonify({
        'success': True,
        'token_type': 'Bearer',
        'access_token': _issue_jwt(user=user, org_id=int(org_id), token_type='access', ttl_minutes=access_ttl),
        'refresh_token': _issue_jwt(user=user, org_id=int(org_id), token_type='refresh', ttl_minutes=refresh_ttl),
        'expires_in': access_ttl * 60,
        'organization_id': int(org_id),
    })


@bp.route('/auth/logout', methods=['POST'])
@_require_api_auth()
def api_logout():
    user = g.api_user
    if not user:
        return _error('Logout requires JWT user authentication', 400)

    user.session_version = int(getattr(user, 'session_version', 1) or 1) + 1
    db.session.commit()
    return jsonify({'success': True, 'message': 'Logged out. Existing JWT tokens are now invalid.'})


@bp.route('/organizations', methods=['GET'])
@_require_api_auth()
def api_list_organizations():
    user = g.api_user
    if user:
        memberships = (
            OrganizationMembership.query
            .filter_by(user_id=int(user.id), is_active=True)
            .order_by(OrganizationMembership.organization_id.asc())
            .all()
        )
        org_ids = [int(m.organization_id) for m in memberships]
        orgs = Organization.query.filter(Organization.id.in_(org_ids)).order_by(Organization.name.asc()).all() if org_ids else []
    else:
        orgs = [db.session.get(Organization, int(g.api_org_id))] if g.api_org_id else []

    return jsonify({'success': True, 'organizations': [_organization_payload(o) for o in orgs if o]})


@bp.route('/organizations', methods=['POST'])
@_require_api_auth()
def api_create_organization():
    user = g.api_user
    if not user:
        return _error('Creating organizations requires JWT user authentication', 400)

    payload = request.get_json(silent=True) or {}
    name = (payload.get('name') or '').strip()
    if not name:
        return _error('name is required', 400)

    org = Organization(
        name=name,
        trading_name=(payload.get('trading_name') or '').strip() or None,
        abn=(payload.get('abn') or '').strip() or None,
        acn=(payload.get('acn') or '').strip() or None,
        organization_type=(payload.get('organization_type') or '').strip() or None,
        contact_email=(payload.get('contact_email') or '').strip().lower() or None,
        contact_number=(payload.get('contact_number') or '').strip() or None,
        address=(payload.get('address') or '').strip() or None,
        industry=(payload.get('industry') or '').strip() or None,
    )
    db.session.add(org)
    db.session.flush()

    membership = OrganizationMembership(
        organization_id=int(org.id),
        user_id=int(user.id),
        role='Admin',
        is_active=True,
        created_at=_utcnow(),
    )
    db.session.add(membership)

    user.organization_id = int(org.id)
    db.session.commit()

    _emit_webhook(
        org_id=int(org.id),
        event_type='organization.created',
        payload={'organization': _organization_payload(org)},
    )

    return jsonify({'success': True, 'organization': _organization_payload(org)}), 201


@bp.route('/organizations/<int:org_id>', methods=['GET'])
@_require_api_auth()
def api_get_organization(org_id: int):
    org = db.session.get(Organization, int(org_id))
    if not org:
        return _error('Organization not found', 404)

    membership = (
        OrganizationMembership.query
        .filter_by(user_id=int(g.api_user.id) if g.api_user else 0, organization_id=int(org_id), is_active=True)
        .first()
    ) if g.api_user else (int(g.api_org_id) == int(org_id))
    if not membership:
        return _error('Forbidden', 403)

    return jsonify({'success': True, 'organization': _organization_payload(org)})


@bp.route('/organizations/<int:org_id>', methods=['PATCH'])
@_require_api_auth('users.manage')
def api_update_organization(org_id: int):
    if int(g.api_org_id) != int(org_id):
        return _error('Forbidden', 403)

    org = db.session.get(Organization, int(org_id))
    if not org:
        return _error('Organization not found', 404)

    payload = request.get_json(silent=True) or {}
    editable_fields = {
        'name', 'trading_name', 'abn', 'acn', 'organization_type', 'contact_email',
        'contact_number', 'address', 'industry', 'billing_email', 'billing_address',
    }

    for field in editable_fields:
        if field in payload:
            value = payload.get(field)
            if isinstance(value, str):
                value = value.strip() or None
                if field in {'contact_email', 'billing_email'} and value:
                    value = value.lower()
            setattr(org, field, value)

    db.session.commit()

    _emit_webhook(
        org_id=int(org.id),
        event_type='organization.updated',
        payload={'organization': _organization_payload(org)},
    )

    return jsonify({'success': True, 'organization': _organization_payload(org)})


@bp.route('/organizations/<int:org_id>', methods=['DELETE'])
@_require_api_auth('users.manage')
def api_delete_organization(org_id: int):
    if int(g.api_org_id) != int(org_id):
        return _error('Forbidden', 403)

    org = db.session.get(Organization, int(org_id))
    if not org:
        return _error('Organization not found', 404)

    try:
        payload = _organization_payload(org)
        db.session.delete(org)
        db.session.commit()
    except Exception:
        db.session.rollback()
        return _error('Organization cannot be deleted due to dependent records', 409)

    _emit_webhook(org_id=int(org_id), event_type='organization.deleted', payload={'organization': payload})
    return jsonify({'success': True})


@bp.route('/documents', methods=['GET'])
@_require_api_auth('documents.view')
def api_list_documents():
    documents = (
        Document.query
        .filter_by(organization_id=int(g.api_org_id), is_active=True)
        .order_by(Document.uploaded_at.desc())
        .all()
    )
    return jsonify({'success': True, 'documents': [_document_payload(d) for d in documents]})


@bp.route('/documents', methods=['POST'])
@_require_api_auth('documents.upload')
@limiter.limit('60 per minute', key_func=_api_rate_limit_key)
def api_create_document():
    if 'file' not in request.files:
        return _error('file is required (multipart/form-data)', 400)

    incoming = request.files['file']
    if not incoming or not (incoming.filename or '').strip():
        return _error('file is required', 400)

    validation = FileValidationService.validate_file(incoming.stream, incoming.filename)
    if not validation.get('success'):
        return _error(validation.get('error') or 'Invalid file', 400)

    safe_filename = FileValidationService.sanitize_filename(incoming.filename)
    content_type = validation.get('content_type') or incoming.content_type
    storage_service = AzureBlobStorageService()

    if not storage_service.is_configured():
        return _error('Storage is not configured', 503)

    uploader_id = int(g.api_user.id) if g.api_user else int(g.api_key.created_by_user_id or 0)
    blob_name = storage_service.generate_file_path(
        filename=safe_filename,
        user_id=uploader_id,
        organization_id=int(g.api_org_id),
    )

    try:
        incoming.stream.seek(0)
    except Exception:
        pass

    upload_result = storage_service.upload_file(
        incoming.stream,
        blob_name,
        content_type=content_type,
        metadata={
            'original_filename': safe_filename,
            'uploaded_by': str(uploader_id),
            'organization_id': str(int(g.api_org_id)),
        },
    )
    if not upload_result.get('success'):
        return _error(upload_result.get('error') or 'Upload failed', 500)

    document = Document(
        filename=safe_filename,
        blob_name=blob_name,
        file_size=int(upload_result.get('size') or 0),
        content_type=content_type,
        uploaded_by=uploader_id,
        organization_id=int(g.api_org_id),
        is_active=True,
    )
    db.session.add(document)
    db.session.commit()

    payload = {'document': _document_payload(document)}
    _emit_webhook(org_id=int(g.api_org_id), event_type='document.created', payload=payload)
    return jsonify({'success': True, 'document': _document_payload(document)}), 201


@bp.route('/documents/<int:doc_id>', methods=['GET'])
@_require_api_auth('documents.view')
def api_get_document(doc_id: int):
    document = Document.query.filter_by(id=int(doc_id), organization_id=int(g.api_org_id), is_active=True).first()
    if not document:
        return _error('Document not found', 404)

    return jsonify({'success': True, 'document': _document_payload(document)})


@bp.route('/documents/<int:doc_id>', methods=['PATCH'])
@_require_api_auth('documents.upload')
def api_update_document(doc_id: int):
    document = Document.query.filter_by(id=int(doc_id), organization_id=int(g.api_org_id), is_active=True).first()
    if not document:
        return _error('Document not found', 404)

    payload = request.get_json(silent=True) or {}
    filename = payload.get('filename')
    if filename is not None:
        sanitized = FileValidationService.sanitize_filename(str(filename))
        if not sanitized:
            return _error('Invalid filename', 400)
        document.filename = sanitized

    db.session.commit()

    event_payload = {'document': _document_payload(document)}
    _emit_webhook(org_id=int(g.api_org_id), event_type='document.updated', payload=event_payload)
    return jsonify({'success': True, 'document': _document_payload(document)})


@bp.route('/documents/<int:doc_id>', methods=['DELETE'])
@_require_api_auth('documents.upload')
def api_delete_document(doc_id: int):
    document = Document.query.filter_by(id=int(doc_id), organization_id=int(g.api_org_id), is_active=True).first()
    if not document:
        return _error('Document not found', 404)

    document.is_active = False
    db.session.commit()

    event_payload = {'document': _document_payload(document)}
    _emit_webhook(org_id=int(g.api_org_id), event_type='document.deleted', payload=event_payload)
    return jsonify({'success': True})


@bp.route('/documents/<int:doc_id>/download', methods=['GET'])
@_require_api_auth('documents.view')
def api_download_document(doc_id: int):
    document = Document.query.filter_by(id=int(doc_id), organization_id=int(g.api_org_id), is_active=True).first()
    if not document:
        return _error('Document not found', 404)

    storage_service = AzureBlobStorageService()
    result = storage_service.download_file(document.blob_name)
    if not result.get('success'):
        return _error(result.get('error') or 'Download failed', 500)

    data = result.get('data')
    if not data:
        return _error('File not found', 404)

    stream = io.BytesIO(data)
    stream.seek(0)
    return send_file(
        stream,
        mimetype=document.content_type or 'application/octet-stream',
        as_attachment=True,
        download_name=document.filename,
    )


@bp.route('/compliance/summary', methods=['GET'])
@_require_api_auth('documents.view')
def api_compliance_summary():
    org_id = int(g.api_org_id)

    total_requirements = (
        db.session.query(ComplianceRequirement.id)
        .join(ComplianceFrameworkVersion, ComplianceFrameworkVersion.id == ComplianceRequirement.framework_version_id)
        .filter(
            ComplianceFrameworkVersion.is_active.is_(True),
            (ComplianceFrameworkVersion.organization_id.is_(None))
            | (ComplianceFrameworkVersion.organization_id == int(org_id)),
        )
        .count()
    )

    assessments = (
        OrganizationRequirementAssessment.query
        .filter_by(organization_id=int(org_id))
        .all()
    )
    linked_count = (
        RequirementEvidenceLink.query
        .filter_by(organization_id=int(org_id))
        .count()
    )

    score_values = [int(a.computed_score) for a in assessments if a.computed_score is not None]
    avg_score = round(sum(score_values) / len(score_values), 2) if score_values else 0

    status_counts: dict[str, int] = {}
    for assessment in assessments:
        status = (assessment.computed_flag or 'Not assessed').strip() or 'Not assessed'
        status_counts[status] = int(status_counts.get(status, 0)) + 1

    return jsonify({
        'success': True,
        'summary': {
            'total_requirements': int(total_requirements),
            'assessed_requirements': int(len(assessments)),
            'average_score': avg_score,
            'linked_evidence_count': int(linked_count),
            'status_counts': status_counts,
        },
    })


def _build_report_inputs(org_id: int, user: User | None) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], list[Document]]:
    organization = db.session.get(Organization, int(org_id))
    if not organization:
        raise ValueError('Organization not found')

    if not organization.billing_complete():
        raise PermissionError('Billing details are required before report generation')

    org_data = {
        'name': organization.name,
        'abn': organization.abn or '',
        'address': organization.address or '',
        'contact_name': user.display_name() if user else 'API Client',
        'email': organization.contact_email or (user.email if user else ''),
        'framework': organization.industry or '',
        'audit_type': 'Initial',
    }

    summary = azure_data_service.get_dashboard_summary(
        user_id=int(user.id) if user else 0,
        organization_id=int(org_id),
    )
    gap_data = []

    if summary.get('file_summaries'):
        for file_summary in summary['file_summaries']:
            frameworks_data = file_summary.get('frameworks', [])
            for framework_data in frameworks_data:
                status = (framework_data.get('status') or '').strip().lower()
                if status == 'complete':
                    display_status = 'Complete'
                elif status == 'needs review':
                    display_status = 'Needs Review'
                elif status == 'missing':
                    display_status = 'Missing'
                else:
                    display_status = framework_data.get('status') or 'Unknown'

                gap_data.append({
                    'requirement_name': framework_data.get('name') or 'Unnamed requirement',
                    'status': display_status,
                    'completion_percentage': round(float(framework_data.get('score') or 0), 1),
                    'supporting_evidence': file_summary.get('file_name') or 'compliance_summary.csv',
                    'last_updated': file_summary.get('last_updated'),
                })

    total = len(gap_data)
    met = len([g for g in gap_data if g['status'] == 'Complete'])
    pending = len([g for g in gap_data if g['status'] == 'Needs Review'])
    not_met = len([g for g in gap_data if g['status'] == 'Missing'])
    avg = sum([g['completion_percentage'] for g in gap_data]) / len(gap_data) if gap_data else 0

    summary_stats = {
        'total': int(total),
        'met': int(met),
        'pending': int(pending),
        'not_met': int(not_met),
        'compliance_percentage': int(avg),
    }

    documents = (
        Document.query
        .filter_by(organization_id=int(org_id), is_active=True)
        .order_by(Document.uploaded_at.desc())
        .all()
    )

    return org_data, gap_data, summary_stats, documents


@bp.route('/reports/generate/<string:report_type>', methods=['GET'])
@_require_api_auth('audits.export')
def api_generate_report(report_type: str):
    report_type = (report_type or '').strip().lower()
    if report_type not in {'gap-analysis', 'accreditation-plan', 'audit-pack'}:
        return _error('Invalid report type', 400)

    try:
        org_data, gap_data, summary_stats, documents = _build_report_inputs(int(g.api_org_id), g.api_user)
    except PermissionError as e:
        return _error(str(e), 403)
    except Exception as e:
        return _error(str(e), 500)

    now_label = datetime.now().strftime('%Y%m%d')
    if report_type == 'gap-analysis':
        buffer = report_generator.generate_gap_analysis_report(org_data, gap_data, summary_stats)
        filename = f'Gap_Analysis_Report_{now_label}.pdf'
    elif report_type == 'accreditation-plan':
        buffer = report_generator.generate_accreditation_plan(org_data, gap_data, summary_stats)
        filename = f'Accreditation_Plan_{now_label}.pdf'
    else:
        buffer = report_generator.generate_audit_pack(org_data, gap_data, summary_stats, documents)
        filename = f'Audit_Pack_Export_{now_label}.pdf'

    _emit_webhook(
        org_id=int(g.api_org_id),
        event_type='report.generated',
        payload={'report_type': report_type, 'filename': filename},
    )

    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename,
    )


@bp.route('/api-keys', methods=['GET'])
@_require_api_auth('users.manage')
def api_list_keys():
    keys = (
        APIKey.query
        .filter_by(organization_id=int(g.api_org_id))
        .order_by(APIKey.created_at.desc())
        .all()
    )
    return jsonify({
        'success': True,
        'api_keys': [
            {
                'id': int(k.id),
                'name': k.name,
                'key_prefix': k.key_prefix,
                'is_active': bool(k.is_active),
                'created_at': k.created_at.isoformat() if k.created_at else None,
                'last_used_at': k.last_used_at.isoformat() if k.last_used_at else None,
                'revoked_at': k.revoked_at.isoformat() if k.revoked_at else None,
            }
            for k in keys
        ],
    })


@bp.route('/api-keys', methods=['POST'])
@_require_api_auth('users.manage')
def api_create_key():
    payload = request.get_json(silent=True) or {}
    name = (payload.get('name') or '').strip()
    if not name:
        return _error('name is required', 400)

    raw_key = f"cnr_{secrets.token_urlsafe(36)}"
    key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
    key_prefix = raw_key[:12]

    key = APIKey(
        organization_id=int(g.api_org_id),
        created_by_user_id=int(g.api_user.id) if g.api_user else None,
        name=name,
        key_prefix=key_prefix,
        key_hash=key_hash,
        is_active=True,
    )
    db.session.add(key)
    db.session.commit()

    return jsonify({
        'success': True,
        'api_key': {
            'id': int(key.id),
            'name': key.name,
            'key_prefix': key.key_prefix,
            'created_at': key.created_at.isoformat() if key.created_at else None,
        },
        'secret': raw_key,
        'warning': 'Store this secret now. It will not be returned again.',
    }), 201


@bp.route('/api-keys/<int:key_id>', methods=['DELETE'])
@_require_api_auth('users.manage')
def api_revoke_key(key_id: int):
    key = APIKey.query.filter_by(id=int(key_id), organization_id=int(g.api_org_id)).first()
    if not key:
        return _error('API key not found', 404)

    key.is_active = False
    key.revoked_at = _utcnow()
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/webhooks', methods=['GET'])
@_require_api_auth('users.manage')
def api_list_webhooks():
    endpoints = (
        WebhookEndpoint.query
        .filter_by(organization_id=int(g.api_org_id))
        .order_by(WebhookEndpoint.created_at.desc())
        .all()
    )
    return jsonify({
        'success': True,
        'webhooks': [
            {
                'id': int(w.id),
                'name': w.name,
                'target_url': w.target_url,
                'events': [e.strip() for e in (w.events_csv or '*').split(',') if e.strip()],
                'is_active': bool(w.is_active),
                'created_at': w.created_at.isoformat() if w.created_at else None,
            }
            for w in endpoints
        ],
        'allowed_events': sorted(ALLOWED_WEBHOOK_EVENTS),
    })


@bp.route('/webhooks', methods=['POST'])
@_require_api_auth('users.manage')
def api_create_webhook():
    payload = request.get_json(silent=True) or {}
    name = (payload.get('name') or '').strip()
    target_url = (payload.get('target_url') or '').strip()
    events = payload.get('events') or ['*']

    if not name or not target_url:
        return _error('name and target_url are required', 400)

    if not (target_url.startswith('http://') or target_url.startswith('https://')):
        return _error('target_url must start with http:// or https://', 400)

    # Production integrations should be TLS-only.
    if not bool(current_app.debug) and target_url.startswith('http://'):
        return _error('target_url must use https in non-debug environments', 400)

    if not isinstance(events, list):
        return _error('events must be an array', 400)

    normalized = []
    for event_name in events:
        item = str(event_name).strip()
        if not item:
            continue
        if item != '*' and item not in ALLOWED_WEBHOOK_EVENTS:
            return _error(f'Unsupported event: {item}', 400)
        normalized.append(item)

    if not normalized:
        normalized = ['*']

    endpoint = WebhookEndpoint(
        organization_id=int(g.api_org_id),
        created_by_user_id=int(g.api_user.id) if g.api_user else None,
        name=name,
        target_url=target_url,
        events_csv=','.join(sorted(set(normalized))),
        secret=secrets.token_hex(32),
        is_active=True,
    )
    db.session.add(endpoint)
    db.session.commit()

    return jsonify({
        'success': True,
        'webhook': {
            'id': int(endpoint.id),
            'name': endpoint.name,
            'target_url': endpoint.target_url,
            'events': [e.strip() for e in (endpoint.events_csv or '*').split(',') if e.strip()],
            'secret': endpoint.secret,
        },
        'warning': 'Store the webhook secret securely.',
    }), 201


@bp.route('/webhooks/<int:webhook_id>', methods=['DELETE'])
@_require_api_auth('users.manage')
def api_delete_webhook(webhook_id: int):
    endpoint = WebhookEndpoint.query.filter_by(id=int(webhook_id), organization_id=int(g.api_org_id)).first()
    if not endpoint:
        return _error('Webhook not found', 404)

    db.session.delete(endpoint)
    db.session.commit()
    return jsonify({'success': True})


@bp.route('/webhooks/<int:webhook_id>/test', methods=['POST'])
@_require_api_auth('users.manage')
def api_test_webhook(webhook_id: int):
    endpoint = WebhookEndpoint.query.filter_by(id=int(webhook_id), organization_id=int(g.api_org_id), is_active=True).first()
    if not endpoint:
        return _error('Webhook not found', 404)

    _emit_webhook(
        org_id=int(g.api_org_id),
        event_type='organization.updated',
        payload={'test': True, 'timestamp': _utcnow().isoformat()},
    )
    return jsonify({'success': True, 'message': 'Test webhook event dispatched.'})
