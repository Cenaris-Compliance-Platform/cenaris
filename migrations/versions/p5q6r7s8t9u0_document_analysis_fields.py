"""add document analysis fields

Revision ID: p5q6r7s8t9u0
Revises: o4p5q6r7s8t9
Create Date: 2026-03-15

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'p5q6r7s8t9u0'
down_revision = 'o4p5q6r7s8t9'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('documents', sa.Column('extracted_text', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('ai_status', sa.String(length=50), nullable=True))
    op.add_column('documents', sa.Column('ai_confidence', sa.Float(), nullable=True))
    op.add_column('documents', sa.Column('ai_focus_area', sa.String(length=80), nullable=True))
    op.add_column('documents', sa.Column('ai_question', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('ai_summary', sa.Text(), nullable=True))
    op.add_column('documents', sa.Column('ai_provider', sa.String(length=50), nullable=True))
    op.add_column('documents', sa.Column('ai_model', sa.String(length=120), nullable=True))
    op.add_column('documents', sa.Column('ai_retrieval_mode', sa.String(length=20), nullable=True))
    op.add_column('documents', sa.Column('ai_analysis_at', sa.DateTime(), nullable=True))
    op.create_index('ix_documents_org_ai_analysis_at', 'documents', ['organization_id', 'ai_analysis_at'], unique=False)


def downgrade():
    op.drop_index('ix_documents_org_ai_analysis_at', table_name='documents')
    op.drop_column('documents', 'ai_analysis_at')
    op.drop_column('documents', 'ai_retrieval_mode')
    op.drop_column('documents', 'ai_model')
    op.drop_column('documents', 'ai_provider')
    op.drop_column('documents', 'ai_summary')
    op.drop_column('documents', 'ai_question')
    op.drop_column('documents', 'ai_focus_area')
    op.drop_column('documents', 'ai_confidence')
    op.drop_column('documents', 'ai_status')
    op.drop_column('documents', 'extracted_text')