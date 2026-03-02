"""add admin notifications

Revision ID: l1m2n3o4p5q6
Revises: k0l1m2n3o4p5
Create Date: 2026-03-02

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'l1m2n3o4p5q6'
down_revision = 'k0l1m2n3o4p5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'admin_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('read_by_user_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=60), nullable=False),
        sa.Column('title', sa.String(length=160), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False, server_default='info'),
        sa.Column('link_url', sa.String(length=255), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('email_sent_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['read_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(
        'ix_admin_notifications_org_created_at',
        'admin_notifications',
        ['organization_id', 'created_at'],
        unique=False,
    )
    op.create_index(
        'ix_admin_notifications_org_read_created_at',
        'admin_notifications',
        ['organization_id', 'is_read', 'created_at'],
        unique=False,
    )
    op.create_index(
        'ix_admin_notifications_event_type',
        'admin_notifications',
        ['event_type'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_admin_notifications_event_type', table_name='admin_notifications')
    op.drop_index('ix_admin_notifications_org_read_created_at', table_name='admin_notifications')
    op.drop_index('ix_admin_notifications_org_created_at', table_name='admin_notifications')
    op.drop_table('admin_notifications')
