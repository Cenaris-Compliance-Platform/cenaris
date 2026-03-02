"""add monthly report delivery settings

Revision ID: m2n3o4p5q6r7
Revises: l1m2n3o4p5q6
Create Date: 2026-03-02

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'm2n3o4p5q6r7'
down_revision = 'l1m2n3o4p5q6'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'organizations',
        sa.Column('monthly_report_enabled', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    )
    op.add_column(
        'organizations',
        sa.Column('monthly_report_recipient_email', sa.String(length=120), nullable=True),
    )


def downgrade():
    op.drop_column('organizations', 'monthly_report_recipient_email')
    op.drop_column('organizations', 'monthly_report_enabled')
