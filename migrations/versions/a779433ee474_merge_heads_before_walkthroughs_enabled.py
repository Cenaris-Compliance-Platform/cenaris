"""Merge heads before walkthroughs_enabled

Revision ID: a779433ee474
Revises: 0bc20bd2029d, s1a2b3c4d5e6
Create Date: 2026-05-15 12:49:18.327948

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a779433ee474'
down_revision = ('0bc20bd2029d', 's1a2b3c4d5e6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
