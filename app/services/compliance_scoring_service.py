from __future__ import annotations

from datetime import datetime, timezone

from app import db
from app.models import (
    ComplianceFrameworkVersion,
    ComplianceRequirement,
    OrganizationRequirementAssessment,
    RequirementEvidenceLink,
)
from sqlalchemy import or_


class ComplianceScoringService:
    """Deterministic scoring for requirement assessments based on linked evidence."""

    SCORE_FLAG_CRITICAL_GAP = 'Critical gap'
    SCORE_FLAG_HIGH_RISK_GAP = 'High risk gap'
    SCORE_FLAG_OK = 'OK'
    SCORE_FLAG_MATURE = 'Mature'

    def recompute_for_organization(
        self,
        *,
        organization_id: int,
        assessed_by_user_id: int | None = None,
        commit: bool = True,
    ) -> int:
        """Recompute assessments for all active requirements visible to an organization."""
        requirements = (
            db.session.query(ComplianceRequirement.id)
            .join(ComplianceFrameworkVersion, ComplianceFrameworkVersion.id == ComplianceRequirement.framework_version_id)
            .filter(
                ComplianceFrameworkVersion.is_active.is_(True),
                or_(
                    ComplianceFrameworkVersion.organization_id.is_(None),
                    ComplianceFrameworkVersion.organization_id == int(organization_id),
                ),
            )
            .all()
        )

        total = 0
        for requirement_id, in requirements:
            self.recompute_requirement_assessment(
                organization_id=int(organization_id),
                requirement_id=int(requirement_id),
                assessed_by_user_id=assessed_by_user_id,
                commit=False,
            )
            total += 1

        if commit:
            db.session.commit()
        return total

    def recompute_requirement_assessment(
        self,
        *,
        organization_id: int,
        requirement_id: int,
        assessed_by_user_id: int | None = None,
        commit: bool = True,
    ) -> OrganizationRequirementAssessment:
        requirement = db.session.get(ComplianceRequirement, int(requirement_id))
        if requirement is None:
            raise ValueError(f'Requirement not found: {requirement_id}')

        links = RequirementEvidenceLink.query.filter_by(
            organization_id=int(organization_id),
            requirement_id=int(requirement_id),
        ).all()

        links_by_bucket: dict[str, int] = {}
        for link in links:
            bucket = (link.evidence_bucket or '').strip().lower()
            if not bucket:
                continue
            links_by_bucket[bucket] = links_by_bucket.get(bucket, 0) + 1

        status_system = self._bucket_status(
            required=True,
            has_links=links_by_bucket.get('system', 0) > 0,
        )
        status_implementation = self._bucket_status(
            required=True,
            has_links=links_by_bucket.get('implementation', 0) > 0,
        )
        status_workforce = self._bucket_status(
            required=self._workforce_required(requirement),
            has_links=links_by_bucket.get('workforce', 0) > 0,
        )
        status_participant = self._bucket_status(
            required=self._participant_required(requirement),
            has_links=links_by_bucket.get('participant', 0) > 0,
        )

        assessment = OrganizationRequirementAssessment.query.filter_by(
            organization_id=int(organization_id),
            requirement_id=int(requirement_id),
        ).first()
        if assessment is None:
            assessment = OrganizationRequirementAssessment(
                organization_id=int(organization_id),
                requirement_id=int(requirement_id),
            )
            db.session.add(assessment)

        assessment.evidence_status_system = status_system
        assessment.evidence_status_implementation = status_implementation
        assessment.evidence_status_workforce = status_workforce
        assessment.evidence_status_participant = status_participant

        score, flag = self._compute_score_and_flag(
            status_system=status_system,
            status_implementation=status_implementation,
            status_workforce=status_workforce,
            status_participant=status_participant,
            best_practice=bool(assessment.best_practice_evidence_present),
        )
        assessment.computed_score = score
        assessment.computed_flag = flag
        assessment.last_assessed_at = datetime.now(timezone.utc)
        assessment.last_assessed_by_user_id = assessed_by_user_id

        if commit:
            db.session.commit()
        else:
            db.session.flush()

        return assessment

    @staticmethod
    def _bucket_status(*, required: bool, has_links: bool) -> str:
        if not required:
            return 'N/A'
        return 'Present' if has_links else 'Missing'

    @staticmethod
    def _workforce_required(requirement: ComplianceRequirement) -> bool:
        return bool(
            requirement.requires_workforce_evidence
            or (requirement.workforce_evidence_required or '').strip()
        )

    @staticmethod
    def _participant_required(requirement: ComplianceRequirement) -> bool:
        return bool(
            requirement.requires_participant_evidence
            or (requirement.participant_evidence_required or '').strip()
        )

    def _compute_score_and_flag(
        self,
        *,
        status_system: str,
        status_implementation: str,
        status_workforce: str,
        status_participant: str,
        best_practice: bool,
    ) -> tuple[int, str]:
        required_statuses = [
            status_system,
            status_implementation,
            *( [] if status_workforce == 'N/A' else [status_workforce] ),
            *( [] if status_participant == 'N/A' else [status_participant] ),
        ]
        missing_count = sum(1 for status in required_statuses if status == 'Missing')

        if missing_count >= 2:
            return 0, self.SCORE_FLAG_CRITICAL_GAP
        if missing_count == 1:
            return 1, self.SCORE_FLAG_HIGH_RISK_GAP
        if best_practice:
            return 3, self.SCORE_FLAG_MATURE
        return 2, self.SCORE_FLAG_OK


compliance_scoring_service = ComplianceScoringService()
