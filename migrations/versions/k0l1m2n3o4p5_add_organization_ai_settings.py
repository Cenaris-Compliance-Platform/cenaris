"""add organization ai settings

Revision ID: k0l1m2n3o4p5
Revises: j9k0l1m2n3o4
Create Date: 2026-02-28

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'k0l1m2n3o4p5'
down_revision = 'j9k0l1m2n3o4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'organization_ai_settings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('policy_draft_use_llm', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('max_query_chars', sa.Integer(), nullable=False, server_default='1200'),
        sa.Column('max_top_k', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('max_citation_text_chars', sa.Integer(), nullable=False, server_default='600'),
        sa.Column('max_answer_chars', sa.Integer(), nullable=False, server_default='2000'),
        sa.Column('max_policy_draft_chars', sa.Integer(), nullable=False, server_default='6000'),
        sa.Column('rag_rate_limit', sa.String(length=40), nullable=False, server_default='20 per minute'),
        sa.Column('policy_rate_limit', sa.String(length=40), nullable=False, server_default='10 per minute'),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('updated_by_user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['updated_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id'),
    )
    op.create_index('ix_org_ai_settings_org_id', 'organization_ai_settings', ['organization_id'], unique=False)


def downgrade():
    op.drop_index('ix_org_ai_settings_org_id', table_name='organization_ai_settings')
    op.drop_table('organization_ai_settings')
