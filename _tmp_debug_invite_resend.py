import os
import tempfile
from datetime import datetime, timezone, timedelta


def main() -> None:
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite")
    os.close(db_fd)

    try:
        os.environ["FLASK_CONFIG"] = "testing"
        os.environ["TEST_DATABASE_URL"] = "sqlite:///" + db_path.replace("\\", "/")

        from app import create_app, db
        from app.models import Organization, OrganizationMembership, User

        app = create_app("testing")
        app.config.update(
            SQLALCHEMY_DATABASE_URI=os.environ["TEST_DATABASE_URL"],
            TESTING=True,
            WTF_CSRF_ENABLED=False,
            WTF_CSRF_CHECK_DEFAULT=False,
        )

        with app.app_context():
            db.drop_all()
            db.create_all()

            org = Organization(name="Org A")
            org.abn = "12345678901"
            org.organization_type = "Company"
            org.contact_email = "contact@example.com"
            org.address = "1 Test St"
            org.industry = "Other"
            org.operates_in_australia = True
            org.declarations_accepted_at = datetime.now(timezone.utc)
            org.data_processing_ack_at = datetime.now(timezone.utc)
            db.session.add(org)
            db.session.flush()

            admin = User(email="user@example.com", email_verified=True, is_active=True)
            admin.set_password("Passw0rd1")
            admin.organization_id = int(org.id)
            db.session.add(admin)
            db.session.flush()

            admin_m = OrganizationMembership(
                organization_id=int(org.id),
                user_id=int(admin.id),
                role="Admin",
                is_active=True,
            )
            db.session.add(admin_m)

            from app.services.rbac import ensure_rbac_seeded_for_org, BUILTIN_ROLE_KEYS
            from app.models import RBACRole

            ensure_rbac_seeded_for_org(int(org.id))
            db.session.flush()

            admin_role = (
                RBACRole.query.filter_by(
                    organization_id=int(org.id),
                    name=BUILTIN_ROLE_KEYS.ORG_ADMIN,
                ).first()
            )
            admin_m.role_id = int(admin_role.id) if admin_role else None

            member_role = (
                RBACRole.query.filter_by(
                    organization_id=int(org.id),
                    name=BUILTIN_ROLE_KEYS.MEMBER,
                ).first()
            )
            member_role_id = str(int(member_role.id)) if member_role else ""

            db.session.commit()

        client = app.test_client()

        r = client.post(
            "/auth/login",
            data={"email": "user@example.com", "password": "Passw0rd1", "remember_me": "y"},
            follow_redirects=False,
            environ_base={"REMOTE_ADDR": "10.0.0.11"},
        )
        print("login", r.status_code, r.headers.get("Location"))

        r = client.post(
            "/org/admin/invite",
            data={
                "email": "invited@example.com",
                "role": member_role_id,
                "new_department_name": "General",
                "new_department_color": "primary",
            },
            follow_redirects=False,
            environ_base={"REMOTE_ADDR": "10.0.0.11"},
        )
        print("invite", r.status_code, r.headers.get("Location"))

        with app.app_context():
            invited = User.query.filter_by(email="invited@example.com").first()
            assert invited is not None
            mem = OrganizationMembership.query.filter_by(user_id=int(invited.id)).first()
            assert mem is not None
            mid = int(mem.id)
            print("after invite", "send_count=", mem.invite_send_count, "invited_at=", mem.invited_at, "revoked=", mem.invite_revoked_at, "accepted=", mem.invite_accepted_at, "is_active=", mem.is_active)

            mem.invite_last_sent_at = datetime.now(timezone.utc) - timedelta(minutes=10)
            db.session.commit()

        r = client.post(
            "/org/admin/invite/resend",
            data={"membership_id": str(mid)},
            follow_redirects=False,
            environ_base={"REMOTE_ADDR": "10.0.0.11"},
        )
        print("resend", r.status_code, r.headers.get("Location"))

        with app.app_context():
            mem2 = db.session.get(OrganizationMembership, mid)
            invited2 = db.session.get(User, int(mem2.user_id)) if mem2 else None
            print(
                "after resend",
                "send_count=",
                getattr(mem2, "invite_send_count", None),
                "pending=",
                _is_pending(mem2, invited2),
                "last_sent=",
                getattr(mem2, "invite_last_sent_at", None),
            )

    finally:
        try:
            os.remove(db_path)
        except OSError:
            pass


def _is_pending(mem, user) -> bool:
    if not mem or not user:
        return False
    return (
        mem.invited_at is not None
        and mem.invite_accepted_at is None
        and mem.invite_revoked_at is None
        and not bool(getattr(user, "password_hash", None))
    )


if __name__ == "__main__":
    main()
