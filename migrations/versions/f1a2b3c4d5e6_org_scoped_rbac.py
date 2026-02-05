"""org-scoped RBAC

Revision ID: f1a2b3c4d5e6
Revises: d036b8f3059d
Create Date: 2026-01-06

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a2b3c4d5e6'
down_revision = 'd036b8f3059d'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'rbac_permissions',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=80), nullable=False, unique=True),
        sa.Column('description', sa.String(length=255), nullable=True),
    )

    op.create_table(
        'rbac_roles',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('is_system', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('organization_id', 'name', name='uq_rbac_roles_org_name'),
        sa.Index('ix_rbac_roles_org_id', 'organization_id'),
    )

    op.create_table(
        'rbac_role_permissions',
        sa.Column('role_id', sa.Integer(), sa.ForeignKey('rbac_roles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('permission_id', sa.Integer(), sa.ForeignKey('rbac_permissions.id', ondelete='CASCADE'), primary_key=True),
    )

    op.create_table(
        'rbac_role_inherits',
        sa.Column('role_id', sa.Integer(), sa.ForeignKey('rbac_roles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('inherited_role_id', sa.Integer(), sa.ForeignKey('rbac_roles.id', ondelete='CASCADE'), primary_key=True),
    )

    op.add_column('organization_memberships', sa.Column('role_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_org_memberships_role_id',
        'organization_memberships',
        'rbac_roles',
        ['role_id'],
        ['id'],
        ondelete='SET NULL',
    )

    conn = op.get_bind()

    permission_rows = [
        {'code': 'documents.view', 'description': 'View documents'},
        {'code': 'documents.upload', 'description': 'Upload documents'},
        {'code': 'documents.delete', 'description': 'Delete documents'},
        {'code': 'audits.export', 'description': 'Export audit data'},
        {'code': 'org.manage', 'description': 'Manage organization profile/settings'},
        {'code': 'departments.manage', 'description': 'Manage departments'},
        {'code': 'users.invite', 'description': 'Invite users to organization'},
        {'code': 'users.manage', 'description': 'Manage users and memberships'},
        {'code': 'roles.manage', 'description': 'Manage roles and permissions'},
    ]

    permissions = sa.table(
        'rbac_permissions',
        sa.column('id', sa.Integer()),
        sa.column('code', sa.String()),
        sa.column('description', sa.String()),
    )
    conn.execute(permissions.insert(), permission_rows)

    perm_id_by_code = {
        row.code: row.id
        for row in conn.execute(sa.text('SELECT id, code FROM rbac_permissions')).fetchall()
    }

    org_ids = [row.id for row in conn.execute(sa.text('SELECT id FROM organizations')).fetchall()]

    # Default system roles per org.
    # Note: membership.role remains legacy ('Admin'/'User') and is kept for backward compatibility.
    for org_id in org_ids:
        admin_role_id = conn.execute(
            sa.text(
                """
                INSERT INTO rbac_roles (organization_id, name, description, is_system)
                VALUES (:org_id, :name, :desc, true)
                RETURNING id
                """
            ),
            {'org_id': org_id, 'name': 'Organisation Admin', 'desc': 'Full administrative access for this organisation.'},
        ).scalar()

        manager_role_id = conn.execute(
            sa.text(
                """
                INSERT INTO rbac_roles (organization_id, name, description, is_system)
                VALUES (:org_id, :name, :desc, true)
                RETURNING id
                """
            ),
            {'org_id': org_id, 'name': 'Compliance Manager', 'desc': 'Manage compliance workflows and documents.'},
        ).scalar()

        auditor_role_id = conn.execute(
            sa.text(
                """
                INSERT INTO rbac_roles (organization_id, name, description, is_system)
                VALUES (:org_id, :name, :desc, true)
                RETURNING id
                """
            ),
            {'org_id': org_id, 'name': 'Auditor', 'desc': 'Read-only access for audits and evidence review.'},
        ).scalar()

        member_role_id = conn.execute(
            sa.text(
                """
                INSERT INTO rbac_roles (organization_id, name, description, is_system)
                VALUES (:org_id, :name, :desc, true)
                RETURNING id
                """
            ),
            {'org_id': org_id, 'name': 'Member', 'desc': 'Standard member access.'},
        ).scalar()

        # Inheritance (simple): Admin -> Manager -> Member; Auditor -> Member
        conn.execute(
            sa.text('INSERT INTO rbac_role_inherits (role_id, inherited_role_id) VALUES (:r, :i)'),
            [
                {'r': admin_role_id, 'i': manager_role_id},
                {'r': manager_role_id, 'i': member_role_id},
                {'r': auditor_role_id, 'i': member_role_id},
            ],
        )

        # Permissions
        def grant(role_id: int, codes: list[str]):
            conn.execute(
                sa.text('INSERT INTO rbac_role_permissions (role_id, permission_id) VALUES (:r, :p)'),
                [{'r': role_id, 'p': perm_id_by_code[c]} for c in codes],
            )

        grant(member_role_id, ['documents.view', 'documents.upload'])
        grant(auditor_role_id, ['documents.view', 'audits.export'])
        grant(manager_role_id, ['documents.view', 'documents.upload', 'documents.delete', 'audits.export'])
        grant(admin_role_id, ['org.manage', 'departments.manage', 'users.invite', 'users.manage', 'roles.manage'])

        # Backfill memberships: Admins -> Organisation Admin; everyone else -> Member
        conn.execute(
            sa.text(
                """
                UPDATE organization_memberships
                SET role_id = :admin_role_id
                WHERE organization_id = :org_id
                  AND is_active IS TRUE
                  AND lower(coalesce(role, '')) IN ('admin', 'organisation administrator', 'organization administrator')
                """
            ),
            {'admin_role_id': admin_role_id, 'org_id': org_id},
        )
        conn.execute(
            sa.text(
                """
                UPDATE organization_memberships
                SET role_id = :member_role_id
                WHERE organization_id = :org_id
                  AND is_active IS TRUE
                  AND role_id IS NULL
                """
            ),
            {'member_role_id': member_role_id, 'org_id': org_id},
        )


def downgrade():
    op.drop_constraint('fk_org_memberships_role_id', 'organization_memberships', type_='foreignkey')
    op.drop_column('organization_memberships', 'role_id')
    op.drop_table('rbac_role_inherits')
    op.drop_table('rbac_role_permissions')
    op.drop_table('rbac_roles')
    op.drop_table('rbac_permissions')
