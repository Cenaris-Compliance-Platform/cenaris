"""Quick smoke check for app.main.routes._mail_configured().

Run: python scripts/_smoke_check_mail_config.py
"""
import os
from app import create_app

# Ensure no ACS envs
os.environ.pop('ACS_CONNECTION_STRING', None)
os.environ.pop('ACS_SENDER_EMAIL', None)
os.environ.pop('MICROSOFT_CLIENT_ID', None)
os.environ.pop('MICROSOFT_CLIENT_SECRET', None)

app = create_app('default')
with app.app_context():
    from app.main.routes import _mail_configured
    print('no-acs:', _mail_configured())

# Set ACS envs and re-check
os.environ['ACS_CONNECTION_STRING'] = 'Endpoint=sb://fake;AccessKey=fake'
os.environ['ACS_SENDER_EMAIL'] = 'sender@example.com'
app2 = create_app('default')
with app2.app_context():
    from app.main.routes import _mail_configured
    print('with-acs:', _mail_configured())

# Set SMTP-like config in app config and check
app3 = create_app('default')
with app3.app_context():
    current = app3.config
    current['MAIL_SERVER'] = 'smtp.example.com'
    current['MAIL_DEFAULT_SENDER'] = 'noreply@example.com'
    from app.main.routes import _mail_configured
    print('with-smtp-config:', _mail_configured())
