"""add performance indexes

Revision ID: f3c9a1b2c3d4
Revises: f1a2b3c4d5e6
Create Date: 2026-01-17

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'f3c9a1b2c3d4'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    # Documents: common filters and ordering
    op.create_index(
        'ix_documents_org_active_uploaded_at',
        'documents',
        ['organization_id', 'is_active', 'uploaded_at'],
        unique=False,
    )

    # OrganizationMembership: common lookups
    op.create_index(
        'ix_org_memberships_org_active',
        'organization_memberships',
        ['organization_id', 'is_active'],
        unique=False,
    )
    op.create_index(
        'ix_org_memberships_user_active',
        'organization_memberships',
        ['user_id', 'is_active'],
        unique=False,
    )
    op.create_index(
        'ix_org_memberships_user_org_active',
        'organization_memberships',
        ['user_id', 'organization_id', 'is_active'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_org_memberships_user_org_active', table_name='organization_memberships')
    op.drop_index('ix_org_memberships_user_active', table_name='organization_memberships')
    op.drop_index('ix_org_memberships_org_active', table_name='organization_memberships')
    op.drop_index('ix_documents_org_active_uploaded_at', table_name='documents')
