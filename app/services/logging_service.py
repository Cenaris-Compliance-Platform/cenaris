"""
Centralized logging service for system-wide logging and monitoring.
Integrates with Azure Application Insights for cloud-based log management.
"""

import logging
import os
import json
import time
from datetime import datetime, timezone
from functools import wraps
from flask import request, g
from flask_login import current_user

# OpenTelemetry and Azure Monitor imports
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    from azure.monitor.opentelemetry.exporter import AzureMonitorLogExporter, AzureMonitorTraceExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    AZURE_LOGGING_AVAILABLE = True
except ImportError:
    AZURE_LOGGING_AVAILABLE = False

logger = logging.getLogger(__name__)


class SecurityEventLogger:
    """Logs security-related events for audit trails."""
    
    EVENT_TYPES = {
        'LOGIN_SUCCESS': 'User logged in successfully',
        'LOGIN_FAILURE': 'Failed login attempt',
        'LOGOUT': 'User logged out',
        'PASSWORD_CHANGE': 'Password changed',
        'PASSWORD_RESET_REQUEST': 'Password reset requested',
        'PASSWORD_RESET_COMPLETE': 'Password reset completed',
        'EMAIL_VERIFICATION': 'Email verified',
        'ACCOUNT_LOCKED': 'Account locked due to failed attempts',
        'ACCOUNT_UNLOCKED': 'Account unlocked',
        'PERMISSION_DENIED': 'Permission denied for action',
        'ROLE_CHANGED': 'User role changed',
        'ORGANIZATION_SWITCHED': 'User switched organization',
        'ORGANIZATION_CREATED': 'New organization created',
        'USER_INVITED': 'User invited to organization',
        'USER_REMOVED': 'User removed from organization',
        'DOCUMENT_UPLOADED': 'Document uploaded',
        'DOCUMENT_DOWNLOADED': 'Document downloaded',
        'SETTINGS_CHANGED': 'Settings changed',
        'DATA_EXPORTED': 'Data exported',
    }
    
    def __init__(self, app=None):
        self.logger = logging.getLogger('security')
        self.logger.setLevel(logging.INFO)
        self.app = app
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app context."""
        self.app = app
        self._configure_logger()
    
    def _configure_logger(self):
        """Configure the security logger with appropriate handlers."""
        # Console handler for local development
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '[%(asctime)s] [SECURITY] %(levelname)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        # Clear existing handlers
        self.logger.handlers = []
        self.logger.addHandler(console_handler)
        
        # Azure Monitor handler (if enabled)
        if self.app and self.app.config.get('APPINSIGHTS_ENABLED') and AZURE_LOGGING_AVAILABLE:
            try:
                connection_string = self.app.config.get('APPINSIGHTS_CONNECTION_STRING')
                if connection_string:
                    # Create logger provider with Azure Monitor exporter
                    logger_provider = LoggerProvider()
                    exporter = AzureMonitorLogExporter(connection_string=connection_string)
                    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
                    
                    # Create and add OpenTelemetry logging handler
                    handler = LoggingHandler(logger_provider=logger_provider)
                    handler.setLevel(logging.INFO)
                    self.logger.addHandler(handler)
                    print("[INFO] Security logger Azure Monitor integration enabled")
            except Exception as e:
                print(f"[WARNING] Could not initialize Azure logging for security logger: {str(e)}")
    
    def log_event(self, event_type, user_id=None, org_id=None, details=None, ip_address=None):
        """
        Log a security event.
        
        Args:
            event_type: Type of event from EVENT_TYPES
            user_id: ID of the user involved (optional)
            org_id: ID of the organization (optional)
            details: Additional details dict (optional)
            ip_address: IP address of the request (optional)
        """
        try:
            if event_type not in self.EVENT_TYPES:
                self.logger.warning(f"Unknown event type: {event_type}")
                return
            
            # Build event data
            event_data = {
                'event_type': event_type,
                'description': self.EVENT_TYPES[event_type],
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'user_id': user_id or (current_user.id if hasattr(current_user, 'id') and current_user.is_authenticated else None),
                'org_id': org_id,
                'ip_address': ip_address or (request.remote_addr if request else None),
                'user_agent': str(request.headers.get('User-Agent', 'Unknown')) if request else None,
            }
            
            if details:
                event_data['details'] = details
            
            # Log as JSON for structured logging
            self.logger.info(json.dumps(event_data))
        except Exception as e:
            # Silently handle errors to prevent breaking the application
            print(f"[ERROR] Failed to log security event: {str(e)}")


class AccessLogger:
    """Logs HTTP requests and responses for monitoring."""
    
    def __init__(self, app=None):
        self.logger = logging.getLogger('access')
        self.logger.setLevel(logging.INFO)
        self.app = app
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app context."""
        self.app = app
        self._configure_logger()
        self._register_middleware()
    
    def _configure_logger(self):
        """Configure the access logger with appropriate handlers."""
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        formatter = logging.Formatter(
            '[%(asctime)s] [ACCESS] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        # Clear existing handlers
        self.logger.handlers = []
        self.logger.addHandler(console_handler)
        
        # Azure Monitor handler (if enabled)
        if self.app and self.app.config.get('APPINSIGHTS_ENABLED') and AZURE_LOGGING_AVAILABLE:
            try:
                connection_string = self.app.config.get('APPINSIGHTS_CONNECTION_STRING')
                if connection_string:
                    logger_provider = LoggerProvider()
                    exporter = AzureMonitorLogExporter(connection_string=connection_string)
                    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
                    
                    handler = LoggingHandler(logger_provider=logger_provider)
                    handler.setLevel(logging.INFO)
                    self.logger.addHandler(handler)
            except Exception as e:
                print(f"[WARNING] Could not initialize Azure logging for access logger: {str(e)}")
    
    def _register_middleware(self):
        """Register Flask before/after request handlers."""
        if not self.app:
            return
        
        @self.app.before_request
        def before_request():
            g.request_start_time = time.time()
        
        @self.app.after_request
        def after_request(response):
            if not self.app.config.get('LOG_ACCESS_EVENTS', False):
                return response
            
            try:
                self.log_request(response)
            except Exception:
                pass  # Silently handle errors
            
            return response
    
    def log_request(self, response=None):
        """Log details about the current HTTP request."""
        try:
            duration = None
            if hasattr(g, 'request_start_time'):
                duration = time.time() - g.request_start_time
            
            log_data = {
                'method': request.method,
                'path': request.path,
                'status_code': response.status_code if response else None,
                'duration_ms': round(duration * 1000, 2) if duration else None,
                'user_id': current_user.id if hasattr(current_user, 'id') and current_user.is_authenticated else None,
                'ip_address': request.remote_addr,
                'user_agent': str(request.headers.get('User-Agent', 'Unknown')),
                'timestamp': datetime.now(timezone.utc).isoformat(),
            }
            
            self.logger.info(json.dumps(log_data))
        except Exception as e:
            print(f"[ERROR] Failed to log access request: {str(e)}")


class ErrorLogger:
    """Logs application errors and exceptions."""
    
    def __init__(self, app=None):
        self.logger = logging.getLogger('error')
        self.logger.setLevel(logging.ERROR)
        self.app = app
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app context."""
        self.app = app
        self._configure_logger()
        self._register_error_handlers()
    
    def _configure_logger(self):
        """Configure the error logger with appropriate handlers."""
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.ERROR)
        formatter = logging.Formatter(
            '[%(asctime)s] [ERROR] %(levelname)s: %(message)s\n%(exc_info)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(formatter)
        
        # Clear existing handlers
        self.logger.handlers = []
        self.logger.addHandler(console_handler)
        
        # Azure Monitor handler (if enabled)
        if self.app and self.app.config.get('APPINSIGHTS_ENABLED') and AZURE_LOGGING_AVAILABLE:
            try:
                connection_string = self.app.config.get('APPINSIGHTS_CONNECTION_STRING')
                if connection_string:
                    logger_provider = LoggerProvider()
                    exporter = AzureMonitorLogExporter(connection_string=connection_string)
                    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
                    
                    handler = LoggingHandler(logger_provider=logger_provider)
                    handler.setLevel(logging.ERROR)
                    self.logger.addHandler(handler)
            except Exception as e:
                print(f"[WARNING] Could not initialize Azure logging for error logger: {str(e)}")
    
    def _register_error_handlers(self):
        """Register Flask error handlers."""
        if not self.app:
            return
        
        @self.app.errorhandler(Exception)
        def handle_exception(e):
            """Catch-all error handler."""
            # Don't log HTTP exceptions (404, 403, etc.) - these are intentional responses
            from werkzeug.exceptions import HTTPException
            if isinstance(e, HTTPException):
                # IMPORTANT: return the exception so Flask converts it to a response.
                # Re-raising causes tests (and some deployments) to treat 404/429/400 as crashes.
                return e

            self.log_error(e)

            # In debug/testing, keep the default developer experience (stack traces).
            try:
                if bool(getattr(self.app, 'debug', False)) or bool(getattr(self.app, 'testing', False)):
                    raise e
            except Exception:
                # If anything goes wrong determining env, fall back to a safe 500.
                pass

            from werkzeug.exceptions import InternalServerError
            return InternalServerError()
    
    def log_error(self, error, context=None):
        """
        Log an error with context.
        
        Args:
            error: Exception object or error message
            context: Additional context dict (optional)
        """
        try:
            error_data = {
                'error_type': type(error).__name__ if isinstance(error, Exception) else 'Error',
                'error_message': str(error),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'user_id': current_user.id if hasattr(current_user, 'id') and current_user.is_authenticated else None,
                'path': request.path if request else None,
                'method': request.method if request else None,
            }
            
            if context:
                error_data['context'] = context
            
            self.logger.error(json.dumps(error_data), exc_info=isinstance(error, Exception))
            
            # Send alert for critical errors (database, service failures, etc.)
            if self._is_critical_error(error):
                try:
                    from app.services.alert_service import alert_critical_error
                    alert_critical_error(error, error_data)
                except Exception as alert_error:
                    # Don't let alert failures break error logging
                    print(f"[WARNING] Failed to send error alert: {alert_error}")
                    
        except Exception as e:
            print(f"[ERROR] Failed to log error: {str(e)}")
    
    def _is_critical_error(self, error):
        """Determine if error is critical enough for immediate alert"""
        critical_errors = [
            'OperationalError',      # Database errors
            'ConnectionError',       # Network/service connectivity
            'TimeoutError',          # Service timeouts
            'MemoryError',          # Out of memory
            'SystemError',          # System-level errors
        ]
        return type(error).__name__ in critical_errors


class ApplicationLogger:
    """Main application logger that orchestrates all logging components."""
    
    def __init__(self):
        self.security_logger = SecurityEventLogger()
        self.access_logger = AccessLogger()
        self.error_logger = ErrorLogger()
        self.tracer = None
    
    def init_app(self, app):
        """Initialize all loggers with Flask app."""
        self.app = app
        
        # Initialize all component loggers
        self.security_logger.init_app(app)
        self.error_logger.init_app(app)
        
        # Only init access logger if enabled
        if app.config.get('LOG_ACCESS_EVENTS', False):
            self.access_logger.init_app(app)
        
        # Initialize tracing (if Azure enabled)
        if app.config.get('APPINSIGHTS_ENABLED') and AZURE_LOGGING_AVAILABLE:
            try:
                connection_string = app.config.get('APPINSIGHTS_CONNECTION_STRING')
                if connection_string:
                    # Set up tracing provider
                    resource = Resource.create({"service.name": "cenaris-app"})
                    trace_provider = TracerProvider(resource=resource)
                    trace_exporter = AzureMonitorTraceExporter(connection_string=connection_string)
                    trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
                    trace.set_tracer_provider(trace_provider)
                    self.tracer = trace.get_tracer(__name__)
                    
                    print("[INFO] Application Insights integration enabled")
            except Exception as e:
                print(f"[WARNING] Could not initialize Azure tracing: {str(e)}")
        
        print("[INFO] Application logging system initialized")
    
    def log_security_event(self, event_type, **kwargs):
        """Convenience method to log security events."""
        return self.security_logger.log_event(event_type, **kwargs)
    
    def log_error(self, error, context=None):
        """Convenience method to log errors."""
        return self.error_logger.log_error(error, context)


# Global app logger instance
app_logger = ApplicationLogger()


def log_security_event(event_type, user_id=None, org_id=None, details=None, ip_address=None):
    """
    Convenience function to log security events.
    
    Args:
        event_type: Type of event (LOGIN_SUCCESS, LOGOUT, etc.)
        user_id: User ID (optional, will auto-detect from current_user)
        org_id: Organization ID (optional)
        details: Additional details dict (optional)
        ip_address: IP address (optional, will auto-detect from request)
    """
    app_logger.security_logger.log_event(
        event_type=event_type,
        user_id=user_id,
        org_id=org_id,
        details=details,
        ip_address=ip_address
    )
