from flask import Flask, redirect, request, g
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import config
import os
import logging
import threading
import time
import contextlib

from werkzeug.middleware.proxy_fix import ProxyFix

import click

from authlib.integrations.flask_client import OAuth
from flask_mail import Mail

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

login_manager = LoginManager()

logger = logging.getLogger(__name__)


_ORG_SWITCHER_CONTEXT_CACHE: dict[tuple[int, int | None], tuple[float, dict]] = {}
_ORG_SWITCHER_CONTEXT_CACHE_LOCK = threading.Lock()


def invalidate_org_switcher_context_cache(user_id: int, org_id: int | None = None) -> None:
    """Invalidate cached org switcher/template context for a user.

    The org switcher context is intentionally cached (perf), but some actions
    (like role changes) must reflect immediately in the UI.
    """
    try:
        user_id_int = int(user_id)
    except Exception:
        return

    try:
        org_id_int = int(org_id) if org_id is not None else None
    except Exception:
        org_id_int = None

    with _ORG_SWITCHER_CONTEXT_CACHE_LOCK:
        if org_id_int is not None:
            _ORG_SWITCHER_CONTEXT_CACHE.pop((user_id_int, org_id_int), None)
        # Also clear any other cached entries for this user (multi-org, None key, etc.)
        keys_to_delete = [k for k in _ORG_SWITCHER_CONTEXT_CACHE.keys() if k[0] == user_id_int]
        for k in keys_to_delete:
            _ORG_SWITCHER_CONTEXT_CACHE.pop(k, None)


def _maybe_enable_system_cert_store() -> None:
    """Use OS certificate store when available.

    On some Windows networks (corporate proxy / TLS inspection), Requests may fail
    to reach OAuth providers because the intercepting root CA is only installed
    in the Windows certificate store. The optional `truststore` package allows
    Python's ssl module to trust the system store.
    """
    if os.name != 'nt':
        return

    # Make this explicitly opt-in so local dev can toggle depending on network.
    flag = (os.environ.get('TRUSTSTORE_ENABLE') or '0').strip().lower()
    if flag not in {'1', 'true', 'yes', 'on'}:
        return

    try:
        import truststore  # type: ignore

        truststore.inject_into_ssl()
        logger.info('Enabled system certificate store via truststore')
    except Exception:
        # Optional dependency; ignore if unavailable.
        return


_maybe_enable_system_cert_store()

# Database (Milestone 1)
db = SQLAlchemy()
migrate = Migrate()

# OAuth + Mail
oauth = OAuth()
mail = Mail()

# Rate limiting
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri=os.environ.get('RATELIMIT_STORAGE_URI') or 'memory://',
)

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    from app.models import User
    return db.session.get(User, int(user_id))

