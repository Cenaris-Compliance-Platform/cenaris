"""
Free Code-Based Alert Service
Sends email notifications for critical events without Azure Monitor costs
Uses existing Flask-Mail infrastructure - $0 cost
"""

import logging
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional
from flask import Flask
from flask_mail import Mail, Message

logger = logging.getLogger(__name__)


class AlertService:
    """
    Free alert system that monitors logs and sends email notifications.
    Features:
    - Email alerts for critical errors
    - Security breach notifications  
    - Rate limiting (prevents spam)
    - Daily digest option
    - Zero cost (uses existing SMTP)
    """
    
    # Alert severity levels
    CRITICAL = 'critical'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'
    
    def __init__(self):
        self.app = None
        self.mail = None
        self.enabled = False
        
        # Rate limiting: track when each alert type was last sent
        self._last_alert_time: Dict[str, datetime] = {}
        self._alert_counts: Dict[str, int] = defaultdict(int)
        
        # Throttling settings (prevent spam)
        self.throttle_minutes = {
            self.CRITICAL: 5,    # Max 1 critical alert per 5 minutes
            self.HIGH: 15,       # Max 1 high alert per 15 minutes
            self.MEDIUM: 30,     # Max 1 medium alert per 30 minutes
            self.LOW: 60,        # Max 1 low alert per 60 minutes
        }
        
        # Alert recipients
        self.alert_emails: List[str] = []
        
        # Thread lock for thread-safe operations
        self._lock = threading.Lock()
    
    def init_app(self, app: Flask, mail: Mail):
        """Initialize alert service with Flask app and Mail instance"""
        self.app = app
        self.mail = mail
        
        # Get alert configuration
        self.enabled = app.config.get('ALERTS_ENABLED', False)
        alert_emails = app.config.get('ALERT_EMAILS', '')
        
        if alert_emails:
            self.alert_emails = [email.strip() for email in alert_emails.split(',') if email.strip()]
        
        if self.enabled and not self.alert_emails:
            logger.warning('[ALERTS] Alerts enabled but no email recipients configured')
            self.enabled = False
        
        if self.enabled:
            logger.info(f'[ALERTS] Alert service initialized - Recipients: {len(self.alert_emails)}')
        else:
            logger.info('[ALERTS] Alert service disabled (set ALERTS_ENABLED=true to enable)')
    
    def _should_send_alert(self, alert_type: str, severity: str) -> bool:
        """Check if alert should be sent based on throttling rules"""
        if not self.enabled:
            return False
        
        with self._lock:
            key = f"{severity}:{alert_type}"
            now = datetime.now()
            
            # Check if we've sent this alert recently
            if key in self._last_alert_time:
                last_time = self._last_alert_time[key]
                throttle_period = timedelta(minutes=self.throttle_minutes.get(severity, 30))
                
                if now - last_time < throttle_period:
                    # Still in throttle period
                    self._alert_counts[key] += 1
                    return False
            
            # Update last alert time
            self._last_alert_time[key] = now
            return True
    
    def _send_email_alert(self, subject: str, body: str, html_body: Optional[str] = None):
        """Send alert email to all recipients"""
        if not self.enabled or not self.alert_emails:
            return
        
        try:
            msg = Message(
                subject=f"[Cenaris Alert] {subject}",
                recipients=self.alert_emails,
                body=body,
                html=html_body
            )
            
            # Send in background thread to avoid blocking
            def send_async():
                try:
                    with self.app.app_context():
                        self.mail.send(msg)
                    logger.info(f'[ALERTS] Email sent: {subject}')
                except Exception as e:
                    logger.error(f'[ALERTS] Failed to send email: {e}')
            
            thread = threading.Thread(target=send_async)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            logger.error(f'[ALERTS] Error preparing email: {e}')
    
    def alert_critical_error(self, error: Exception, context: Optional[Dict] = None):
        """
        Send alert for critical application error
        Example: Database connection lost, critical service down
        """
        alert_type = 'critical_error'
        
        if not self._should_send_alert(alert_type, self.CRITICAL):
            return
        
        error_name = type(error).__name__
        error_msg = str(error)
        
        # Build email body
        body = f"""
CRITICAL ERROR DETECTED
======================

Error Type: {error_name}
Message: {error_msg}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

"""
        
        if context:
            body += "\nContext:\n"
            for key, value in context.items():
                body += f"  {key}: {value}\n"
        
        body += f"""

Action Required:
- Check application logs immediately
- Investigate error cause
- Monitor system health

View logs: https://portal.azure.com (Application Insights → Logs)
"""
        
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif; line-height: 1.6;">
    <div style="background-color: #dc3545; color: white; padding: 15px; border-radius: 5px;">
        <h2 style="margin: 0;">🚨 CRITICAL ERROR DETECTED</h2>
    </div>
    
    <div style="padding: 20px; background-color: #f8f9fa; margin-top: 20px; border-radius: 5px;">
        <p><strong>Error Type:</strong> {error_name}</p>
        <p><strong>Message:</strong> {error_msg}</p>
        <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    </div>
    
    <div style="margin-top: 20px; padding: 15px; background-color: #fff3cd; border-left: 4px solid #ffc107;">
        <h3>⚡ Action Required</h3>
        <ul>
            <li>Check application logs immediately</li>
            <li>Investigate error cause</li>
            <li>Monitor system health</li>
        </ul>
    </div>
    
    <p style="margin-top: 20px;">
        <a href="https://portal.azure.com" style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
            View Logs in Azure
        </a>
    </p>
