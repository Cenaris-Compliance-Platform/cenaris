"""document management features

Revision ID: n3o4p5q6r7s8
Revises: m2n3o4p5q6r7
Create Date: 2026-03-03

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'n3o4p5q6r7s8'
down_revision = 'm2n3o4p5q6r7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('documents', sa.Column('search_text', sa.Text(), nullable=True))
    op.create_index('ix_documents_org_active_search_text', 'documents', ['organization_id', 'is_active'])

    op.create_table(
        'document_tags',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('normalized_name', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'normalized_name', name='uq_document_tags_org_normalized_name'),
    )
    op.create_index('ix_document_tags_org_name', 'document_tags', ['organization_id', 'name'])

    op.create_table(
        'document_tag_map',
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.Column('linked_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['document_tags.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('document_id', 'tag_id'),
    )
    op.create_index('ix_document_tag_map_tag_id', 'document_tag_map', ['tag_id'])

    bind = op.get_bind()
    if bind and bind.dialect.name == 'postgresql':
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_documents_search_text_tsv "
            "ON documents USING GIN (to_tsvector('simple', coalesce(search_text, '')))"
        )


def downgrade():
    bind = op.get_bind()
    if bind and bind.dialect.name == 'postgresql':
        op.execute('DROP INDEX IF EXISTS ix_documents_search_text_tsv')

    op.drop_index('ix_document_tag_map_tag_id', table_name='document_tag_map')
    op.drop_table('document_tag_map')

    op.drop_index('ix_document_tags_org_name', table_name='document_tags')
    op.drop_table('document_tags')

    op.drop_index('ix_documents_org_active_search_text', table_name='documents')
    op.drop_column('documents', 'search_text')
