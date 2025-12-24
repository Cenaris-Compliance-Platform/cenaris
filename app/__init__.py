from flask import Flask, redirect, request
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import config
import os

import click

from authlib.integrations.flask_client import OAuth
from flask_mail import Mail

login_manager = LoginManager()

# Database (Milestone 1)
db = SQLAlchemy()
migrate = Migrate()

# OAuth + Mail
oauth = OAuth()
mail = Mail()

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login."""
    from app.models import User
    return User.query.get(int(user_id))

def create_app(config_name=None):
    """Application factory pattern."""
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG') or 'default'

    if isinstance(config_name, str):
        config_name = config_name.strip()

    if config_name not in config:
        config_name = 'default'
    
    app = Flask(__name__)
    # Ensure the instance folder exists early so SQLite can create/open the DB file.
    os.makedirs(app.instance_path, exist_ok=True)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    @app.before_request
    def _normalize_localhost_for_turnstile():
        """Turnstile widgets are bound to hostnames; localhost != 127.0.0.1.

        In local development, users often browse via http://127.0.0.1:PORT.
        If Turnstile is configured for 'localhost' only, Cloudflare shows
        'Invalid domain'. Redirect GET/HEAD requests to localhost to match.
        """
        # The error happens at widget render time, so the site key alone is
        # sufficient to consider Turnstile "enabled" for this normalization.
        if not app.config.get('TURNSTILE_SITE_KEY'):
            return None

        if request.method not in {'GET', 'HEAD'}:
            return None

        host = (request.host or '')
        host_only = host.split(':', 1)[0]
        if host_only != '127.0.0.1':
            return None

        port = host.split(':', 1)[1] if ':' in host else ''
        new_host = f'localhost:{port}' if port else 'localhost'

        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(request.url)
        return redirect(urlunsplit((parts.scheme, new_host, parts.path, parts.query, parts.fragment)), code=302)

    # Initialize database extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Initialize OAuth + Mail
    oauth.init_app(app)
    mail.init_app(app)

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
    # Flask-Login's FlaskLoginClient (used in tests) only seeds _user_id/_fresh.
    # With 'strong' protection, Flask-Login may invalidate those sessions.
    login_manager.session_protection = 'basic' if app.config.get('TESTING') else 'strong'
    login_manager.refresh_view = 'auth.login'
    login_manager.needs_refresh_message = 'Please re-authenticate to access this page.'
    login_manager.needs_refresh_message_category = 'info'
    
    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.main import bp as main_bp
    app.register_blueprint(main_bp)
    
    from app.upload import bp as upload_bp
    app.register_blueprint(upload_bp)

    from app.onboarding import bp as onboarding_bp
    app.register_blueprint(onboarding_bp, url_prefix='/onboarding')
    
    # Add security headers
    @app.after_request
    def add_security_headers(response):
        """Add security headers to all responses."""
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response
    
    # Add CSP header for production
    if not app.debug:
        @app.after_request
        def add_csp_header(response):
            """Add Content Security Policy header."""
            csp = (
                "default-src 'self'; "
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                "font-src 'self' https://cdn.jsdelivr.net; "
                "img-src 'self' data:; "
                "connect-src 'self'"
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
        """Provide organization switcher data to templates."""
        try:
            from flask_login import current_user
            if not getattr(current_user, 'is_authenticated', False):
                return {}

            from app.models import Organization, OrganizationMembership

            orgs = (
                Organization.query
                .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
                .filter(OrganizationMembership.user_id == int(current_user.id), OrganizationMembership.is_active.is_(True))
                .order_by(Organization.name.asc())
                .all()
            )

            active_org_id = getattr(current_user, 'organization_id', None)
            is_org_admin_active = False
            if active_org_id:
                try:
                    is_org_admin_active = bool(current_user.is_org_admin(int(active_org_id)))
                except Exception:
                    is_org_admin_active = False

            return {
                'user_organizations': orgs,
                'is_org_admin_active': is_org_admin_active,
            }
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

        org = Organization.query.get(int(org_id))
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
    
    return app