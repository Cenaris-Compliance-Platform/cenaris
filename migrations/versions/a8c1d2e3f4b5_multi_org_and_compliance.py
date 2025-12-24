"""multi org memberships and compliance

Revision ID: a8c1d2e3f4b5
Revises: f2d1a0b8c8a1
Create Date: 2025-12-24 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a8c1d2e3f4b5'
down_revision = 'f2d1a0b8c8a1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'organization_memberships',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='User'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('organization_id', 'user_id', name='uq_org_membership_org_user'),
    )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('first_name', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('last_name', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('title', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('mobile_number', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('time_zone', sa.String(length=60), nullable=True))

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('operates_in_australia', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('declarations_accepted_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('declarations_accepted_by_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('data_processing_ack_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('data_processing_ack_by_user_id', sa.Integer(), nullable=True))

    # Backfill memberships for existing users that have an organization_id.
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == 'sqlite':
        op.execute(sa.text(
            """
            INSERT OR IGNORE INTO organization_memberships (organization_id, user_id, role, is_active, created_at)
            SELECT organization_id, id,
                   CASE WHEN lower(coalesce(role, '')) = 'admin' THEN 'Admin' ELSE 'User' END,
                   1,
                   CURRENT_TIMESTAMP
            FROM users
            WHERE organization_id IS NOT NULL
            """
        ))
    else:
        op.execute(sa.text(
            """
            INSERT INTO organization_memberships (organization_id, user_id, role, is_active, created_at)
            SELECT organization_id, id,
                   CASE WHEN lower(coalesce(role, '')) = 'admin' THEN 'Admin' ELSE 'User' END,
                   TRUE,
                   CURRENT_TIMESTAMP
            FROM users
            WHERE organization_id IS NOT NULL
            ON CONFLICT (organization_id, user_id) DO NOTHING
            """
        ))


def downgrade():
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_column('data_processing_ack_by_user_id')
        batch_op.drop_column('data_processing_ack_at')
        batch_op.drop_column('declarations_accepted_by_user_id')
        batch_op.drop_column('declarations_accepted_at')
        batch_op.drop_column('operates_in_australia')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('time_zone')
        batch_op.drop_column('mobile_number')
        batch_op.drop_column('title')
        batch_op.drop_column('last_name')
        batch_op.drop_column('first_name')

    op.drop_table('organization_memberships')
