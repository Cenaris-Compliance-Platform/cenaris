"""add compliance requirement models

Revision ID: h7i8j9k0l1m2
Revises: g1h2j3k4l5m6
Create Date: 2026-02-26

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h7i8j9k0l1m2'
down_revision = 'g1h2j3k4l5m6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'compliance_framework_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=True),
        sa.Column('jurisdiction', sa.String(length=20), nullable=False),
        sa.Column('scheme', sa.String(length=50), nullable=False),
        sa.Column('source_authority', sa.String(length=255), nullable=True),
        sa.Column('source_document', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(length=500), nullable=True),
        sa.Column('version_label', sa.String(length=50), nullable=False),
        sa.Column('imported_at', sa.DateTime(), nullable=False),
        sa.Column('imported_by_user_id', sa.Integer(), nullable=True),
        sa.Column('checksum', sa.String(length=64), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['imported_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'organization_id',
            'scheme',
            'version_label',
            name='uq_compliance_framework_org_scheme_version',
        ),
    )
    op.create_index(
        'ix_compliance_framework_versions_org_active',
        'compliance_framework_versions',
        ['organization_id', 'is_active'],
        unique=False,
    )

    op.create_table(
        'compliance_requirements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('framework_version_id', sa.Integer(), nullable=False),
        sa.Column('requirement_id', sa.String(length=120), nullable=False),
        sa.Column('module_type', sa.String(length=40), nullable=True),
        sa.Column('module_name', sa.String(length=255), nullable=True),
        sa.Column('standard_name', sa.String(length=255), nullable=True),
        sa.Column('outcome_code', sa.String(length=120), nullable=True),
        sa.Column('outcome_text', sa.Text(), nullable=True),
        sa.Column('quality_indicator_code', sa.String(length=120), nullable=True),
        sa.Column('quality_indicator_text', sa.Text(), nullable=True),
        sa.Column('applies_to_all_providers', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('registration_group_numbers', sa.String(length=255), nullable=True),
        sa.Column('registration_group_names', sa.Text(), nullable=True),
        sa.Column('registration_group_source_url', sa.String(length=500), nullable=True),
        sa.Column('audit_type', sa.String(length=50), nullable=True),
        sa.Column('high_risk_flag', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('stage_1_applies', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('stage_2_applies', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('audit_test_methods', sa.Text(), nullable=True),
        sa.Column('sampling_required', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('sampling_subject', sa.String(length=255), nullable=True),
        sa.Column('system_evidence_required', sa.Text(), nullable=True),
        sa.Column('implementation_evidence_required', sa.Text(), nullable=True),
        sa.Column('workforce_evidence_required', sa.Text(), nullable=True),
        sa.Column('participant_evidence_required', sa.Text(), nullable=True),
        sa.Column('requires_workforce_evidence', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('requires_participant_evidence', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('minimum_evidence_score_2', sa.Text(), nullable=True),
        sa.Column('best_practice_evidence_score_3', sa.Text(), nullable=True),
        sa.Column('common_nonconformity_patterns', sa.Text(), nullable=True),
        sa.Column('gap_rule_1', sa.Text(), nullable=True),
        sa.Column('gap_rule_2', sa.Text(), nullable=True),
        sa.Column('gap_rule_3', sa.Text(), nullable=True),
        sa.Column('nc_severity_default', sa.String(length=50), nullable=True),
        sa.Column('evidence_owner_role', sa.String(length=120), nullable=True),
        sa.Column('review_frequency', sa.String(length=120), nullable=True),
        sa.Column('system_of_record', sa.String(length=255), nullable=True),
        sa.Column('audit_export_label', sa.String(length=255), nullable=True),
        sa.Column('source_version', sa.String(length=50), nullable=True),
        sa.Column('source_last_reviewed_date', sa.Date(), nullable=True),
        sa.Column('change_trigger', sa.String(length=255), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['framework_version_id'], ['compliance_framework_versions.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('framework_version_id', 'requirement_id', name='uq_compliance_requirement_per_framework'),
    )
    op.create_index('ix_compliance_requirements_requirement_id', 'compliance_requirements', ['requirement_id'], unique=False)
    op.create_index(
        'ix_compliance_requirements_quality_indicator_code',
        'compliance_requirements',
        ['quality_indicator_code'],
        unique=False,
    )

    op.create_table(
        'organization_requirement_assessments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('requirement_id', sa.Integer(), nullable=False),
        sa.Column('evidence_status_system', sa.String(length=20), nullable=False, server_default='Not assessed'),
        sa.Column('evidence_status_implementation', sa.String(length=20), nullable=False, server_default='Not assessed'),
        sa.Column('evidence_status_workforce', sa.String(length=20), nullable=False, server_default='Not assessed'),
        sa.Column('evidence_status_participant', sa.String(length=20), nullable=False, server_default='Not assessed'),
        sa.Column('best_practice_evidence_present', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('computed_score', sa.Integer(), nullable=True),
        sa.Column('computed_flag', sa.String(length=30), nullable=True),
        sa.Column('last_assessed_at', sa.DateTime(), nullable=True),
        sa.Column('last_assessed_by_user_id', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['requirement_id'], ['compliance_requirements.id']),
        sa.ForeignKeyConstraint(['last_assessed_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('organization_id', 'requirement_id', name='uq_org_requirement_assessment'),
    )
    op.create_index(
        'ix_org_requirement_assessments_org',
        'organization_requirement_assessments',
        ['organization_id'],
        unique=False,
    )
    op.create_index(
        'ix_org_requirement_assessments_flag',
        'organization_requirement_assessments',
        ['computed_flag'],
        unique=False,
    )

    op.create_table(
        'requirement_evidence_links',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('organization_id', sa.Integer(), nullable=False),
        sa.Column('requirement_id', sa.Integer(), nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('evidence_bucket', sa.String(length=30), nullable=False),
        sa.Column('rationale_note', sa.Text(), nullable=True),
        sa.Column('linked_by_user_id', sa.Integer(), nullable=True),
        sa.Column('linked_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['requirement_id'], ['compliance_requirements.id']),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id']),
        sa.ForeignKeyConstraint(['linked_by_user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'organization_id',
            'requirement_id',
            'document_id',
            'evidence_bucket',
            name='uq_requirement_evidence_link',
        ),
    )
    op.create_index(
        'ix_requirement_evidence_links_org_requirement',
        'requirement_evidence_links',
        ['organization_id', 'requirement_id'],
        unique=False,
    )
    op.create_index(
        'ix_requirement_evidence_links_document',
        'requirement_evidence_links',
        ['document_id'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_requirement_evidence_links_document', table_name='requirement_evidence_links')
    op.drop_index('ix_requirement_evidence_links_org_requirement', table_name='requirement_evidence_links')
    op.drop_table('requirement_evidence_links')

    op.drop_index('ix_org_requirement_assessments_flag', table_name='organization_requirement_assessments')
    op.drop_index('ix_org_requirement_assessments_org', table_name='organization_requirement_assessments')
    op.drop_table('organization_requirement_assessments')

    op.drop_index('ix_compliance_requirements_quality_indicator_code', table_name='compliance_requirements')
    op.drop_index('ix_compliance_requirements_requirement_id', table_name='compliance_requirements')
    op.drop_table('compliance_requirements')

    op.drop_index('ix_compliance_framework_versions_org_active', table_name='compliance_framework_versions')
    op.drop_table('compliance_framework_versions')
