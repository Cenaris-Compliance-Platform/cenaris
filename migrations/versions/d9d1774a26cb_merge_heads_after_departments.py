"""merge heads after departments

Revision ID: d9d1774a26cb
Revises: 77d1c5c875d4, d1c2e3f4a5b6
Create Date: 2025-12-27 16:14:46.103978

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd9d1774a26cb'
down_revision = ('77d1c5c875d4', 'd1c2e3f4a5b6')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
