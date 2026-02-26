"""normalize compliance computed_flag values

Revision ID: i8j9k0l1m2n3
Revises: h7i8j9k0l1m2
Create Date: 2026-02-26

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i8j9k0l1m2n3'
down_revision = 'h7i8j9k0l1m2'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        sa.text(
            """
            UPDATE organization_requirement_assessments
            SET computed_flag = CASE
                WHEN lower(trim(computed_flag)) = 'red' THEN 'Critical gap'
                WHEN lower(trim(computed_flag)) = 'amber' THEN 'High risk gap'
                WHEN lower(trim(computed_flag)) = 'green' THEN 'OK'
                WHEN lower(trim(computed_flag)) = 'ok' THEN 'OK'
                WHEN lower(trim(computed_flag)) = 'mature' THEN 'Mature'
                ELSE computed_flag
            END
            WHERE computed_flag IS NOT NULL
            """
        )
    )


def downgrade():
    op.execute(
        sa.text(
            """
            UPDATE organization_requirement_assessments
            SET computed_flag = CASE
                WHEN computed_flag = 'Critical gap' THEN 'red'
                WHEN computed_flag = 'High risk gap' THEN 'amber'
                WHEN computed_flag = 'OK' THEN 'green'
                WHEN computed_flag = 'Mature' THEN 'mature'
                ELSE computed_flag
            END
            WHERE computed_flag IS NOT NULL
            """
        )
    )
