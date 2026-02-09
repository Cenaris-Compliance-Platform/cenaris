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
try:
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor  # type: ignore
except Exception:  # pragma: no cover
    SQLAlchemyInstrumentor = None  # type: ignore

# Azure Monitor exporters (optional; do not fail app startup/tests if unavailable)
try:  # pragma: no cover
    from azure.monitor.opentelemetry.exporter import (
        AzureMonitorTraceExporter,  # type: ignore
        AzureMonitorMetricExporter,  # type: ignore
    )
except Exception:  # pragma: no cover
    AzureMonitorTraceExporter = None  # type: ignore
    AzureMonitorMetricExporter = None  # type: ignore

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
        self.is_development = os.getenv('FLASK_ENV') == 'development' or os.getenv('FLASK_DEBUG') == '1'
        
        # Metrics instruments
        self.http_request_duration = None
        self.http_requests_total = None
        self.cpu_usage_counter = None
        self.memory_usage_counter = None
        self.disk_usage_counter = None
        self.db_query_duration = None
        self.db_connections_active = None
        
        # System monitoring thread
        self.system_monitor_thread = None
        # Development: collect less frequently to save costs (5 minutes)
        # Production: collect every 60 seconds for better monitoring
        self.monitor_interval = 300 if self.is_development else 60
        
        # Cache for system metrics (reduce psutil calls)
        self._last_cpu = 0.0
        self._last_memory = 0.0
        self._last_disk = 0.0

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

        if AzureMonitorTraceExporter is None or AzureMonitorMetricExporter is None:
            logger.warning('[MONITORING] Azure Monitor exporter not available; monitoring disabled')
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
                trace_provider.add_span_processor(BatchSpanProcessor(trace_exporter))
                trace.set_tracer_provider(trace_provider)
                self.tracer = trace.get_tracer(__name__)
                logger.info('[MONITORING] Created new tracer')
            
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
        
        # System health metrics - Using UpDownCounter instead of observable gauges
        # This is more cost-effective as we control when metrics are sent
        self.cpu_usage_counter = self.meter.create_up_down_counter(
            name="system.cpu.usage",
            description="CPU usage percentage",
            unit="%"
        )
        
        self.memory_usage_counter = self.meter.create_up_down_counter(
            name="system.memory.usage",
            description="Memory usage percentage",
            unit="%"
        )
        
        self.disk_usage_counter = self.meter.create_up_down_counter(
            name="system.disk.usage",
            description="Disk usage percentage",
            unit="%"
        )
        
        # Database metrics
        self.db_query_duration = self.meter.create_histogram(
            name="db.query.duration",
            description="Database query duration in milliseconds",
            unit="ms"
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
            
            # Instrument SQLAlchemy for database query tracking (within app context).
            # Optional dependency: do not fail app startup/tests if missing.
            if SQLAlchemyInstrumentor is None:
                logger.info('[MONITORING] SQLAlchemy auto-instrumentation not available (missing dependency)')
            else:
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
            """Track request start time"""
            g.request_start_time = time.time()
        
        @app.after_request
        def after_request(response):
            """Track request completion and metrics"""
            if not self.enabled:
                return response
            
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

            # IMPORTANT:
            # Do not re-raise HTTP exceptions (404/429/400/etc). Flask can convert them
            # into proper responses, and tests expect `client.get/post` to return a Response.
            try:
                from werkzeug.exceptions import HTTPException

                if isinstance(error, HTTPException):
                    return error
            except Exception:
                pass

            # For non-HTTP exceptions, allow Flask to render its default 500 page.
            # Returning the error here lets Flask handle it consistently.
            raise error

    def _start_system_monitoring(self):
        """Start background thread for system health monitoring"""
        def monitor_system_health():
            """Collect system metrics periodically"""
            while self.enabled:
                try:
                    time.sleep(self.monitor_interval)
                    self._collect_system_metrics()
                except Exception as e:
                    logger.error(f'[MONITORING] System health monitoring error: {e}')
        
        self.system_monitor_thread = Thread(target=monitor_system_health, daemon=True)
        self.system_monitor_thread.start()
        interval_desc = f"{self.monitor_interval}s (dev mode)" if self.is_development else f"{self.monitor_interval}s"
        logger.info(f'[MONITORING] System health monitoring started (interval: {interval_desc})')

    def _collect_system_metrics(self):
        """Manually collect and record system metrics (cost-optimized)"""
        try:
            # Get CPU usage (non-blocking)
            cpu_percent = psutil.cpu_percent(interval=0.1)
            if self.cpu_usage_counter:
                # Calculate delta from last reading
                delta = cpu_percent - self._last_cpu
                if delta != 0:  # Only send if changed
                    self.cpu_usage_counter.add(delta)
                    self._last_cpu = cpu_percent
        except Exception as e:
            logger.debug(f'[MONITORING] Error getting CPU usage: {e}')
        
        try:
            # Get memory usage
            memory = psutil.virtual_memory()
            if self.memory_usage_counter:
                delta = memory.percent - self._last_memory
                if abs(delta) > 0.5:  # Only send if changed by >0.5%
                    self.memory_usage_counter.add(delta)
                    self._last_memory = memory.percent
        except Exception as e:
            logger.debug(f'[MONITORING] Error getting memory usage: {e}')
        
        try:
            # Get disk usage (Windows/Linux compatible)
            disk_path = 'C:\\' if os.name == 'nt' else '/'
            disk = psutil.disk_usage(disk_path)
            if self.disk_usage_counter:
                delta = disk.percent - self._last_disk
                if abs(delta) > 1.0:  # Only send if changed by >1%
                    self.disk_usage_counter.add(delta)
                    self._last_disk = disk.percent
        except Exception as e:
            logger.debug(f'[MONITORING] Error getting disk usage: {e}')

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


# Global instance
monitoring_service = MonitoringService()