</body>
</html>
"""
        
        subject = f"Critical Error: {error_name}"
        self._send_email_alert(subject, body, html_body)
    
    def alert_security_breach(self, event_type: str, details: Dict):
        """
        Send alert for security-related events
        Example: Multiple failed logins, account lockout, suspicious activity
        """
        alert_type = f'security_{event_type}'
        severity = self.HIGH if event_type in ['ACCOUNT_LOCKED', 'PERMISSION_DENIED'] else self.MEDIUM
        
        if not self._should_send_alert(alert_type, severity):
            return
        
        body = f"""
SECURITY ALERT
==============

Event: {event_type}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

Details:
"""
        
        for key, value in details.items():
            body += f"  {key}: {value}\n"
        
        body += """

Recommended Actions:
- Review user activity logs
- Check for unusual patterns
- Verify user identity if needed

View security logs: https://portal.azure.com
"""
        
        subject = f"Security Alert: {event_type}"
        self._send_email_alert(subject, body)
    
    def alert_high_error_rate(self, error_count: int, time_period: str):
        """
        Send alert when error rate exceeds threshold
        Example: More than 10 errors in 5 minutes
        """
        alert_type = 'high_error_rate'
        
        if not self._should_send_alert(alert_type, self.HIGH):
            return
        
        body = f"""
HIGH ERROR RATE DETECTED
========================

Error Count: {error_count} errors
Time Period: {time_period}
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

This indicates a potential system issue that needs investigation.

Actions:
- Check error logs for patterns
- Verify system resources (CPU, memory, disk)
- Check external service status
- Monitor for continued errors

View logs: https://portal.azure.com
"""
        
        subject = f"High Error Rate: {error_count} errors in {time_period}"
        self._send_email_alert(subject, body)
    
    def alert_service_down(self, service_name: str, details: Optional[str] = None):
        """
        Send alert when a critical service is down
        Example: Database unavailable, storage service down
        """
        alert_type = f'service_down_{service_name}'
        
        if not self._should_send_alert(alert_type, self.CRITICAL):
            return
        
        body = f"""
SERVICE DOWN ALERT
==================

Service: {service_name}
Status: UNAVAILABLE
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

"""
        
        if details:
            body += f"Details: {details}\n\n"
        
        body += """
