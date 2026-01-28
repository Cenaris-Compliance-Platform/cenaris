import os
from datetime import timedelta
from dotenv import load_dotenv

load_dotenv()


def _normalize_database_url(url: str | None) -> str | None:
    if not url:
        return url
    # Some platforms provide "postgres://" but SQLAlchemy expects "postgresql://"
    if url.startswith('postgres://'):
        return 'postgresql://' + url[len('postgres://'):]
    return url

class Config:
    """Base configuration class."""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    
    # Azure Storage Configuration
    AZURE_STORAGE_CONNECTION_STRING = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    AZURE_CONTAINER_NAME = os.environ.get('AZURE_CONTAINER_NAME') or 'compliance-documents'
    
    # Database Configuration
    # For SQLite, Flask-SQLAlchemy resolves relative file paths against the Flask instance folder.
    # Use a plain filename here (not "instance/..."), otherwise it may become "instance/instance/...".
    DATABASE_URL = _normalize_database_url(os.environ.get('DATABASE_URL')) or 'sqlite:///compliance.db'

    # SQLAlchemy (Milestone 1)
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # SQL logging is expensive and can add noticeable latency (especially with remote DBs).
    # Enable only when debugging.
    SQLALCHEMY_ECHO = (os.environ.get('SQLALCHEMY_ECHO') or '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    
    # Database Connection Pooling (Production)
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,           # Number of connections to keep in the pool
        'max_overflow': 20,        # Max connections beyond pool_size
        'pool_recycle': 3600,      # Recycle connections after 1 hour
        'pool_pre_ping': True,     # Verify connections before using them
        'pool_timeout': 30,        # Timeout for getting a connection from pool
    }

    # OAuth (Google / Microsoft)
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    MICROSOFT_CLIENT_ID = os.environ.get('MICROSOFT_CLIENT_ID')
    MICROSOFT_CLIENT_SECRET = os.environ.get('MICROSOFT_CLIENT_SECRET')
    # 'common' supports consumer + org accounts; you can set a tenant id for single-tenant.
    MICROSOFT_TENANT = os.environ.get('MICROSOFT_TENANT') or 'common'

    # Email (Forgot password)
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = (os.environ.get('MAIL_USE_TLS') or 'true').strip().lower() in {'1', 'true', 'yes', 'on'}
    MAIL_USE_SSL = (os.environ.get('MAIL_USE_SSL') or 'false').strip().lower() in {'1', 'true', 'yes', 'on'}
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME')
    
    # SMTP connection timeout (prevents worker hangs when SMTP is unreachable)
    MAIL_TIMEOUT = 10

    # Email verification (token-based)
    REQUIRE_EMAIL_VERIFICATION = (os.environ.get('REQUIRE_EMAIL_VERIFICATION') or 'false').strip().lower() in {'1', 'true', 'yes', 'on'}

    # CAPTCHA (Cloudflare Turnstile) - optional
    TURNSTILE_SITE_KEY = os.environ.get('TURNSTILE_SITE_KEY')
    TURNSTILE_SECRET_KEY = os.environ.get('TURNSTILE_SECRET_KEY')
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'pdf', 'docx'}
    
    # Security Configuration
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None

    # Session cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)

    # Remember-me cookies (Flask-Login)
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'

    # Rate limiting (Flask-Limiter)
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI') or 'memory://'

    # Feature flags
    # ML/ADLS summary is not shipped yet; keep disabled unless explicitly enabled.
    ML_SUMMARY_ENABLED = (os.environ.get('ML_SUMMARY_ENABLED') or '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    
    # Azure Application Insights (Milestone 2: System Logging)
    APPINSIGHTS_CONNECTION_STRING = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
    APPINSIGHTS_ENABLED = bool(APPINSIGHTS_CONNECTION_STRING)
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_RETENTION_DAYS = int(os.environ.get('LOG_RETENTION_DAYS') or 90)
    
    # Security Event Logging
    LOG_SECURITY_EVENTS = True   # Always log security events
    LOG_ACCESS_EVENTS = True     # Re-enabled with OpenTelemetry SDK (Python 3.13 compatible)
    
    @staticmethod
    def init_app(app):
        pass

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    DATABASE_URL = _normalize_database_url(os.environ.get('DEV_DATABASE_URL')) or 'sqlite:///compliance_dev.db'

    # Keep SQLAlchemy in sync
    SQLALCHEMY_DATABASE_URI = DATABASE_URL

    # Defaults for dev convenience
    REQUIRE_EMAIL_VERIFICATION = (os.environ.get('REQUIRE_EMAIL_VERIFICATION') or 'false').strip().lower() in {'1', 'true', 'yes', 'on'}

class ProductionConfig(Config):
    """Production configuration."""
    DEBUG = False

    # Assume HTTPS in production; secure cookies.
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True

    # In production, default to requiring email verification unless explicitly disabled.
    REQUIRE_EMAIL_VERIFICATION = (os.environ.get('REQUIRE_EMAIL_VERIFICATION') or 'true').strip().lower() in {'1', 'true', 'yes', 'on'}
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Log to stderr in production
        import logging
        from logging import StreamHandler
        file_handler = StreamHandler()
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)


class TestingConfig(DevelopmentConfig):
    """Testing configuration.

    Uses a local SQLite database and disables CSRF so Flask test clients can
    post forms without having to scrape tokens.
    """

    TESTING = True
    WTF_CSRF_ENABLED = False
    WTF_CSRF_CHECK_DEFAULT = False
    DATABASE_URL = _normalize_database_url(os.environ.get('TEST_DATABASE_URL')) or 'sqlite:///test.db'
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    # Disable secure cookies in testing so they work with test client
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}