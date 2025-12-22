"""welcome email sent timestamp

Revision ID: b1a6fbbd4a2d
Revises: e947b7b2fb8c
Create Date: 2025-12-22 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b1a6fbbd4a2d'
down_revision = 'e947b7b2fb8c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('welcome_email_sent_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('welcome_email_sent_at')
