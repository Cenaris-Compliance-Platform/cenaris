"""departments for memberships

Revision ID: d1c2e3f4a5b6
Revises: e80ea29bf39b
Create Date: 2025-12-27 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1c2e3f4a5b6'
down_revision = 'e80ea29bf39b'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'departments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('organization_id', sa.Integer(), sa.ForeignKey('organizations.id'), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('color', sa.String(length=20), nullable=False, server_default='primary'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.UniqueConstraint('organization_id', 'name', name='uq_departments_org_name'),
    )
    op.create_index('ix_departments_org_id', 'departments', ['organization_id'])

    with op.batch_alter_table('organization_memberships', schema=None) as batch_op:
        batch_op.add_column(sa.Column('department_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_org_memberships_department_id', 'departments', ['department_id'], ['id'])

    # Drop server default after creation.
    with op.batch_alter_table('departments', schema=None) as batch_op:
        batch_op.alter_column('color', server_default=None)


def downgrade():
    with op.batch_alter_table('organization_memberships', schema=None) as batch_op:
        batch_op.drop_constraint('fk_org_memberships_department_id', type_='foreignkey')
        batch_op.drop_column('department_id')

    op.drop_index('ix_departments_org_id', table_name='departments')
    op.drop_table('departments')
