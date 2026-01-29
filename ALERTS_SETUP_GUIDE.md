# 🔔 Free Code-Based Alert System

## Overview

Your Cenaris application now has a **completely free** alert system that sends email notifications for critical events. No Azure costs - it uses your existing email infrastructure!

## ✅ Features

- ✨ **Zero Cost** - Uses existing Flask-Mail (SMTP)
- 🚨 **5 Alert Types** - Critical errors, security breaches, high error rates, service failures, resource exhaustion
- ⏱️ **Smart Throttling** - Prevents email spam (rate limiting)
- 📧 **HTML Emails** - Beautiful, professional alert emails
- 🔒 **Thread-Safe** - Works in production with multiple workers
- 🎯 **Auto-Integration** - Automatically triggers on critical errors

## 🎯 Alert Types

### 1. Critical Errors (Auto-Triggered)
**When:** Database failures, connection errors, memory errors
**Throttle:** Max 1 per 5 minutes
**Example:**
```python
# Automatically sent when critical exceptions occur
# No code needed - integrated into error logger!
```

### 2. Security Breaches
**When:** Account lockouts, failed login attempts, suspicious activity
**Throttle:** Max 1 per 15 minutes
**Example:**
```python
from app.services.alert_service import alert_security_breach

alert_security_breach('ACCOUNT_LOCKED', {
    'user_id': user.id,
    'email': user.email,
    'ip_address': request.remote_addr,
    'failed_attempts': 5
})
```

### 3. High Error Rate
**When:** Multiple errors occur in a short time period
**Throttle:** Max 1 per 15 minutes
**Example:**
```python
from app.services.alert_service import alert_high_error_rate

alert_high_error_rate(error_count=25, time_period="5 minutes")
```

### 4. Service Down
**When:** Critical services become unavailable
**Throttle:** Max 1 per 5 minutes
**Example:**
```python
from app.services.alert_service import alert_service_down

alert_service_down('Database', 'Connection timeout after 3 retries')
alert_service_down('Azure Storage', 'Authentication failed')
```

### 5. Resource Exhaustion
**When:** System resources reach critical levels
**Throttle:** Max 1 per 5-15 minutes
**Example:**
```python
from app.services.alert_service import alert_resource_exhaustion

alert_resource_exhaustion('Disk', current_value=95.5, threshold=90.0)
alert_resource_exhaustion('Memory', current_value=87.2, threshold=85.0)
```

## 🚀 Setup Instructions

### Step 1: Enable Alerts in .env

```bash
# Add to your .env file
ALERTS_ENABLED=true
ALERT_EMAILS=admin@yourdomain.com,ops@yourdomain.com
```

**Multiple emails:** Separate with commas (no spaces!)

### Step 2: Verify Email Configuration

Make sure these are already set in your `.env`:
```bash
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your.email@gmail.com
MAIL_PASSWORD=your_app_password
MAIL_DEFAULT_SENDER=your.email@gmail.com
```

### Step 3: Test the System

```bash
# Activate your virtual environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate  # Windows

# Run test script
python test_alerts.py
```

You should receive a test email within 1-2 minutes!

### Step 4: Restart Your Application

```bash
python run.py
```

Alerts are now active! 🎉

## 📧 Example Alert Email

```
Subject: [Cenaris Alert] Critical Error: OperationalError

CRITICAL ERROR DETECTED
======================

Error Type: OperationalError
Message: (psycopg2.OperationalError) FATAL: too many connections
Time: 2026-01-29 15:30:45 UTC

Context:
  user_id: 42
  path: /api/upload
  method: POST

Action Required:
- Check application logs immediately
- Investigate error cause
- Monitor system health

[View Logs in Azure Button]
```

## 🎨 Integration Examples

### Example 1: Monitor Database Connection Pool

```python
from app import db
from app.services.alert_service import alert_resource_exhaustion

def check_db_pool():
    """Monitor database connection usage"""
    pool = db.engine.pool
    active = pool.size() - pool.checkedin()
    max_size = pool.size() + pool.overflow()
    
    usage_percent = (active / max_size) * 100
    
    if usage_percent > 80:
        alert_resource_exhaustion(
            'Database Connections',
            current_value=usage_percent,
            threshold=80.0
        )
```

### Example 2: Monitor Error Rate

```python
from collections import deque
from datetime import datetime, timedelta
from app.services.alert_service import alert_high_error_rate

# Track recent errors
recent_errors = deque(maxlen=100)

def track_error(error):
    """Track errors and alert if rate is high"""
    recent_errors.append(datetime.now())
    
    # Count errors in last 5 minutes
    five_min_ago = datetime.now() - timedelta(minutes=5)
    recent_count = sum(1 for t in recent_errors if t > five_min_ago)
    
    if recent_count > 10:
        alert_high_error_rate(recent_count, "5 minutes")
```

### Example 3: Storage Service Health Check

```python
from app.services.alert_service import alert_service_down

def check_storage_health():
    """Verify Azure Storage is accessible"""
    try:
        # Try to access storage
        container_client.exists()
    except Exception as e:
        alert_service_down(
            'Azure Storage',
            f'Health check failed: {str(e)}'
        )
```

### Example 4: Security Monitoring

