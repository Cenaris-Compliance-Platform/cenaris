"""add demo_analysis_results table

Revision ID: o4p5q6r7s8t9
Revises: 7b4a3f9c2d11
Create Date: 2026-03-15

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'o4p5q6r7s8t9'
down_revision = '7b4a3f9c2d11'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'demo_analysis_results',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=True),
        sa.Column('question', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('analysis_mode', sa.String(length=20), nullable=False, server_default='balanced'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('snippet_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('citation_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('provider', sa.String(length=50), nullable=True),
        sa.Column('model_used', sa.String(length=120), nullable=True),
        sa.Column('retrieval_mode', sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_demo_analysis_org_created', 'demo_analysis_results', ['organization_id', 'created_at'])
    op.create_index('ix_demo_analysis_user_created', 'demo_analysis_results', ['user_id', 'created_at'])


def downgrade():
    op.drop_index('ix_demo_analysis_user_created', table_name='demo_analysis_results')
    op.drop_index('ix_demo_analysis_org_created', table_name='demo_analysis_results')
    op.drop_table('demo_analysis_results')
