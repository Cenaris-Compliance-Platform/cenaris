"""add contact fields

Revision ID: g1h2j3k4l5m6
Revises: f3c9a1b2c3d4
Create Date: 2025-01-27

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g1h2j3k4l5m6'
down_revision = 'f3c9a1b2c3d4'
branch_labels = None
depends_on = None


def upgrade():
    # User table: add secondary_email, work_phone (mobile_number already exists)
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('work_phone', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('secondary_email', sa.String(length=120), nullable=True))

    # Organization table: add acn, contact_number
    # Also add billing_details text field per client request (invoice notes / billing instructions)
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.add_column(sa.Column('acn', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('contact_number', sa.String(length=40), nullable=True))
        batch_op.add_column(sa.Column('billing_details', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('organizations', schema=None) as batch_op:
        batch_op.drop_column('billing_details')
        batch_op.drop_column('contact_number')
        batch_op.drop_column('acn')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('secondary_email')
        batch_op.drop_column('work_phone')
