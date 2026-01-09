"""Send test emails using the app's configured Flask-Mail settings.

Usage examples (Windows PowerShell):
  python scripts/email_smoke_test.py --to you@company.com --type all --user-email you@company.com --base-url https://your-app.com

Notes:
- For verify/reset emails, --user-email must exist in the database so tokens can be generated.
- This script does not modify the database.
"""

from __future__ import annotations

import argparse
import os
import sys


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Send Cenaris email smoke tests")
    p.add_argument("--to", required=True, help="Recipient email address")
    p.add_argument(
        "--type",
        default="all",
        choices=["all", "verify", "reset", "invite", "welcome", "generic"],
        help="Which email to send",
    )
    p.add_argument(
        "--user-email",
        default=None,
        help="Existing user email in DB (required for verify/reset token generation)",
    )
    p.add_argument(
        "--base-url",
        default=None,
        help="Public base URL (e.g. https://app.example.com). Default: APP_BASE_URL env or http://localhost:5000",
    )
    p.add_argument(
        "--config",
        default=None,
        help="Flask config name (default: FLASK_CONFIG env or 'default')",
    )
    return p.parse_args()


def _base_url(args: argparse.Namespace) -> str:
    base = (args.base_url or os.environ.get("APP_BASE_URL") or "http://localhost:5000").strip()
    return base.rstrip("/")


def main() -> int:
    args = _parse_args()

    # Import app lazily so argparse help is fast.
    from app import create_app, db
    from app.models import User, Organization

    config_name = (args.config or os.environ.get("FLASK_CONFIG") or "default").strip() or "default"
    app = create_app(config_name)

    with app.app_context():
        # Reuse the actual helper functions so this tests real production code paths.
        from app.auth.routes import _email_verify_token, _send_email_verification_email, _password_reset_token, _send_password_reset_email
        from app.main.routes import _send_invite_email
        from app.onboarding.routes import _send_welcome_email
        from flask_mail import Message
        from app import mail

        base = _base_url(args)

        def require_user() -> User:
            email = (args.user_email or "").strip().lower()
            if not email:
                raise SystemExit("--user-email is required for this email type")
            u = User.query.filter_by(email=email).first()
            if not u:
                raise SystemExit(f"No user found in DB with email: {email}")
            return u

        def send_generic() -> None:
            msg = Message(
                subject="Cenaris test email",
                recipients=[args.to],
                body=f"This is a test email from Cenaris. Base URL: {base}",
            )
            mail.send(msg)

        def send_verify() -> None:
            u = require_user()
            token = _email_verify_token(u)
            verify_url = f"{base}/auth/verify-email/{token}"
            _send_email_verification_email(u, verify_url)

        def send_reset() -> None:
            u = require_user()
            token = _password_reset_token(u)
            reset_url = f"{base}/auth/reset-password/{token}"
            _send_password_reset_email(u, reset_url)

        def send_invite() -> None:
            u = require_user()
            org = None
            try:
                if getattr(u, "organization_id", None):
                    org = db.session.get(Organization, int(u.organization_id))
            except Exception:
                org = None

            if not org:
                org = Organization(name="Example Organization")

            token = _password_reset_token(u)
            reset_url = f"{base}/auth/reset-password/{token}"
            _send_invite_email(u, reset_url, org)

        def send_welcome() -> None:
            u = require_user()
            dashboard_url = f"{base}/dashboard"
            _send_welcome_email(u, dashboard_url)

        chosen = args.type
        try:
            if chosen in {"all", "generic"}:
                send_generic()
                print("OK: generic")
            if chosen in {"all", "verify"}:
                send_verify()
                print("OK: verify")
            if chosen in {"all", "reset"}:
                send_reset()
                print("OK: reset")
            if chosen in {"all", "invite"}:
                send_invite()
                print("OK: invite")
            if chosen in {"all", "welcome"}:
                send_welcome()
                print("OK: welcome")
        except Exception as e:
            print(f"FAILED: {type(e).__name__}: {e}")
            return 2

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