IMMEDIATE ACTION REQUIRED:
- Verify service status
- Check network connectivity
- Review recent deployments
- Restart service if needed

This is a critical issue affecting application functionality.
"""
        
        html_body = f"""
<html>
<body style="font-family: Arial, sans-serif;">
    <div style="background-color: #dc3545; color: white; padding: 20px; border-radius: 5px;">
        <h2 style="margin: 0;">🔴 SERVICE DOWN</h2>
    </div>
    
    <div style="padding: 20px; margin-top: 20px;">
        <p><strong style="font-size: 18px;">Service:</strong> {service_name}</p>
        <p><strong>Status:</strong> <span style="color: #dc3545; font-weight: bold;">UNAVAILABLE</span></p>
        <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</p>
    </div>
    
    <div style="background-color: #dc3545; color: white; padding: 15px; margin-top: 20px; border-radius: 5px;">
        <h3 style="margin-top: 0;">⚡ IMMEDIATE ACTION REQUIRED</h3>
        <ul>
            <li>Verify service status</li>
            <li>Check network connectivity</li>
            <li>Review recent deployments</li>
            <li>Restart service if needed</li>
        </ul>
    </div>
</body>
</html>
"""
        
        subject = f"CRITICAL: {service_name} Service Down"
        self._send_email_alert(subject, body, html_body)
    
    def alert_resource_exhaustion(self, resource_type: str, current_value: float, threshold: float):
        """
        Send alert when system resources are running low
        Example: Disk 95% full, memory 90% used
        """
        alert_type = f'resource_{resource_type}'
        severity = self.CRITICAL if current_value > 95 else self.HIGH
        
        if not self._should_send_alert(alert_type, severity):
            return
        
        body = f"""
RESOURCE EXHAUSTION WARNING
===========================

Resource: {resource_type}
Current Usage: {current_value:.1f}%
Threshold: {threshold:.1f}%
Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

This resource is running critically low and may cause service disruption.

Actions:
- Free up {resource_type} space immediately
- Investigate what's consuming resources
- Consider scaling up if persistent
- Monitor trends

View metrics: https://portal.azure.com
"""
        
        subject = f"Resource Alert: {resource_type} at {current_value:.1f}%"
        self._send_email_alert(subject, body)
    
    def send_test_alert(self):
        """Send a test alert to verify email configuration"""
        body = f"""
TEST ALERT
==========

This is a test alert from the Cenaris Alert Service.

If you received this email, your alert system is configured correctly!

Configuration:
- Recipients: {', '.join(self.alert_emails)}
- Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}

Throttling Settings:
- Critical alerts: Max 1 per {self.throttle_minutes[self.CRITICAL]} minutes
- High alerts: Max 1 per {self.throttle_minutes[self.HIGH]} minutes
- Medium alerts: Max 1 per {self.throttle_minutes[self.MEDIUM]} minutes
- Low alerts: Max 1 per {self.throttle_minutes[self.LOW]} minutes

The alert service is ready to monitor your application!
"""
        
        subject = "Test Alert - System Working"
        self._send_email_alert(subject, body)
        logger.info('[ALERTS] Test alert sent')


# Global alert service instance
alert_service = AlertService()


# Convenience functions
def alert_critical_error(error: Exception, context: Optional[Dict] = None):
    """Send critical error alert"""
    alert_service.alert_critical_error(error, context)


def alert_security_breach(event_type: str, details: Dict):
    """Send security breach alert"""
    alert_service.alert_security_breach(event_type, details)


def alert_high_error_rate(error_count: int, time_period: str):
    """Send high error rate alert"""
    alert_service.alert_high_error_rate(error_count, time_period)


def alert_service_down(service_name: str, details: Optional[str] = None):
    """Send service down alert"""
    alert_service.alert_service_down(service_name, details)


def alert_resource_exhaustion(resource_type: str, current_value: float, threshold: float):
    """Send resource exhaustion alert"""
    alert_service.alert_resource_exhaustion(resource_type, current_value, threshold)
