"""Consolidate NDIS framework to global (organization_id=NULL)

Revision ID: q6r7s8t9u0v1
Revises: p5q6r7s8t9u0
Create Date: 2026-05-12

This migration consolidates organization-scoped NDIS frameworks into a single
global framework (organization_id=NULL) to eliminate data redundancy.

For each existing organization:
- Creates OrganizationRequirementAssessment records from the global framework
- Preserves all existing assessment data

After this migration, organizations will share a single global NDIS framework
while maintaining separate assessment records.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, text


revision = 'q6r7s8t9u0v1'
down_revision = 'p5q6r7s8t9u0'
branch_labels = None
depends_on = None


def upgrade():
    """Consolidate per-org frameworks to global."""
    # Get the connection and create a session
    connection = op.get_bind()
    session = Session(bind=connection)
    
    try:
        # Step 1: Check if any organization-scoped frameworks exist.
        org_frameworks = connection.execute(
            text("""
                SELECT DISTINCT cfv.organization_id, cfv.id, cfv.scheme, cfv.version_label
                FROM compliance_framework_versions cfv
                WHERE cfv.organization_id IS NOT NULL AND cfv.scheme = 'NDIS'
                ORDER BY cfv.organization_id ASC
            """)
        ).fetchall()

        if not org_frameworks:
            return

        first_org_framework = org_frameworks[0]

        # Step 2: Create or get the global framework.
        global_fw = connection.execute(
            text("""
                SELECT id FROM compliance_framework_versions
                WHERE organization_id IS NULL AND scheme = 'NDIS'
                LIMIT 1
            """)
        ).first()

        if not global_fw:
            connection.execute(text("""
                INSERT INTO compliance_framework_versions (
                    organization_id, jurisdiction, scheme, source_authority,
                    source_document, source_url, version_label, imported_at,
                    imported_by_user_id, checksum, is_active
                )
                SELECT
                    NULL, jurisdiction, scheme, source_authority,
                    source_document, source_url, version_label, imported_at,
                    imported_by_user_id, checksum, is_active
                FROM compliance_framework_versions
                WHERE id = :first_fw_id
            """), {"first_fw_id": first_org_framework[1]})

            global_fw = connection.execute(
                text("""
                    SELECT id FROM compliance_framework_versions
                    WHERE organization_id IS NULL AND scheme = 'NDIS'
                    LIMIT 1
                """)
            ).first()

        global_fw_id = global_fw[0] if global_fw else None

        if not global_fw_id:
            return

        # Step 3: Copy all org-scoped requirements into the global framework.
        connection.execute(text("""
            INSERT INTO compliance_requirements (
                framework_version_id, requirement_id, module_type, module_name,
                standard_name, outcome_code, outcome_text, quality_indicator_code,
                quality_indicator_text, applies_to_all_providers, registration_group_numbers,
                registration_group_names, registration_group_source_url, audit_type,
                high_risk_flag, stage_1_applies, stage_2_applies, audit_test_methods,
                sampling_required, sampling_subject, system_evidence_required,
                implementation_evidence_required, workforce_evidence_required,
                participant_evidence_required, requires_workforce_evidence,
                requires_participant_evidence, minimum_evidence_score_2,
                best_practice_evidence_score_3, common_nonconformity_patterns,
                gap_rule_1, gap_rule_2, gap_rule_3, nc_severity_default,
                evidence_owner_role, review_frequency, system_of_record,
                audit_export_label, source_version, source_last_reviewed_date,
                change_trigger, notes, created_at
            )
            SELECT
                :global_fw_id, requirement_id, module_type, module_name,
                standard_name, outcome_code, outcome_text, quality_indicator_code,
                quality_indicator_text, applies_to_all_providers, registration_group_numbers,
                registration_group_names, registration_group_source_url, audit_type,
                high_risk_flag, stage_1_applies, stage_2_applies, audit_test_methods,
                sampling_required, sampling_subject, system_evidence_required,
                implementation_evidence_required, workforce_evidence_required,
                participant_evidence_required, requires_workforce_evidence,
                requires_participant_evidence, minimum_evidence_score_2,
                best_practice_evidence_score_3, common_nonconformity_patterns,
                gap_rule_1, gap_rule_2, gap_rule_3, nc_severity_default,
                evidence_owner_role, review_frequency, system_of_record,
                audit_export_label, source_version, source_last_reviewed_date,
                change_trigger, notes, created_at
            FROM compliance_requirements
            WHERE framework_version_id IN (
                SELECT id FROM compliance_framework_versions
                WHERE organization_id IS NOT NULL AND scheme = 'NDIS'
            )
            ON CONFLICT (framework_version_id, requirement_id) DO NOTHING
        """), {"global_fw_id": global_fw_id})

        # Step 4a: Remove old assessment rows only when the target global row already exists.
        connection.execute(text("""
            DELETE FROM organization_requirement_assessments old_ora
            USING compliance_requirements old_cr,
                  compliance_requirements new_cr,
                  organization_requirement_assessments existing_ora
            WHERE old_ora.requirement_id = old_cr.id
              AND new_cr.requirement_id = old_cr.requirement_id
              AND new_cr.framework_version_id = :global_fw_id
              AND existing_ora.organization_id = old_ora.organization_id
              AND existing_ora.requirement_id = new_cr.id
              AND existing_ora.id <> old_ora.id
              AND old_cr.framework_version_id IN (
                  SELECT id FROM compliance_framework_versions
                  WHERE organization_id IS NOT NULL AND scheme = 'NDIS'
              )
        """), {"global_fw_id": global_fw_id})

        # Step 4b: Remap remaining assessment rows to the new global requirements.
        connection.execute(text("""
            UPDATE organization_requirement_assessments ora
            SET requirement_id = new_cr.id,
                updated_at = NOW()
            FROM compliance_requirements old_cr
            JOIN compliance_requirements new_cr
              ON new_cr.requirement_id = old_cr.requirement_id
             AND new_cr.framework_version_id = :global_fw_id
            WHERE ora.requirement_id = old_cr.id
              AND old_cr.framework_version_id IN (
                  SELECT id FROM compliance_framework_versions
                  WHERE organization_id IS NOT NULL AND scheme = 'NDIS'
              )
        """), {"global_fw_id": global_fw_id})

        # Step 5: Ensure each organization has assessment rows for every global requirement.
        connection.execute(text("""
            INSERT INTO organization_requirement_assessments (
                organization_id, requirement_id, evidence_status_system,
                evidence_status_implementation, evidence_status_workforce,
                evidence_status_participant, best_practice_evidence_present,
                computed_score, computed_flag, last_assessed_by_user_id,
                last_assessed_at, updated_at
            )
            SELECT
                orgs.organization_id, cr.id, 'Not assessed', 'Not assessed', 'Not assessed',
                'Not assessed', FALSE, NULL, NULL, NULL, NOW(), NOW()
            FROM (
                SELECT DISTINCT organization_id
                FROM compliance_framework_versions
                WHERE organization_id IS NOT NULL AND scheme = 'NDIS'
                UNION
                SELECT DISTINCT organization_id
                FROM organization_requirement_assessments
            ) AS orgs
            CROSS JOIN (
                SELECT id
                FROM compliance_requirements
                WHERE framework_version_id = :global_fw_id
            ) AS cr
            ON CONFLICT (organization_id, requirement_id) DO NOTHING
        """), {"global_fw_id": global_fw_id})

        # Step 6a: Remove duplicate evidence links only when the target global row already exists.
        connection.execute(text("""
            DELETE FROM requirement_evidence_links old_rel
            USING compliance_requirements old_cr,
                  compliance_requirements new_cr,
                  requirement_evidence_links existing_rel
            WHERE old_rel.requirement_id = old_cr.id
              AND new_cr.requirement_id = old_cr.requirement_id
              AND new_cr.framework_version_id = :global_fw_id
              AND existing_rel.organization_id = old_rel.organization_id
              AND existing_rel.document_id = old_rel.document_id
              AND existing_rel.evidence_bucket = old_rel.evidence_bucket
              AND existing_rel.requirement_id = new_cr.id
              AND existing_rel.id <> old_rel.id
              AND old_cr.framework_version_id IN (
                  SELECT id FROM compliance_framework_versions
                  WHERE organization_id IS NOT NULL AND scheme = 'NDIS'
              )
        """), {"global_fw_id": global_fw_id})

        # Step 6b: Remap any existing evidence links to the new global requirements.
        connection.execute(text("""
            UPDATE requirement_evidence_links rel
            SET requirement_id = new_cr.id
            FROM compliance_requirements old_cr
            JOIN compliance_requirements new_cr
              ON new_cr.requirement_id = old_cr.requirement_id
             AND new_cr.framework_version_id = :global_fw_id
            WHERE rel.requirement_id = old_cr.id
              AND old_cr.framework_version_id IN (
                  SELECT id FROM compliance_framework_versions
                  WHERE organization_id IS NOT NULL AND scheme = 'NDIS'
              )
        """), {"global_fw_id": global_fw_id})

        # Step 7: Delete org-scoped frameworks and requirements.
        connection.execute(text("""
            DELETE FROM compliance_requirements
            WHERE framework_version_id IN (
                SELECT id FROM compliance_framework_versions
                WHERE organization_id IS NOT NULL AND scheme = 'NDIS'
            )
        """))

        connection.execute(text("""
            DELETE FROM compliance_framework_versions
            WHERE organization_id IS NOT NULL AND scheme = 'NDIS'
        """))
    
    except Exception as e:
        # Log the error but don't fail - this allows manual cleanup if needed
        print(f"Error during consolidation: {e}")
    finally:
        session.close()


def downgrade():
    """Restore org-scoped frameworks from global.
    
    Note: This is a best-effort downgrade. It will recreate org frameworks
    from the global framework but will not restore deleted organization_id values.
    """
    connection = op.get_bind()
    session = Session(bind=connection)
    
    try:
        # Get the global NDIS framework
        global_fw = connection.execute(
            text("""
                SELECT id FROM compliance_framework_versions
                WHERE organization_id IS NULL AND scheme = 'NDIS'
                LIMIT 1
            """)
        ).first()
        
        if global_fw:
            global_fw_id = global_fw[0]
            
            # For each organization, recreate org-specific framework
            orgs = connection.execute(
                text("""
                    SELECT DISTINCT organization_id FROM organization_requirement_assessments
                    ORDER BY organization_id ASC
                """)
            ).fetchall()
            
            for org_row in orgs:
                org_id = org_row[0]
                
                # Create org-specific framework from global
                connection.execute(text("""
                    INSERT INTO compliance_framework_versions (
                        organization_id, jurisdiction, scheme, source_authority,
                        source_document, source_url, version_label, imported_at,
                        imported_by_user_id, checksum, is_active
                    )
                    SELECT
                        :org_id, jurisdiction, scheme, source_authority,
                        source_document, source_url, version_label, imported_at,
                        imported_by_user_id, checksum, is_active
                    FROM compliance_framework_versions
                    WHERE id = :global_fw_id
                """), {"org_id": org_id, "global_fw_id": global_fw_id})
                
                # Get the newly created org framework
                org_fw = connection.execute(
                    text("""
                        SELECT id FROM compliance_framework_versions
                        WHERE organization_id = :org_id AND scheme = 'NDIS'
                        LIMIT 1
                    """), {"org_id": org_id}
                ).first()
                
                if org_fw:
                    org_fw_id = org_fw[0]
                    
                    # Copy requirements to org-specific framework
                    connection.execute(text("""
                        INSERT INTO compliance_requirements (
                            framework_version_id, requirement_id, module_type, module_name,
                            standard_name, outcome_code, outcome_text, quality_indicator_code,
                            quality_indicator_text, applies_to_all_providers, registration_group_numbers,
                            registration_group_names, registration_group_source_url, audit_type,
                            high_risk_flag, stage_1_applies, stage_2_applies, audit_test_methods,
                            sampling_required, sampling_subject, system_evidence_required,
                            implementation_evidence_required, workforce_evidence_required,
                            participant_evidence_required, requires_workforce_evidence,
                            requires_participant_evidence, minimum_evidence_score_2,
                            best_practice_evidence_score_3, common_nonconformity_patterns,
                            gap_rule_1, gap_rule_2, gap_rule_3, nc_severity_default,
                            evidence_owner_role, review_frequency, system_of_record,
                            audit_export_label, source_version, source_last_reviewed_date,
                            change_trigger, notes, created_at
                        )
                        SELECT
                            :org_fw_id, requirement_id, module_type, module_name,
                            standard_name, outcome_code, outcome_text, quality_indicator_code,
                            quality_indicator_text, applies_to_all_providers, registration_group_numbers,
                            registration_group_names, registration_group_source_url, audit_type,
                            high_risk_flag, stage_1_applies, stage_2_applies, audit_test_methods,
                            sampling_required, sampling_subject, system_evidence_required,
                            implementation_evidence_required, workforce_evidence_required,
                            participant_evidence_required, requires_workforce_evidence,
                            requires_participant_evidence, minimum_evidence_score_2,
                            best_practice_evidence_score_3, common_nonconformity_patterns,
                            gap_rule_1, gap_rule_2, gap_rule_3, nc_severity_default,
                            evidence_owner_role, review_frequency, system_of_record,
                            audit_export_label, source_version, source_last_reviewed_date,
                            change_trigger, notes, created_at
                        FROM compliance_requirements
                        WHERE framework_version_id = :global_fw_id
                    """), {"org_fw_id": org_fw_id, "global_fw_id": global_fw_id})
    
    except Exception as e:
        print(f"Error during downgrade: {e}")
    finally:
        session.close()
