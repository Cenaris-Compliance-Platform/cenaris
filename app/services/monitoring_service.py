"""
Enhanced System Monitoring Service
Tracks performance, system health, database queries, and errors
Sends all telemetry to Azure Application Insights
"""

import os
import time
import psutil
import logging
from datetime import datetime, timezone
from threading import Thread
from flask import Flask, request, g
from typing import Optional, Dict, Any

# OpenTelemetry imports
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

# Azure Monitor exporters
from azure.monitor.opentelemetry.exporter import (
    AzureMonitorTraceExporter,
    AzureMonitorMetricExporter,
)

logger = logging.getLogger(__name__)


class MonitoringService:
    """
    Comprehensive monitoring service for tracking:
    - HTTP request performance (response times, status codes)
    - System health (CPU, memory, disk usage)
    - Database performance (query times, connection pool)
    - Application errors and exceptions
    """

    def __init__(self):
        self.enabled = False
        self.connection_string = None
        self.tracer = None
        self.meter = None
        self.app = None
        
        # Metrics instruments
        self.http_request_duration = None
        self.http_requests_total = None
        self.cpu_usage_gauge = None
        self.memory_usage_gauge = None
        self.disk_usage_gauge = None
        self.db_query_duration = None
        self.db_connections_active = None
        self.active_users_gauge = None
        self.user_sessions_counter = None
        
        # System monitoring thread
        self.system_monitor_thread = None
        self.monitor_interval = 60  # Collect system metrics every 60 seconds
        
        # Active user tracking
        self.active_users = {}  # {user_id: last_activity_timestamp}
        self.active_user_timeout = 900  # 15 minutes timeout for active users

    def init_app(self, app: Flask):
        """Initialize monitoring service with Flask app"""
        print('[DEBUG] MonitoringService.init_app() called')
        self.app = app
        self.connection_string = app.config.get('APPINSIGHTS_CONNECTION_STRING')
        print(f'[DEBUG] Connection string found: {bool(self.connection_string)}')
        
        if not self.connection_string:
            logger.warning('[MONITORING] No Application Insights connection string configured')
            print('[DEBUG] No connection string, returning early')
            return
        
        try:
            print('[DEBUG] Starting monitoring setup...')
            # Create resource with service information
            resource = Resource.create({
                "service.name": "cenaris-compliance",
                "service.version": "1.0.0",
                "deployment.environment": os.getenv('FLASK_ENV', 'production'),
            })
            print('[DEBUG] Resource created')
            
            # Reuse existing tracer if already set up (by logging_service)
            try:
                self.tracer = trace.get_tracer(__name__)
                print('[DEBUG] Reusing existing tracer')
                logger.info('[MONITORING] Reusing existing tracer from logging service')
            except Exception as te:
                print(f'[DEBUG] Creating new tracer, error was: {te}')
                # Set up tracing only if not already configured
                trace_provider = TracerProvider(resource=resource)
                trace_exporter = AzureMonitorTraceExporter(connection_string=self.connection_string)
                
                from opentelemetry.sdk.trace.export import BatchSpanProcessor
                # Add custom span processor to enrich spans with user context
                trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
                trace.set_tracer_provider(trace_provider)
                self.tracer = trace.get_tracer(__name__)
                logger.info('[MONITORING] Created new tracer with custom processors')
            
            print('[DEBUG] About to set up metrics...')
            # Set up metrics (for performance counters)
            metric_provider = MeterProvider(resource=resource)
            metric_exporter = AzureMonitorMetricExporter(connection_string=self.connection_string)
            
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            metric_reader = PeriodicExportingMetricReader(metric_exporter, export_interval_millis=60000)
            metric_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
            metrics.set_meter_provider(metric_provider)
            self.meter = metrics.get_meter(__name__)
            print('[DEBUG] Metrics set up complete')
            
            # Create metric instruments
            self._create_metrics()
            print('[DEBUG] Metric instruments created')
            
            # Auto-instrument Flask, Requests, and SQLAlchemy
            self._instrument_libraries(app)
            print('[DEBUG] Libraries instrumented')
            
            # Register Flask hooks for custom tracking
            self._register_flask_hooks(app)
            print('[DEBUG] Flask hooks registered')
            
            # Start system monitoring thread
            self._start_system_monitoring()
            print('[DEBUG] System monitoring started')
            
            self.enabled = True
            logger.info('[MONITORING] Enhanced monitoring initialized successfully')
            logger.info('[MONITORING] Tracking: Performance, System Health, Database, Errors')
            
        except Exception as e:
            print(f'[DEBUG] ERROR in monitoring setup: {e}')
            import traceback
            traceback.print_exc()
            logger.error(f'[MONITORING] Failed to initialize: {e}')
            self.enabled = False

    def _create_metrics(self):
        """Create custom metric instruments"""
        if not self.meter:
            return
        
        # HTTP metrics
        self.http_request_duration = self.meter.create_histogram(
            name="http.server.request.duration",
            description="HTTP request duration in milliseconds",
            unit="ms"
        )
        
        self.http_requests_total = self.meter.create_counter(
            name="http.server.requests.total",
            description="Total number of HTTP requests",
            unit="1"
        )
        
        # System health metrics
        self.cpu_usage_gauge = self.meter.create_observable_gauge(
            name="system.cpu.usage",
            description="CPU usage percentage",
            unit="%",
            callbacks=[self._get_cpu_usage]
        )
        
        self.memory_usage_gauge = self.meter.create_observable_gauge(
            name="system.memory.usage",
            description="Memory usage percentage",
            unit="%",
            callbacks=[self._get_memory_usage]
        )
        
        self.disk_usage_gauge = self.meter.create_observable_gauge(
            name="system.disk.usage",
            description="Disk usage percentage",
            unit="%",
            callbacks=[self._get_disk_usage]
        )
        
        # Database metrics
        self.db_query_duration = self.meter.create_histogram(
            name="db.query.duration",
            description="Database query duration in milliseconds",
            unit="ms"
        )
        
        # User session metrics
        self.active_users_gauge = self.meter.create_observable_gauge(
            name="app.users.active",
            description="Number of currently active users",
            unit="1",
            callbacks=[self._get_active_users_count]
        )
        
        self.user_sessions_counter = self.meter.create_counter(
            name="app.user.sessions",
            description="User session events",
            unit="1"
        )

    def _instrument_libraries(self, app: Flask):
        """Auto-instrument Flask, Requests, and SQLAlchemy"""
        try:
            # Instrument Flask for automatic request tracking
            FlaskInstrumentor().instrument_app(app)
            logger.info('[MONITORING] Flask auto-instrumentation enabled')
            
            # Instrument requests library for external API calls
            RequestsInstrumentor().instrument()
            logger.info('[MONITORING] Requests auto-instrumentation enabled')
            
            # Instrument SQLAlchemy for database query tracking (within app context)
            try:
                with app.app_context():
                    from app import db
                    SQLAlchemyInstrumentor().instrument(
                        engine=db.engine,
                        enable_commenter=True,  # Add trace context to SQL comments
                    )
                    logger.info('[MONITORING] SQLAlchemy auto-instrumentation enabled')
            except Exception as e:
                logger.warning(f'[MONITORING] SQLAlchemy instrumentation failed: {e}')
            
        except Exception as e:
            logger.warning(f'[MONITORING] Auto-instrumentation partial failure: {e}')

    def _register_flask_hooks(self, app: Flask):
        """Register Flask before/after request hooks for custom tracking"""
        
        @app.before_request
        def before_request():
            """Track request start time and user activity"""
            g.request_start_time = time.time()
            
            # Track authenticated user activity and set user context for Application Insights
            try:
                from flask_login import current_user
                from opentelemetry import trace
                
                if current_user and current_user.is_authenticated:
                    user_id = str(current_user.id)
                    self._track_user_activity(current_user.id)
                    
                    # Store user_id in Flask g for use in after_request
                    g.user_id = user_id
                    
                    # Set user context on current span using multiple attribute names
                    # to ensure Azure Application Insights picks it up
                    current_span = trace.get_current_span()
                    if current_span and current_span.is_recording():
                        # Standard OpenTelemetry semantic convention
                        current_span.set_attribute("enduser.id", user_id)
                        # Azure-specific attributes
                        current_span.set_attribute("ai.user.id", user_id)
                        current_span.set_attribute("ai.user.authUserId", user_id)
                        # Store in custom dimensions
                        current_span.set_attribute("user_id", user_id)
                        logger.debug(f'[MONITORING] Set user context on span for user {user_id}')
            except Exception as e:
                logger.warning(f'[MONITORING] Error setting user context: {e}')
        
        @app.after_request
        def after_request(response):
            """Track request completion and metrics"""
            if not self.enabled:
                return response
            
            # Ensure user context is on the span even if not set in before_request
            try:
                from flask_login import current_user
                from opentelemetry import trace
                
                if hasattr(g, 'user_id'):
                    user_id = g.user_id
                    current_span = trace.get_current_span()
                    if current_span and current_span.is_recording():
                        # Re-set user attributes to ensure they're captured
                        current_span.set_attribute("ai.user.authUserId", user_id)
                        current_span.set_attribute("user_id", user_id)
            except Exception as e:
                logger.debug(f'[MONITORING] Error in after_request user context: {e}')
            
            try:
                # Calculate request duration
                if hasattr(g, 'request_start_time'):
                    duration_ms = (time.time() - g.request_start_time) * 1000
                    
                    # Record metrics
                    if self.http_request_duration:
                        self.http_request_duration.record(
                            duration_ms,
                            attributes={
                                "http.method": request.method,
                                "http.route": request.endpoint or "unknown",
                                "http.status_code": response.status_code,
                            }
                        )
                    
                    if self.http_requests_total:
                        self.http_requests_total.add(
                            1,
                            attributes={
                                "http.method": request.method,
                                "http.status_code": response.status_code,
                            }
                        )
                
            except Exception as e:
                logger.warning(f'[MONITORING] Error tracking request: {e}')
            
            return response
        
        @app.errorhandler(Exception)
        def handle_exception(error):
            """Track application errors"""
            if self.enabled and self.tracer:
                try:
                    with self.tracer.start_as_current_span("error_handler") as span:
                        span.set_attribute("error.type", type(error).__name__)
                        span.set_attribute("error.message", str(error))
                        span.record_exception(error)
                except Exception:
                    pass
            
            # Re-raise the exception for Flask's default error handling
            raise error

    def _start_system_monitoring(self):
        """Start background thread for system health monitoring"""
        def monitor_system_health():
            """Collect system metrics periodically"""
            while self.enabled:
                try:
                    time.sleep(self.monitor_interval)
                    # Metrics are collected via observable callbacks
                except Exception as e:
                    logger.error(f'[MONITORING] System health monitoring error: {e}')
        
        self.system_monitor_thread = Thread(target=monitor_system_health, daemon=True)
        self.system_monitor_thread.start()
        logger.info('[MONITORING] System health monitoring thread started')

    def _get_cpu_usage(self, options) -> Any:
        """Get current CPU usage percentage"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            yield metrics.Observation(cpu_percent)
        except Exception as e:
            logger.warning(f'[MONITORING] Error getting CPU usage: {e}')

    def _get_memory_usage(self, options) -> Any:
        """Get current memory usage percentage"""
        try:
            memory = psutil.virtual_memory()
            yield metrics.Observation(memory.percent)
        except Exception as e:
            logger.warning(f'[MONITORING] Error getting memory usage: {e}')

    def _get_disk_usage(self, options) -> Any:
        """Get current disk usage percentage"""
        try:
            disk = psutil.disk_usage('/')
            yield metrics.Observation(disk.percent)
        except Exception as e:
            logger.warning(f'[MONITORING] Error getting disk usage: {e}')

    def track_custom_event(self, name: str, properties: Optional[Dict[str, Any]] = None):
        """Track a custom application event"""
        if not self.enabled or not self.tracer:
            return
        
        try:
            with self.tracer.start_as_current_span(name) as span:
                if properties:
                    for key, value in properties.items():
                        span.set_attribute(key, str(value))
        except Exception as e:
            logger.warning(f'[MONITORING] Error tracking custom event: {e}')

    def track_database_query(self, query_name: str, duration_ms: float, success: bool = True):
        """Track database query performance"""
        if not self.enabled or not self.db_query_duration:
            return
        
        try:
            self.db_query_duration.record(
                duration_ms,
                attributes={
                    "db.query.name": query_name,
                    "db.query.success": success,
                }
            )
        except Exception as e:
            logger.warning(f'[MONITORING] Error tracking database query: {e}')
    
    def _track_user_activity(self, user_id: int):
        """Track user activity for active user counting"""
        try:
            self.active_users[user_id] = time.time()
            # Clean up inactive users periodically
            current_time = time.time()
            inactive_users = [uid for uid, last_active in self.active_users.items() 
                            if current_time - last_active > self.active_user_timeout]
            for uid in inactive_users:
                self.active_users.pop(uid, None)
        except Exception as e:
            logger.warning(f'[MONITORING] Error tracking user activity: {e}')
    
    def _get_active_users_count(self, options) -> Any:
        """Get current count of active users"""
        try:
            # Clean up inactive users
            current_time = time.time()
            self.active_users = {uid: last_active for uid, last_active in self.active_users.items() 
                                if current_time - last_active <= self.active_user_timeout}
            yield metrics.Observation(len(self.active_users))
        except Exception as e:
            logger.warning(f'[MONITORING] Error getting active users count: {e}')
    
    def track_user_session(self, user_id: int, event_type: str, properties: Optional[Dict[str, Any]] = None):
        """Track user session events (login, logout, etc.) with geographic data"""
        if not self.enabled or not self.tracer:
            return
        
        try:
            from flask import request
            from opentelemetry import trace
            
            # Set user ID on current span for the request
            current_span = trace.get_current_span()
            if current_span:
                current_span.set_attribute("enduser.id", str(user_id))
                current_span.set_attribute("user_AuthenticatedId", str(user_id))
            
            # Start a span for the user session event
            with self.tracer.start_as_current_span(f"user_session_{event_type}") as span:
                span.set_attribute("user.id", str(user_id))
                span.set_attribute("enduser.id", str(user_id))
                span.set_attribute("user_AuthenticatedId", str(user_id))
                span.set_attribute("session.event", event_type)
                
                # Add geographic data (App Insights will auto-capture from IP)
                # These are just for span attributes; geography is auto-captured in customDimensions
                try:
                    user_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
                    if user_ip:
                        span.set_attribute("client.ip", user_ip.split(',')[0].strip())
                except Exception:
                    pass
                
                # Add custom properties
                if properties:
                    for key, value in properties.items():
                        span.set_attribute(key, str(value))
            
            # Increment session counter
            if self.user_sessions_counter:
                self.user_sessions_counter.add(
                    1,
                    attributes={
                        "session.event": event_type,
                    }
                )
                
        except Exception as e:
            logger.warning(f'[MONITORING] Error tracking user session: {e}')


# Global instance
monitoring_service = MonitoringService()
