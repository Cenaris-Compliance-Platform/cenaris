"""org required details and terms

Revision ID: f2d1a0b8c8a1
Revises: b1a6fbbd4a2d
Create Date: 2025-12-22 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2d1a0b8c8a1'
down_revision = 'b1a6fbbd4a2d'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('trading_name', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('organization_type', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('industry', sa.String(length=60), nullable=True))
        batch_op.add_column(sa.Column('billing_email', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('billing_address', sa.String(length=255), nullable=True))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('terms_accepted_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('terms_accepted_at')

    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_column('billing_address')
        batch_op.drop_column('billing_email')
        batch_op.drop_column('industry')
        batch_op.drop_column('organization_type')
        batch_op.drop_column('trading_name')
