def test_invite_creates_department_and_assigns_membership(client, app, db_session, seed_org_user):
    from app.models import Department, OrganizationMembership, User

    org_id, user_id, _membership_id = seed_org_user

    # Login as org admin
    resp = client.post(
        "/auth/login",
        data={"email": "user@example.com", "password": "Passw0rd1", "remember_me": "y"},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code in {302, 303}

    invite_email = "invitee@example.com"

    with app.app_context():
        from app.services.rbac import ensure_rbac_seeded_for_org, BUILTIN_ROLE_KEYS
        from app.models import RBACRole

        ensure_rbac_seeded_for_org(int(org_id))
        db_session.session.commit()
        member_role = (
            RBACRole.query
            .filter_by(organization_id=int(org_id), name=BUILTIN_ROLE_KEYS.MEMBER)
            .first()
        )
        member_role_id = str(int(member_role.id)) if member_role else ''

    resp = client.post(
        "/org/admin/invite",
        data={
            "email": invite_email,
            "role": member_role_id,
            "department_id": "",
            "new_department_name": "Finance",
            "new_department_color": "success",
        },
        follow_redirects=False,
    )
    assert resp.status_code in {302, 303}

    with app.app_context():
        dept = Department.query.filter_by(organization_id=int(org_id), name="Finance").first()
        assert dept is not None
        assert dept.color == "success"

        invited_user = User.query.filter_by(email=invite_email).first()
        assert invited_user is not None

        membership = (
            OrganizationMembership.query
            .filter_by(organization_id=int(org_id), user_id=int(invited_user.id))
            .first()
        )
        assert membership is not None
        assert membership.department_id == dept.id
        assert membership.department is not None
        assert membership.department.name == "Finance"


def test_invite_selects_existing_department(client, app, db_session, seed_org_user):
    from app.models import Department, OrganizationMembership, User

    org_id, user_id, _membership_id = seed_org_user

    with app.app_context():
        dept = Department(organization_id=int(org_id), name="IT", color="primary")
        db_session.session.add(dept)
        db_session.session.commit()
        dept_id = int(dept.id)

    # Login as org admin
    resp = client.post(
        "/auth/login",
        data={"email": "user@example.com", "password": "Passw0rd1", "remember_me": "y"},
        follow_redirects=False,
        environ_base={"REMOTE_ADDR": "127.0.0.1"},
    )
    assert resp.status_code in {302, 303}

    invite_email = "invitee2@example.com"

    with app.app_context():
        from app.services.rbac import ensure_rbac_seeded_for_org, BUILTIN_ROLE_KEYS
        from app.models import RBACRole

        ensure_rbac_seeded_for_org(int(org_id))
        db_session.session.commit()
        admin_role = (
            RBACRole.query
            .filter_by(organization_id=int(org_id), name=BUILTIN_ROLE_KEYS.ORG_ADMIN)
            .first()
        )
        admin_role_id = str(int(admin_role.id)) if admin_role else ''

    resp = client.post(
        "/org/admin/invite",
        data={
            "email": invite_email,
            "role": admin_role_id,
            "department_id": str(dept_id),
            "new_department_name": "",
            "new_department_color": "primary",
        },
        follow_redirects=False,
    )
    assert resp.status_code in {302, 303}

    with app.app_context():
        invited_user = User.query.filter_by(email=invite_email).first()
        assert invited_user is not None

        membership = (
            OrganizationMembership.query
            .filter_by(organization_id=int(org_id), user_id=int(invited_user.id))
            .first()
        )
        assert membership is not None
        assert membership.department_id == dept_id
        assert membership.department is not None
        assert membership.department.name == "IT"
