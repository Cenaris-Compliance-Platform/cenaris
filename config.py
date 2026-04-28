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
    SECRET_KEY = os.environ.get('SECRET_KEY')
    
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

    # Billing (Stripe)
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')
    STRIPE_WEBHOOK_TOLERANCE_SECONDS = int(os.environ.get('STRIPE_WEBHOOK_TOLERANCE_SECONDS') or 300)
    STRIPE_PRICE_ID_STARTER = os.environ.get('STRIPE_PRICE_ID_STARTER')
    STRIPE_PRICE_ID_TEAM = os.environ.get('STRIPE_PRICE_ID_TEAM')
    STRIPE_PRICE_ID_SCALE = os.environ.get('STRIPE_PRICE_ID_SCALE')
    STRIPE_PRICE_ID_GROWTH = os.environ.get('STRIPE_PRICE_ID_GROWTH')
    STRIPE_PRICE_ID_ENTERPRISE = os.environ.get('STRIPE_PRICE_ID_ENTERPRISE')
    APP_BASE_URL = os.environ.get('APP_BASE_URL')

    # Billing access controls
    SUPER_ADMIN_EMAILS = (
        os.environ.get('SUPER_ADMIN_EMAILS')
        or 'muhammadhaiderali2710@gmail.com'
    )
    INTERNAL_TEAM_EMAILS = (
        os.environ.get('INTERNAL_TEAM_EMAILS')
        or 'muhammadhaideraliroy2710@gmail.com'
    )
    
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

    # RAG corpus source (JSONL built from NDIS regulatory PDF)
    NDIS_RAG_CORPUS_PATH = os.environ.get('NDIS_RAG_CORPUS_PATH') or 'data/rag/ndis/ndis_chunks.jsonl'
    NDIS_POLICY_PROMPT_PATH = os.environ.get('NDIS_POLICY_PROMPT_PATH') or 'app/ai/prompts/ndis_policy_system_prompt.txt'

    # Policy draft generation mode (deterministic fallback remains default-safe)
    POLICY_DRAFT_USE_LLM = (os.environ.get('POLICY_DRAFT_USE_LLM') or '0').strip().lower() in {'1', 'true', 'yes', 'on'}

    # AI runtime guardrails (cost + safety)
    AI_ENVIRONMENT = (os.environ.get('AI_ENVIRONMENT') or 'development').strip().lower()
    AI_MAX_QUERY_CHARS = int(os.environ.get('AI_MAX_QUERY_CHARS') or 1200)
    AI_MAX_TOP_K = int(os.environ.get('AI_MAX_TOP_K') or 5)
    AI_MAX_CITATION_TEXT_CHARS = int(os.environ.get('AI_MAX_CITATION_TEXT_CHARS') or 600)
    AI_MAX_ANSWER_CHARS = int(os.environ.get('AI_MAX_ANSWER_CHARS') or 2000)
    AI_MAX_POLICY_DRAFT_CHARS = int(os.environ.get('AI_MAX_POLICY_DRAFT_CHARS') or 6000)
    AI_POLICY_LLM_ALLOW_IN_DEVELOPMENT = (os.environ.get('AI_POLICY_LLM_ALLOW_IN_DEVELOPMENT') or '0').strip().lower() in {'1', 'true', 'yes', 'on'}
    AI_RAG_RATE_LIMIT = os.environ.get('AI_RAG_RATE_LIMIT') or '20 per minute'
    AI_POLICY_RATE_LIMIT = os.environ.get('AI_POLICY_RATE_LIMIT') or '10 per minute'
    MIN_AUDIT_LOG_RETENTION_DAYS = max(1, int(os.environ.get('MIN_AUDIT_LOG_RETENTION_DAYS') or 90))
    AI_USAGE_RETENTION_DAYS = max(
        MIN_AUDIT_LOG_RETENTION_DAYS,
        int(os.environ.get('AI_USAGE_RETENTION_DAYS') or 90),
    )
    ASSISTANT_CHAT_USE_LLM = (os.environ.get('ASSISTANT_CHAT_USE_LLM') or '1').strip().lower() in {'1', 'true', 'yes', 'on'}
    ASSISTANT_CHAT_MAX_OUTPUT_TOKENS = int(os.environ.get('ASSISTANT_CHAT_MAX_OUTPUT_TOKENS') or 550)
    ASSISTANT_CHAT_TEMPERATURE = float(os.environ.get('ASSISTANT_CHAT_TEMPERATURE') or 0.2)

    # Azure OpenAI (used when POLICY_DRAFT_USE_LLM=true)
    AZURE_OPENAI_ENDPOINT = os.environ.get('AZURE_OPENAI_ENDPOINT')
    AZURE_OPENAI_API_KEY = os.environ.get('AZURE_OPENAI_API_KEY')
    AZURE_OPENAI_API_VERSION = os.environ.get('AZURE_OPENAI_API_VERSION') or '2024-10-21'
    AZURE_OPENAI_CHAT_DEPLOYMENT = os.environ.get('AZURE_OPENAI_CHAT_DEPLOYMENT')
    AZURE_OPENAI_CHAT_DEPLOYMENT_MINI = os.environ.get('AZURE_OPENAI_CHAT_DEPLOYMENT_MINI')
    AZURE_OPENAI_CHAT_DEPLOYMENT_WRITER = os.environ.get('AZURE_OPENAI_CHAT_DEPLOYMENT_WRITER')
    AZURE_OPENAI_ASSISTANT_DEPLOYMENT = (
        os.environ.get('AZURE_OPENAI_ASSISTANT_DEPLOYMENT')
        or os.environ.get('AZURE_OPENAI_CHAT_DEPLOYMENT_MINI')
        or os.environ.get('AZURE_OPENAI_CHAT_DEPLOYMENT')
    )
    AZURE_OPENAI_TIMEOUT_SECONDS = int(os.environ.get('AZURE_OPENAI_TIMEOUT_SECONDS') or 30)
    AZURE_OPENAI_POLICY_MAX_OUTPUT_TOKENS_TEMPLATE = int(os.environ.get('AZURE_OPENAI_POLICY_MAX_OUTPUT_TOKENS_TEMPLATE') or 1200)
    AZURE_OPENAI_POLICY_MAX_OUTPUT_TOKENS_TEMPLATE_PLUS = int(os.environ.get('AZURE_OPENAI_POLICY_MAX_OUTPUT_TOKENS_TEMPLATE_PLUS') or 2200)
    AZURE_OPENAI_POLICY_MAX_OUTPUT_TOKENS_FULL_DRAFT = int(os.environ.get('AZURE_OPENAI_POLICY_MAX_OUTPUT_TOKENS_FULL_DRAFT') or 3800)
    AZURE_OPENAI_POLICY_MAX_OUTPUT_TOKENS = int(os.environ.get('AZURE_OPENAI_POLICY_MAX_OUTPUT_TOKENS') or 1400)
    AZURE_OPENAI_SUMMARY_MAX_OUTPUT_TOKENS = int(os.environ.get('AZURE_OPENAI_SUMMARY_MAX_OUTPUT_TOKENS') or 450)

    # Demo provider for fast validation of AI flow (non-production helper)
    OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')
    OPENROUTER_MODEL = os.environ.get('OPENROUTER_MODEL') or 'mistralai/mistral-7b-instruct:free'
    OPENROUTER_ASSISTANT_MODEL = os.environ.get('OPENROUTER_ASSISTANT_MODEL') or OPENROUTER_MODEL
    
    # Azure Application Insights (Milestone 2: System Logging)
    APPINSIGHTS_CONNECTION_STRING = os.environ.get('APPLICATIONINSIGHTS_CONNECTION_STRING')
    APPINSIGHTS_ENABLED = bool(APPINSIGHTS_CONNECTION_STRING)
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL') or 'INFO'
    LOG_RETENTION_DAYS = max(
        MIN_AUDIT_LOG_RETENTION_DAYS,
        int(os.environ.get('LOG_RETENTION_DAYS') or 90),
    )
    
    # Security Event Logging
    LOG_SECURITY_EVENTS = True   # Always log security events
    LOG_ACCESS_EVENTS = True     # Re-enabled with OpenTelemetry SDK (Python 3.13 compatible)
    
    # Alert Configuration (Free code-based alerts - Milestone 2)
    ALERTS_ENABLED = (os.environ.get('ALERTS_ENABLED') or 'false').strip().lower() in {'1', 'true', 'yes', 'on'}
    ALERT_EMAILS = os.environ.get('ALERT_EMAILS') or ''  # Comma-separated list of emails
    
    @staticmethod
    def init_app(app):
        if app.config.get('SECRET_KEY'):
            return
        if app.config.get('TESTING'):
            # Keep tests deterministic when SECRET_KEY is not provided by the test harness.
            app.config['SECRET_KEY'] = 'test-secret-key'
            return
        raise RuntimeError('SECRET_KEY is required. Set it via environment variables (for example in .env).')

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
    # Keep policy draft tests deterministic/offline by default.
    POLICY_DRAFT_USE_LLM = False
    AI_POLICY_LLM_ALLOW_IN_DEVELOPMENT = False
    ASSISTANT_CHAT_USE_LLM = False
    # Disable secure cookies in testing so they work with test client
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False

config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}