def create_app(config_name=None):
    """Application factory pattern."""
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG') or 'default'

    if isinstance(config_name, str):
        config_name = config_name.strip()

    if config_name not in config:
        config_name = 'default'
    
    app = Flask(__name__)

    # Respect X-Forwarded-* headers when running behind a reverse proxy (e.g. Render).
    # This fixes request.remote_addr (otherwise often 127.0.0.1) and makes url_for(...,_external=True)
    # generate the correct scheme/host for OAuth callbacks.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1, x_prefix=1)
    # Ensure the instance folder exists early so SQLite can create/open the DB file.
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    @app.before_request
    def _normalize_localhost_hostnames():
        """Keep local dev hostnames consistent (localhost vs 127.0.0.1).

        OAuth callbacks in this app use http://localhost:PORT by default.
        If a user browses via http://127.0.0.1:PORT, cookies set on localhost
        won't be sent to 127.0.0.1, which makes users appear logged out.

        Redirect GET/HEAD requests from any non-canonical host to the canonical
        host to ensure the session cookie remains consistent across navigations.
        """

        # Opt-out switch (mostly for testing multi-host scenarios).
        flag = (os.environ.get('DEV_CANONICAL_HOST') or '1').strip().lower()
        if flag in {'0', 'false', 'no', 'off'}:
            return None

        # Only canonicalize in debug/dev.
        if not app.debug:
            return None

        if request.method not in {'GET', 'HEAD'}:
            return None

        host = (request.host or '')
        host_only = host.split(':', 1)[0]

        canonical = (os.environ.get('DEV_CANONICAL_HOSTNAME') or 'localhost').strip() or 'localhost'
        if host_only == canonical:
            return None

        port = host.split(':', 1)[1] if ':' in host else ''
        new_host = f'{canonical}:{port}' if port else canonical

        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(request.url)
        return redirect(urlunsplit((parts.scheme, new_host, parts.path, parts.query, parts.fragment)), code=302)

    @app.before_request
    def _start_request_timer():
        """Start timing the request for performance debugging."""
        g.request_start_time = time.time()
        g.sql_query_count = 0
        g.sql_query_time_s = 0.0

    @app.after_request
    def _log_slow_requests(response):
        """Log requests that take longer than threshold."""
        try:
            if hasattr(g, 'request_start_time'):
                elapsed = time.time() - g.request_start_time
                # Log requests slower than 1 second to identify bottlenecks
                if elapsed > 1.0:
                    endpoint = request.endpoint or 'unknown'
                    method = request.method
                    extra = ''
                    try:
                        qn = int(getattr(g, 'sql_query_count', 0) or 0)
                        qt = float(getattr(g, 'sql_query_time_s', 0.0) or 0.0)
                        extra = f' | sql: {qn} queries, {qt:.3f}s'
                    except Exception:
                        extra = ''
                    logger.warning(f'SLOW REQUEST: {method} {endpoint} took {elapsed:.2f}s{extra}')

                # Optional: always log SQL timing when explicitly enabled.
                perf_flag = (os.environ.get('PERF_SQL_LOG') or '0').strip().lower()
                if perf_flag in {'1', 'true', 'yes', 'on'}:
                    endpoint = request.endpoint or 'unknown'
                    method = request.method
                    qn = int(getattr(g, 'sql_query_count', 0) or 0)
                    qt = float(getattr(g, 'sql_query_time_s', 0.0) or 0.0)
                    logger.info(f'PERF SQL: {method} {endpoint} | {qn} queries, {qt:.3f}s')
        except Exception:
            pass
        return response

    # Initialize database extensions
    db.init_app(app)
    migrate.init_app(app, db)
    
    # Initialize logging system (Milestone 2)
    from app.services.logging_service import app_logger
    app_logger.init_app(app)
    
    # Initialize enhanced monitoring service (System Monitoring)
    from app.services.monitoring_service import monitoring_service
    monitoring_service.init_app(app)

    # ---- Optional SQL performance instrumentation ----
    # This is extremely useful for diagnosing 2-3s page loads (DB vs template vs network).
    # It is lightweight, but we still keep it "quiet" unless PERF_SQL_LOG=1 or the request is slow.
    try:
        from sqlalchemy import event

        if not getattr(app, '_perf_sql_listeners_installed', False):
            with app.app_context():
                engine = db.engine

            @event.listens_for(engine, 'before_cursor_execute')
            def _perf_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                try:
                    conn.info['__perf_query_start_time'] = time.perf_counter()
                except Exception:
                    pass

            @event.listens_for(engine, 'after_cursor_execute')
            def _perf_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
                try:
                    start = conn.info.pop('__perf_query_start_time', None)
                    if start is None:
                        return
                    duration = time.perf_counter() - float(start)
                    # Only count if we're in a request context.
                    with contextlib.suppress(Exception):
                        g.sql_query_count = int(getattr(g, 'sql_query_count', 0) or 0) + 1
                        g.sql_query_time_s = float(getattr(g, 'sql_query_time_s', 0.0) or 0.0) + float(duration)
                except Exception:
                    pass

            app._perf_sql_listeners_installed = True
    except Exception:
        # Don't ever break app startup due to perf tooling.
        pass

    # Initialize OAuth + Mail
    oauth.init_app(app)
    mail.init_app(app)

    # Initialize rate limiter
    limiter.init_app(app)

    # Register OAuth providers (only if configured)
    google_id = app.config.get('GOOGLE_CLIENT_ID')
    google_secret = app.config.get('GOOGLE_CLIENT_SECRET')
    if google_id and google_secret:
        oauth.register(
            name='google',
            client_id=google_id,
            client_secret=google_secret,
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'},
        )

    ms_id = app.config.get('MICROSOFT_CLIENT_ID')
    ms_secret = app.config.get('MICROSOFT_CLIENT_SECRET')
    ms_tenant = app.config.get('MICROSOFT_TENANT') or 'common'
    if ms_id and ms_secret:
        oauth.register(
            name='microsoft',
            client_id=ms_id,
            client_secret=ms_secret,
            server_metadata_url=f'https://login.microsoftonline.com/{ms_tenant}/v2.0/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'},
        )
    
    # Initialize extensions
    from flask_wtf.csrf import CSRFProtect
    csrf = CSRFProtect(app)
    
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to access this page.'
    login_manager.login_message_category = 'info'
    # Flask-Login session protection:
    # - In testing, disable to keep the test client stable.
    # - In debug/dev, use a relaxed mode to avoid spurious logouts (e.g., IPv4/IPv6 loopback
    #   differences or varying proxy headers during local development).
    # - In production, keep protection enabled.
    if app.config.get('TESTING'):
        login_manager.session_protection = None
    elif app.debug:
        login_manager.session_protection = 'basic'
    else:
        login_manager.session_protection = 'strong'
    login_manager.refresh_view = 'auth.login'
    login_manager.needs_refresh_message = 'Please re-authenticate to access this page.'
    login_manager.needs_refresh_message_category = 'info'

    @app.before_request
    def _check_session_security():
        """Check session inactivity timeout, version, and password changes."""
        try:
            # Static assets should not require loading the user from the DB.
            # If we touch `current_user` here, Flask-Login will load the user for every image/css/js request.
            path = request.path or ''
            if path.startswith('/static/'):
                return None

            from flask_login import current_user, logout_user
            from flask import session, url_for, flash, abort
            from datetime import datetime, timezone, timedelta
            from app.models import User
            import time

            if not getattr(current_user, 'is_authenticated', False):
                return None

            endpoint = request.endpoint or ''
            path = request.path or ''
            is_asset_like = endpoint in {
                'static',
                'main.organization_logo',
                'main.organization_logo_by_id',
            } or path.startswith('/static/')
            
            # 1. Check session inactivity timeout (30 minutes)
            last_activity = session.get('last_activity_time')
            now_ts = time.time()
            
            if last_activity:
                inactive_seconds = now_ts - last_activity
                if inactive_seconds > 1800:  # 30 minutes
                    logout_user()
                    try:
                        session.clear()
                    except Exception:
                        pass
                    if is_asset_like:
                        return abort(401)
                    flash('Your session expired due to inactivity. Please sign in again.', 'info')
                    return redirect(url_for('auth.login'))
            
            # Update last activity timestamp only for non-asset requests
            if not is_asset_like:
                session['last_activity_time'] = now_ts
            
            # 2. Check session version (for logout-all-devices)
            user_session_version = session.get('session_version')
            if user_session_version is not None:
                db_session_version = getattr(current_user, 'session_version', 1)
                if user_session_version != db_session_version:
                    logout_user()
                    try:
                        session.clear()
                    except Exception:
                        pass
                    if is_asset_like:
                        return abort(401)
                    flash('You have been logged out from all devices. Please sign in again.', 'info')
                    return redirect(url_for('auth.login'))

            # 3. Check password change timestamp (force logout if changed)
            # Query fresh user from DB periodically to get latest password_changed_at.
            # Doing this on every request can be very expensive and slows down all page loads.
            # The interval keeps security guarantees (logout after password change) while reducing DB pressure.
            # Increase from 15s to 60s: password changes are rare, so a 1-minute delay is acceptable.
            password_check_interval = int(app.config.get('SECURITY_DB_CHECK_INTERVAL_SECONDS') or 60)
            last_pwd_check = session.get('last_pwd_check_ts')

            user = None

            # Avoid an extra DB refresh on asset-like requests; they already pay the user_loader DB hit.
            if is_asset_like:
                user = current_user
            else:
                if last_pwd_check is not None and (now_ts - float(last_pwd_check)) < password_check_interval:
                    # Use the user loaded by Flask-Login for this request.
                    user = current_user
                else:
                    from app import db
                    user = db.session.get(User, int(current_user.id))
                    if user:
                        try:
                            db.session.refresh(user)
                        except Exception:
                            pass
                    session['last_pwd_check_ts'] = now_ts

            if not user:
                return None

            pwd_changed_at = getattr(user, 'password_changed_at', None)
            if not pwd_changed_at:
                return None

            if getattr(pwd_changed_at, 'tzinfo', None) is None:
                pwd_changed_at = pwd_changed_at.replace(tzinfo=timezone.utc)

            auth_ts = session.get('auth_time')
            if auth_ts is None:
                # Best-effort: seed from last_login_at so older sessions can still be invalidated.
                last_login_at = getattr(user, 'last_login_at', None)
                if last_login_at:
                    try:
                        session['auth_time'] = int(last_login_at.replace(tzinfo=timezone.utc).timestamp())
                        auth_ts = session.get('auth_time')
                    except Exception:
                        auth_ts = None

            if auth_ts is None:
                return None

            auth_time = datetime.fromtimestamp(int(auth_ts), tz=timezone.utc)
            
            # Add 2-second tolerance to avoid false positives from timestamp precision
            if pwd_changed_at > auth_time + timedelta(seconds=2):
                logout_user()
                try:
                    session.clear()
                except Exception:
                    pass
                if is_asset_like:
                    return abort(401)
                flash('Your password was changed. Please sign in again.', 'info')
                return redirect(url_for('auth.login'))
        except Exception:
            return None

        return None
    
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""
        # Prevent MIME type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        
        # Enable XSS protection in browsers
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Enforce HTTPS (only in production)
        if not app.debug:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions policy (disable dangerous features)
        response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        
        return response
    
    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.upload import bp as upload_bp
    app.register_blueprint(upload_bp)

    from app.onboarding import bp as onboarding_bp
    app.register_blueprint(onboarding_bp, url_prefix='/onboarding')
    
    # Add CSP header for production
    if not app.debug:
        @app.after_request
        def add_csp_header(response):
            """Add Content Security Policy header."""
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://challenges.cloudflare.com; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "img-src 'self' data:; "
                "connect-src 'self'; "
                "frame-src https://challenges.cloudflare.com"
            )
            response.headers['Content-Security-Policy'] = csp
            return response
    
    # Add template context processors
    @app.context_processor
    def inject_csrf_token():
        from flask_wtf.csrf import generate_csrf
        return dict(csrf_token=generate_csrf)

    @app.context_processor
    def inject_current_year():
        from datetime import datetime, timezone
        return {'current_year': datetime.now(timezone.utc).year}

    @app.context_processor
    def inject_org_switcher():
        """Provide organization switcher data to templates.
        
        PERFORMANCE: This runs on EVERY page render. Keep it minimal.
        Only compute expensive data when absolutely needed.
        """
        try:
            from flask_login import current_user
            if not getattr(current_user, 'is_authenticated', False):
                return {}

            # FAST PATH: Skip all DB work for non-navigation pages (assets, AJAX, etc)
            endpoint = request.endpoint or ''
            if endpoint in {'static', 'main.organization_logo', 'main.organization_logo_by_id'}:
                return {}

            user_id = int(getattr(current_user, 'id'))
            active_org_id_raw = getattr(current_user, 'organization_id', None)
            active_org_id = int(active_org_id_raw) if active_org_id_raw else None

            # Aggressive cache: 5 minutes instead of 30 seconds
            cache_seconds = int((app.config.get('ORG_SWITCHER_CACHE_SECONDS') or 300))
            if cache_seconds > 0:
                cache_key = (user_id, active_org_id)
                now = time.monotonic()
                with _ORG_SWITCHER_CONTEXT_CACHE_LOCK:
                    cached = _ORG_SWITCHER_CONTEXT_CACHE.get(cache_key)
                if cached:
                    expires_at, payload = cached
                    if now < expires_at:
                        return payload

            from app.models import Organization, OrganizationMembership

            # Load ONLY org IDs for the switcher (avoid loading RBAC/department relationships).
            memberships_rows = (
                OrganizationMembership.query
                .with_entities(OrganizationMembership.organization_id)
                .filter_by(user_id=user_id, is_active=True)
                .all()
            )
            org_ids = [int(row[0]) for row in memberships_rows]
            orgs = (
                Organization.query
                .filter(Organization.id.in_(org_ids))
                .order_by(Organization.name.asc())
                .all()
            ) if org_ids else []

            # Build minimal org data for switcher
            org_data = [
                {
                    'id': org.id,
                    'name': org.name,
                    'has_logo': bool(org.logo_blob_name),
                    'logo_blob_name': (org.logo_blob_name or ''),
                }
                for org in orgs
            ]

            # Initialize defaults (no expensive queries yet)
            is_org_admin_active = False
            can_invite_member = False
            can_manage_team = False
            can_export_audit = False
            can_manage_org = False
            can_manage_roles = False
            active_role_name = None
            available_roles = []
            user_departments = []
            
            if active_org_id:
                try:
                    # Reuse request-scoped membership + permission caches.
                    membership = current_user.active_membership(org_id=int(active_org_id))
                    if membership:
                        active_role_name = membership.display_role_name

                    can_manage_team = current_user.has_permission('users.manage', org_id=int(active_org_id))
                    can_invite_member = current_user.has_permission('users.invite', org_id=int(active_org_id))
                    can_export_audit = current_user.has_permission('audits.export', org_id=int(active_org_id))
                    can_manage_org = current_user.has_permission('org.manage', org_id=int(active_org_id))
                    can_manage_roles = current_user.has_permission('roles.manage', org_id=int(active_org_id))
                    is_org_admin_active = bool(can_manage_team)

                    # Load roles/departments if the user has invite permissions (for the floating invite modal).
                    if can_invite_member:
                        try:
                            from app.models import RBACRole, Department

                            has_any_role = (
                                RBACRole.query
                                .filter_by(organization_id=int(active_org_id))
                                .limit(1)
                                .first()
                            )
                            if not has_any_role:
                                from app.services.rbac import ensure_rbac_seeded_for_org
                                ensure_rbac_seeded_for_org(int(active_org_id))

                            available_roles = (
                                RBACRole.query
                                .filter_by(organization_id=int(active_org_id))
                                .order_by(RBACRole.name.asc())
                                .all()
                            )

                            user_departments = (
                                Department.query
                                .filter_by(organization_id=int(active_org_id))
                                .order_by(Department.name.asc())
                                .all()
                            )
                        except Exception:
                            available_roles = []
                            user_departments = []
                except Exception:
                    pass

            # Only cache lightweight data structures; avoid caching ORM objects across requests.
            payload = {
                'user_organizations': org_data,
                'user_organizations_with_logos': org_data,
                'is_org_admin_active': is_org_admin_active,
                'can_invite_member': can_invite_member,
                'can_manage_team': can_manage_team,
                'can_export_audit': can_export_audit,
                'can_manage_org': can_manage_org,
                'can_manage_roles': can_manage_roles,
                'active_role_name': active_role_name,
                'available_roles': [{'id': r.id, 'name': r.name} for r in (available_roles or [])],
                'user_departments': [{'id': d.id, 'name': d.name} for d in (user_departments or [])],
            }

            if cache_seconds > 0:
                try:
                    cache_key = (user_id, active_org_id)
                    expires_at = time.monotonic() + max(1, cache_seconds)
                    with _ORG_SWITCHER_CONTEXT_CACHE_LOCK:
                        _ORG_SWITCHER_CONTEXT_CACHE[cache_key] = (expires_at, payload)
                except Exception:
                    pass

            return payload
        except Exception:
            return {}
    
    # Add custom template filters
    @app.template_filter('datetime_format')
    def datetime_format(value, format='%b %d, %Y at %I:%M %p'):
        """Format datetime for templates."""
        from datetime import datetime
        if isinstance(value, str):
            try:
                value = datetime.fromisoformat(value.replace('Z', '+00:00'))
            except:
                return 'Unknown date'
        if isinstance(value, datetime):
            return value.strftime(format)
        return 'Unknown date'

    @app.template_filter('file_size_format')
    def file_size_format(value):
        """Format file size bytes for templates."""
        if not value:
            return 'Unknown'
        try:
            size = float(value)
        except (TypeError, ValueError):
            return 'Unknown'
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def _sqlite_db_file_from_uri(uri: str) -> str | None:
        if not uri or not uri.startswith('sqlite:///'):
            return None

        rel = uri[len('sqlite:///'):]

        # If it looks like an absolute Windows path, normalize it.
        # Examples: sqlite:////C:/path/db.sqlite or sqlite:///C:/path/db.sqlite
        if rel.startswith('/') and len(rel) > 2 and rel[2] == ':':
            rel = rel[1:]
        if len(rel) > 1 and rel[1] == ':':
            return os.path.abspath(rel)

        # Otherwise treat as instance-relative (Flask-SQLAlchemy behavior for sqlite:///relative.db).
        return os.path.abspath(os.path.join(app.instance_path, rel))

    @app.cli.command('reset-local-db')
    @click.option('--yes', is_flag=True, help='Skip confirmation prompt.')
    def reset_local_db(yes: bool):
        """Delete the local SQLite DB file and re-apply migrations (DEV ONLY)."""
        import subprocess
        import sys

        uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        db_file = _sqlite_db_file_from_uri(uri)
        if not db_file:
            raise click.ClickException(
                f"Refusing to reset because SQLALCHEMY_DATABASE_URI is not a local sqlite file: {uri}"
            )

        if not yes:
            click.echo(f"This will delete: {db_file}")
            click.echo('This is intended for local development/testing only.')
            if not click.confirm('Continue?', default=False):
                click.echo('Aborted.')
                return

        os.makedirs(os.path.dirname(db_file), exist_ok=True)
        if os.path.exists(db_file):
            os.remove(db_file)
            click.echo('Deleted existing DB file.')
        else:
            click.echo('DB file did not exist; continuing.')

        # Recreate schema via migrations in a fresh process (more reliable on Windows).
        project_root = os.path.abspath(os.path.join(app.root_path, os.pardir))
        cmd = [sys.executable, '-m', 'flask', '--app', 'run:app', 'db', 'upgrade']
        click.echo('Applying migrations...')
        subprocess.run(cmd, cwd=project_root, check=True)
        click.echo('Migrations applied. Local DB is ready.')

    @app.cli.command('wipe-test-data')
    @click.option('--yes', is_flag=True, help='Skip confirmation prompt.')
    @click.option(
        '--force',
        is_flag=True,
        help='Allow running even when DEBUG is false (requires ALLOW_DATA_WIPE=1).',
    )
    def wipe_test_data(yes: bool, force: bool):
        """Wipe application data (users/orgs/docs) but keep schema + migrations.

        Intended for development/testing so you can reuse the same email and rerun flows.
        Refuses to run in production unless --force and ALLOW_DATA_WIPE=1 are set.
        """
        from sqlalchemy import text

        is_debug = bool(app.config.get('DEBUG'))
        allow_force = (os.environ.get('ALLOW_DATA_WIPE') or '').strip() in {'1', 'true', 'yes', 'on'}
        if not is_debug:
            if not (force and allow_force):
                raise click.ClickException(
                    'Refusing to wipe data because DEBUG is false. '\
                    'Use a dev database, or run with --force and set ALLOW_DATA_WIPE=1.'
                )

        uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        dialect = db.engine.dialect.name

        if not yes:
            click.echo('This will permanently delete application data (users, orgs, memberships, documents).')
            click.echo(f'Database: {dialect} ({uri})')
            if not click.confirm('Continue?', default=False):
                click.echo('Aborted.')
                return

        # Wipe tables defined in SQLAlchemy metadata (keeps alembic_version intact).
        table_names = [t.name for t in db.metadata.sorted_tables]
        if not table_names:
            click.echo('No tables found in metadata; nothing to wipe.')
            return

        try:
            if dialect == 'postgresql':
                quoted = ', '.join([f'"{name}"' for name in table_names])
                db.session.execute(text(f'TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE'))
            else:
                # SQLite/MySQL/etc: delete rows in reverse dependency order.
                for name in reversed(table_names):
                    db.session.execute(text(f'DELETE FROM "{name}"'))

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise click.ClickException(f'Failed wiping data: {e}')

        click.echo('Wiped application data. Schema + migrations remain unchanged.')

    @app.cli.command('reset-org-state')
    @click.option('--org-id', type=int, required=True, help='Organization ID to reset.')
    @click.option('--yes', is_flag=True, help='Skip confirmation prompt.')
    @click.option(
        '--force',
        is_flag=True,
        help='Allow running even when DEBUG is false (requires ALLOW_DATA_WIPE=1).',
    )
    @click.option('--reset-declarations/--keep-declarations', default=True, show_default=True)
    @click.option('--reset-privacy-ack/--keep-privacy-ack', default=True, show_default=True)
    @click.option('--reset-billing/--keep-billing', default=True, show_default=True)
    def reset_org_state(
        org_id: int,
        yes: bool,
        force: bool,
        reset_declarations: bool,
        reset_privacy_ack: bool,
        reset_billing: bool,
    ):
        """Reset onboarding/billing fields for a single org (DEV ONLY).

        This is useful when you want to re-test onboarding steps without creating new users.
        It does NOT delete users or memberships.
        """
        from app.models import Organization

        is_debug = bool(app.config.get('DEBUG'))
        allow_force = (os.environ.get('ALLOW_DATA_WIPE') or '').strip() in {'1', 'true', 'yes', 'on'}
        if not is_debug:
            if not (force and allow_force):
                raise click.ClickException(
                    'Refusing to reset org state because DEBUG is false. '\
                    'Use a dev database, or run with --force and set ALLOW_DATA_WIPE=1.'
                )

        org = db.session.get(Organization, int(org_id))
        if not org:
            raise click.ClickException(f'Organization not found: {org_id}')

        if not yes:
            click.echo(f'Organization: {org.id} / {org.name}')
            click.echo('This will reset selected fields:')
            click.echo(f'- Declarations: {reset_declarations}')
            click.echo(f'- Privacy ack:  {reset_privacy_ack}')
            click.echo(f'- Billing:      {reset_billing}')
            if not click.confirm('Continue?', default=False):
                click.echo('Aborted.')
                return

        try:
            if reset_declarations:
                org.operates_in_australia = None
                org.declarations_accepted_at = None
                org.declarations_accepted_by_user_id = None

            if reset_privacy_ack:
                org.data_processing_ack_at = None
                org.data_processing_ack_by_user_id = None

            if reset_billing:
                org.billing_email = None
                org.billing_address = None

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise click.ClickException(f'Failed resetting org state: {e}')

        click.echo('Organization state reset. Users/memberships were not changed.')

    @app.cli.command('purge-users')
    @click.option(
        '--email',
        'emails',
        multiple=True,
        required=True,
        help='Email address to purge. Can be provided multiple times.',
    )
    @click.option('--yes', is_flag=True, help='Skip confirmation prompt.')
    @click.option(
        '--force',
        is_flag=True,
        help='Allow running even when DEBUG is false (requires ALLOW_DATA_WIPE=1).',
    )
    def purge_users(emails: tuple[str, ...], yes: bool, force: bool):
        """Delete users by email and remove their related data.

        This is intended for development/testing so you can re-run invite/login flows
        using the same email addresses without wiping the whole database.

        Deletes:
        - the User row
        - OrganizationMembership rows (via SQLAlchemy cascade)
        - Document rows uploaded by the user
        - LoginEvent rows for that user
        """

        from app.models import User, Document, LoginEvent

        is_debug = bool(app.config.get('DEBUG'))
        allow_force = (os.environ.get('ALLOW_DATA_WIPE') or '').strip().lower() in {'1', 'true', 'yes', 'on'}
        if not is_debug:
            if not (force and allow_force):
                raise click.ClickException(
                    'Refusing to purge users because DEBUG is false. '
                    'Use a dev database, or run with --force and set ALLOW_DATA_WIPE=1.'
                )

        normalized = sorted({(e or '').strip().lower() for e in emails if (e or '').strip()})
        if not normalized:
            raise click.ClickException('No valid --email values provided.')

        uri = app.config.get('SQLALCHEMY_DATABASE_URI')
        dialect = db.engine.dialect.name

        if not yes:
            click.echo('This will permanently delete users and their related data:')
            for e in normalized:
                click.echo(f'- {e}')
            click.echo(f'Database: {dialect} ({uri})')
            if not click.confirm('Continue?', default=False):
                click.echo('Aborted.')
                return

        deleted_users = 0
        for email in normalized:
            user = User.query.filter_by(email=email).first()
            if not user:
                click.echo(f'Not found: {email}')
                continue

            uid = int(user.id)

            try:
                # Delete documents uploaded by this user.
                Document.query.filter(Document.uploaded_by == uid).delete(synchronize_session=False)

                # Delete login events for this user (or matching email fallback).
                LoginEvent.query.filter((LoginEvent.user_id == uid) | (LoginEvent.email == email)).delete(synchronize_session=False)

                # Delete user (memberships cascade via relationship).
                db.session.delete(user)
                db.session.flush()
                deleted_users += 1
                click.echo(f'Purged: {email}')
            except Exception as e:
                db.session.rollback()
                raise click.ClickException(f'Failed purging {email}: {e}')

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise click.ClickException(f'Failed committing purge: {e}')

        click.echo(f'Done. Purged users: {deleted_users}')
    
    return app