```python
from flask import request
from app.services.alert_service import alert_security_breach

@app.before_request
def check_suspicious_activity():
    """Monitor for suspicious patterns"""
    ip = request.remote_addr
    
    if is_ip_blacklisted(ip):
        alert_security_breach('SUSPICIOUS_IP', {
            'ip_address': ip,
            'path': request.path,
            'user_agent': request.user_agent.string
        })
```

## 🛡️ Best Practices

### 1. Don't Over-Alert
✅ **Good:** Alert on critical issues requiring immediate action
❌ **Bad:** Alert on every warning or info-level event

### 2. Use Appropriate Severity
```python
# Critical - Immediate action required
alert_critical_error(error, context)  # Database down, service crash

# High - Action needed soon
alert_security_breach(event, details)  # Security incidents
alert_high_error_rate(count, period)   # Error spikes

# Medium - Monitor
# Use logging instead of alerts
```

### 3. Respect Throttling
The system automatically prevents spam, but be mindful:
```python
# ❌ Don't do this in a loop
for item in items:
    alert_service_down('Service', 'Down')  # Sends 1, throttles rest

# ✅ Do this instead
if not service_is_up():
    alert_service_down('Service', 'Health check failed')
```

### 4. Provide Context
```python
# ❌ Minimal information
alert_critical_error(error)

# ✅ Rich context
alert_critical_error(error, {
    'user_id': current_user.id,
    'org_id': current_user.organization_id,
    'action': 'document_upload',
    'file_size': file_size,
    'database_pool_size': db.engine.pool.size()
})
```

## 🔧 Configuration Options

### Throttle Time Customization

Edit `app/services/alert_service.py`:
```python
self.throttle_minutes = {
    self.CRITICAL: 5,    # Critical: Max 1 per 5 minutes
    self.HIGH: 15,       # High: Max 1 per 15 minutes
    self.MEDIUM: 30,     # Medium: Max 1 per 30 minutes
    self.LOW: 60,        # Low: Max 1 per 60 minutes
}
```

### Email Template Customization

Alerts support both plain text and HTML:
```python
# Customize HTML in alert_service.py
html_body = f"""
<html>
<body style="your-custom-styles">
    <h1>Your Custom Alert</h1>
    {your_content}
</body>
</html>
"""
```

## 💰 Cost Comparison

| Feature | Azure Alerts | Code-Based Alerts |
|---------|--------------|-------------------|
| **Setup Cost** | $0 | $0 |
| **Per Alert Rule** | $0.10/month | $0 |
| **Per Email** | $0.02 | $0 (uses your SMTP) |
| **100 alerts/month** | ~$12/month | $0 |
| **SMS/Phone** | Extra cost | Not supported |
| **Custom Logic** | Limited | Unlimited |

**Savings:** ~$144/year for typical usage!

## 📊 Monitoring Alert Activity

Check alert logs:
```bash
# Search for alert activity
grep "\[ALERTS\]" logs/app.log

# In Azure Log Analytics
traces
| where message contains "ALERTS"
| order by timestamp desc
```

## 🐛 Troubleshooting

### Alerts Not Sending

**Check 1: Is it enabled?**
```python
from app.services.alert_service import alert_service
print(f"Enabled: {alert_service.enabled}")
print(f"Recipients: {alert_service.alert_emails}")
```

**Check 2: Email configuration**
```bash
# Verify SMTP settings in .env
MAIL_SERVER=smtp.gmail.com  # Must be valid SMTP server
MAIL_USERNAME=...           # Must be set
MAIL_PASSWORD=...           # Must be set (use app password for Gmail)
```

**Check 3: Test manually**
```python
python test_alerts.py
```

**Check 4: Check logs**
```bash
# Look for error messages
grep "ALERTS" logs/app.log
grep "ERROR.*Failed to send" logs/app.log
```

### Throttling Issues

If you're not receiving alerts you expect:
```python
# Check last alert times
from app.services.alert_service import alert_service
print(alert_service._last_alert_time)
```

Alerts may be throttled if sent too frequently. This is intentional to prevent spam.

### Gmail Issues

If using Gmail, you need an **App Password**:
1. Enable 2-factor authentication on your Google account
2. Generate an app password: https://myaccount.google.com/apppasswords
3. Use the app password (not your regular password) in `.env`

## 🔄 Upgrading to Azure Alerts Later

When you're ready for enterprise-grade monitoring:

**Keep code-based alerts for:**
- Application-specific errors
- Business logic failures
- Custom conditions

**Add Azure alerts for:**
- Infrastructure metrics (CPU, memory, disk)
- System-wide patterns
- Long-term trend analysis
- SMS/phone notifications

Both can run side-by-side!

## 📚 Additional Resources

- [Flask-Mail Documentation](https://pythonhosted.org/Flask-Mail/)
- [SMTP Configuration Guide](../DEPLOYMENT_RUNBOOK.md)
- [Azure Application Insights](https://portal.azure.com)

## ✅ Next Steps

1. ✅ Enable alerts in `.env`
2. ✅ Run `python test_alerts.py`
3. ✅ Verify test email received
4. ✅ Monitor your application
5. ✅ Customize alert logic as needed

---

**🎉 Your free alert system is ready!**

**Questions?** Check application logs or Azure Application Insights for more details.
