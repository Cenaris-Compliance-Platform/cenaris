"""add policy reminders audit expiry

Revision ID: r4s5t6u7v8w9
Revises: q6r7s8t9u0v1
Create Date: 2026-05-13
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'r4s5t6u7v8w9'
down_revision = 'q6r7s8t9u0v1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('requirement_evidence_links', sa.Column('expires_at', sa.DateTime(), nullable=True))
    op.add_column('requirement_evidence_links', sa.Column('expires_at_set_by_user_id', sa.Integer(), nullable=True))
    op.add_column('requirement_evidence_links', sa.Column('expires_at_set_at', sa.DateTime(), nullable=True))
    op.add_column('requirement_evidence_links', sa.Column('expiry_note', sa.String(length=255), nullable=True))
    op.create_index('ix_requirement_evidence_links_expires_at', 'requirement_evidence_links', ['expires_at'], unique=False)
    op.create_foreign_key(
        'fk_requirement_evidence_links_expires_at_set_by_user_id',
        'requirement_evidence_links',
        'users',
        ['expires_at_set_by_user_id'],
        ['id'],
    )

    op.create_table(
        'requirement_reminders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('requirement_id', sa.Integer(), nullable=False),
        sa.Column('frequency_days', sa.Integer(), nullable=False, server_default='30'),
        sa.Column('next_send_at', sa.DateTime(), nullable=True),
        sa.Column('last_sent_at', sa.DateTime(), nullable=True),
        sa.Column('recipient_user_id', sa.Integer(), nullable=True),
        sa.Column('recipient_email', sa.String(length=160), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['recipient_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['requirement_id'], ['compliance_requirements.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'requirement_id', name='uq_requirement_reminders_org_requirement'),
    )
    op.create_index('ix_requirement_reminders_org', 'requirement_reminders', ['organization_id'], unique=False)
    op.create_index('ix_requirement_reminders_next_send', 'requirement_reminders', ['next_send_at'], unique=False)
    op.create_index('ix_requirement_reminders_active', 'requirement_reminders', ['organization_id', 'is_active'], unique=False)

    op.create_table(
        'policy_drafts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('policy_type', sa.String(length=160), nullable=True),
        sa.Column('source_mode', sa.String(length=20), nullable=True),
        sa.Column('scope_mode', sa.String(length=20), nullable=True),
        sa.Column('requirement_code', sa.String(length=120), nullable=True),
        sa.Column('document_id', sa.Integer(), nullable=True),
        sa.Column('last_version_number', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_policy_drafts_org', 'policy_drafts', ['organization_id'], unique=False)
    op.create_index('ix_policy_drafts_created', 'policy_drafts', ['created_at'], unique=False)

    op.create_table(
        'policy_draft_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('policy_draft_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('created_by_user_id', sa.Integer(), nullable=True),
        sa.Column('draft_text', sa.Text(), nullable=False),
        sa.Column('draft_mode', sa.String(length=40), nullable=True),
        sa.Column('output_mode', sa.String(length=40), nullable=True),
        sa.Column('policy_tone', sa.String(length=120), nullable=True),
        sa.Column('policy_audience', sa.String(length=120), nullable=True),
        sa.Column('policy_strictness', sa.String(length=120), nullable=True),
        sa.Column('org_profile', sa.String(length=120), nullable=True),
        sa.Column('context_goal', sa.String(length=500), nullable=True),
        sa.Column('context_brief', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['created_by_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['policy_draft_id'], ['policy_drafts.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('policy_draft_id', 'version_number', name='uq_policy_draft_version_number'),
    )
    op.create_index('ix_policy_draft_versions_draft', 'policy_draft_versions', ['policy_draft_id'], unique=False)
    op.create_index('ix_policy_draft_versions_created', 'policy_draft_versions', ['created_at'], unique=False)

    op.create_table(
        'audit_events',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('actor_user_id', sa.Integer(), nullable=True),
        sa.Column('event_type', sa.String(length=80), nullable=False),
        sa.Column('entity_type', sa.String(length=80), nullable=True),
        sa.Column('entity_id', sa.String(length=120), nullable=True),
        sa.Column('message', sa.String(length=255), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_audit_events_org_created', 'audit_events', ['organization_id', 'created_at'], unique=False)
    op.create_index('ix_audit_events_type', 'audit_events', ['event_type'], unique=False)
    op.create_index('ix_audit_events_entity', 'audit_events', ['entity_type', 'entity_id'], unique=False)


def downgrade():
    op.drop_index('ix_audit_events_entity', table_name='audit_events')
    op.drop_index('ix_audit_events_type', table_name='audit_events')
    op.drop_index('ix_audit_events_org_created', table_name='audit_events')
    op.drop_table('audit_events')

    op.drop_index('ix_policy_draft_versions_created', table_name='policy_draft_versions')
    op.drop_index('ix_policy_draft_versions_draft', table_name='policy_draft_versions')
    op.drop_table('policy_draft_versions')

    op.drop_index('ix_policy_drafts_created', table_name='policy_drafts')
    op.drop_index('ix_policy_drafts_org', table_name='policy_drafts')
    op.drop_table('policy_drafts')

    op.drop_index('ix_requirement_reminders_active', table_name='requirement_reminders')
    op.drop_index('ix_requirement_reminders_next_send', table_name='requirement_reminders')
    op.drop_index('ix_requirement_reminders_org', table_name='requirement_reminders')
    op.drop_table('requirement_reminders')

    op.drop_constraint('fk_requirement_evidence_links_expires_at_set_by_user_id', 'requirement_evidence_links', type_='foreignkey')
    op.drop_index('ix_requirement_evidence_links_expires_at', table_name='requirement_evidence_links')
    op.drop_column('requirement_evidence_links', 'expiry_note')
    op.drop_column('requirement_evidence_links', 'expires_at_set_at')
    op.drop_column('requirement_evidence_links', 'expires_at_set_by_user_id')
    op.drop_column('requirement_evidence_links', 'expires_at')
