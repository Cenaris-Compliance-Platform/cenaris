"""
Compliance setup service for initializing org assessments from global framework.
"""

from datetime import datetime, timezone
from app import db
from app.models import (
    ComplianceFrameworkVersion,
    ComplianceRequirement,
    OrganizationRequirementAssessment,
)


class ComplianceSetupError(Exception):
    pass


class ComplianceSetupService:
    @staticmethod
    def get_global_ndis_framework(session=None) -> ComplianceFrameworkVersion | None:
        """Fetch the global (organization_id=NULL) NDIS framework."""
        sess = session or db.session
        return (
            sess.query(ComplianceFrameworkVersion)
            .filter_by(
                organization_id=None,
                scheme='NDIS',
                is_active=True,
            )
            .first()
        )

    @staticmethod
    def create_org_assessments_from_global_framework(
        org_id: int,
        user_id: int | None = None,
        commit: bool = True,
        session = None,
    ) -> int:
        """
        Create OrganizationRequirementAssessment records for an org
        from the global NDIS framework.
        
        Args:
            org_id: Organization ID
            user_id: Optional user ID to record as the initializer
            commit: Whether to commit the transaction (disable during active flushes)
            session: Optional session override (uses db.session by default)
        
        Returns:
            Number of new assessment records created
        
        Raises:
            ComplianceSetupError: If global framework not found or creation fails
        """
        sess = session or db.session
        global_fw = ComplianceSetupService.get_global_ndis_framework(session=sess)
        
        if not global_fw:
            raise ComplianceSetupError(
                'Global NDIS framework not found. '
                'Please contact support or run: flask import-master-mapping --file-path <path> (without --org-id)'
            )
        
        try:
            requirements = (
                sess.query(ComplianceRequirement)
                .filter_by(framework_version_id=global_fw.id)
                .all()
            )
            
            if not requirements:
                raise ComplianceSetupError('Global NDIS framework has no requirements.')
            
            created = 0
            for req in requirements:
                existing = (
                    sess.query(OrganizationRequirementAssessment)
                    .filter_by(
                        organization_id=int(org_id),
                        requirement_id=int(req.id),
                    )
                    .first()
                )
                
                if existing is None:
                    assessment = OrganizationRequirementAssessment(
                        organization_id=int(org_id),
                        requirement_id=int(req.id),
                        evidence_status_system='Not assessed',
                        evidence_status_implementation='Not assessed',
                        evidence_status_workforce='Not assessed',
                        evidence_status_participant='Not assessed',
                        best_practice_evidence_present=False,
                        last_assessed_by_user_id=user_id,
                        last_assessed_at=datetime.now(timezone.utc),
                    )
                    sess.add(assessment)
                    created += 1
            
            if commit:
                sess.commit()
            return created
        
        except ComplianceSetupError:
            raise
        except Exception as e:
            if commit:
                sess.rollback()
            raise ComplianceSetupError(f'Failed to create assessment records: {e}')


compliance_setup_service = ComplianceSetupService()
