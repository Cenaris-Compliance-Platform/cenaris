from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, or_, func

from app import db
from app.models import (
    ComplianceFrameworkVersion,
    ComplianceRequirement,
    OrganizationRequirementAssessment,
    RequirementEvidenceLink,
)


# ---------------------------------------------------------------------------
# Constants — user-facing label mapping
# ---------------------------------------------------------------------------

FLAG_CRITICAL_GAP = 'Critical gap'
FLAG_HIGH_RISK_GAP = 'High risk gap'
FLAG_OK = 'OK'
FLAG_MATURE = 'Mature'

_USER_LABEL: dict[str | None, str] = {
    FLAG_CRITICAL_GAP: 'Critical Gap',
    FLAG_HIGH_RISK_GAP: 'Needs Attention',
    FLAG_OK: 'Evidence Present',
    FLAG_MATURE: 'Best Practice',
    None: 'Not Yet Assessed',
}

_FLAG_SEVERITY: dict[str | None, int] = {
    FLAG_CRITICAL_GAP: 0,
    FLAG_HIGH_RISK_GAP: 1,
    FLAG_OK: 2,
    FLAG_MATURE: 3,
    None: -1,
}

_FLAG_COLOUR: dict[str | None, str] = {
    FLAG_CRITICAL_GAP: 'danger',
    FLAG_HIGH_RISK_GAP: 'warning',
    FLAG_OK: 'success',
    FLAG_MATURE: 'primary',
    None: 'secondary',
}

_FLAG_ICON: dict[str | None, str] = {
    FLAG_CRITICAL_GAP: 'bi-x-circle-fill',
    FLAG_HIGH_RISK_GAP: 'bi-exclamation-triangle-fill',
    FLAG_OK: 'bi-check-circle-fill',
    FLAG_MATURE: 'bi-star-fill',
    None: 'bi-dash-circle',
}

_READINESS_BAND: list[tuple[int, str, str]] = [
    # (min_score_inclusive, band_label, band_colour)
    (80, 'Audit Ready', 'success'),
    (50, 'Partially Ready', 'warning'),
    (0,  'Not Ready',     'danger'),
]


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class RequirementRow:
    """One row in the Audit Readiness Centre table."""
    requirement_db_id: int
    requirement_id: str
    module_name: str
    module_type: str
    standard_name: str
    audit_type: str
    high_risk_flag: bool

    # Evidence bucket statuses
    status_system: str
    status_implementation: str
    status_workforce: str
    status_participant: str

    # Computed flag + score
    computed_flag: Optional[str]
    computed_score: Optional[int]

    # User-facing labels
    user_label: str
    flag_colour: str
    flag_icon: str
    severity: int

    # "What auditors check" — from gap_rule fields
    gap_rules: list[str]
    nonconformity_patterns: str

    # Linked evidence count
    evidence_count: int

    # Owner / review
    evidence_owner_role: str
    review_frequency: str

    # When last assessed
    last_assessed_at: Optional[datetime]


@dataclass
class ModuleBreakdown:
    """Stats for one NDIS Practice Standard module."""
    module_name: str
    total: int = 0
    critical: int = 0
    needs_attention: int = 0
    evidence_present: int = 0
    best_practice: int = 0
    not_assessed: int = 0

    @property
    def readiness_pct(self) -> int:
        if self.total == 0:
            return 0
        met = self.evidence_present + self.best_practice
        return min(100, round(met / self.total * 100))

    @property
    def progress_colour(self) -> str:
        pct = self.readiness_pct
        if pct >= 80:
            return 'success'
        if pct >= 50:
            return 'warning'
        return 'danger'


@dataclass
class SummaryStats:
    """Top-level numbers shown in the stat cards."""
    total: int = 0
    critical: int = 0
    needs_attention: int = 0
    evidence_present: int = 0
    best_practice: int = 0
    not_assessed: int = 0

    @property
    def readiness_pct(self) -> int:
        if self.total == 0:
            return 0
        met = self.evidence_present + self.best_practice
        return min(100, round(met / self.total * 100))

    @property
    def readiness_band(self) -> str:
        pct = self.readiness_pct
        for min_pct, label, _ in _READINESS_BAND:
            if pct >= min_pct:
                return label
        return 'Not Ready'

    @property
    def readiness_colour(self) -> str:
        pct = self.readiness_pct
        for min_pct, _, colour in _READINESS_BAND:
            if pct >= min_pct:
                return colour
        return 'danger'


@dataclass
class GapAnalysisPayload:
    """Everything the route needs to render the Audit Readiness Centre."""
    summary: SummaryStats
    module_breakdown: list[ModuleBreakdown]
    requirements: list[RequirementRow]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    framework_label: str = 'NDIS Practice Standards'
    has_data: bool = True


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class GapAnalysisService:
    """Aggregate compliance scoring data into the Audit Readiness Centre payload."""

    def build_for_organization(self, organization_id: int) -> GapAnalysisPayload:
        """
        Build the full Audit Readiness Centre payload for one organisation.

        Reads from OrganizationRequirementAssessment (already scored) joined
        with ComplianceRequirement metadata.  Does NOT recompute scores —
        that is ComplianceScoringService's job.
        """
        org_id = int(organization_id)
        from app.models import Organization
        organization = db.session.get(Organization, org_id)
        enabled_modules = []
        filter_modules = False
        if organization and organization.enabled_modules_list is not None:
            filter_modules = True
            enabled_modules = [m.strip() for m in organization.enabled_modules_list.split(',') if m.strip()]

        rows = (
            db.session.query(ComplianceRequirement, OrganizationRequirementAssessment)
            .join(
                ComplianceFrameworkVersion,
                ComplianceFrameworkVersion.id == ComplianceRequirement.framework_version_id,
            )
            .outerjoin(
                OrganizationRequirementAssessment,
                and_(
                    OrganizationRequirementAssessment.organization_id == org_id,
                    OrganizationRequirementAssessment.requirement_id == ComplianceRequirement.id,
                ),
            )
            .filter(
                ComplianceFrameworkVersion.is_active.is_(True),
                or_(
                    ComplianceFrameworkVersion.organization_id.is_(None),
                    ComplianceFrameworkVersion.organization_id == org_id,
                ),
            )
            .order_by(
                ComplianceRequirement.module_name.asc(),
                ComplianceRequirement.requirement_id.asc(),
            )
            .all()
        )

        if not rows:
            return GapAnalysisPayload(
                summary=SummaryStats(),
                module_breakdown=[],
                requirements=[],
                has_data=False,
            )

        # Build evidence link count map: requirement_id → count
        req_ids = [r.id for r, _ in rows]
        link_counts: dict[int, int] = {}
        if req_ids:
            link_count_rows = (
                db.session.query(
                    RequirementEvidenceLink.requirement_id,
                    func.count(RequirementEvidenceLink.id).label('cnt'),
                )
                .filter(
                    RequirementEvidenceLink.organization_id == org_id,
                    RequirementEvidenceLink.requirement_id.in_(req_ids),
                )
                .group_by(RequirementEvidenceLink.requirement_id)
                .all()
            )
            link_counts = {row.requirement_id: row.cnt for row in link_count_rows}

        summary = SummaryStats()
        module_map: dict[str, ModuleBreakdown] = {}
        requirement_rows: list[RequirementRow] = []

        for req, assessment in rows:
            module_key = (req.module_name or 'Uncategorised').strip()
            
            # Filter by enabled modules (if they have explicitly saved their settings)
            if filter_modules and module_key not in enabled_modules:
                continue

            flag = (assessment.computed_flag if assessment else None)
            score = (assessment.computed_score if assessment else None)

            # If it's technically a 'Critical gap' but there are zero evidence links
            # and no human has explicitly assessed it, it's actually just 'Not Yet Assessed'.
            if flag == FLAG_CRITICAL_GAP and link_counts.get(int(req.id), 0) == 0:
                if not assessment or not assessment.last_assessed_by_user_id:
                    flag = None

            user_label = _USER_LABEL.get(flag, 'Not Yet Assessed')
            flag_colour = _FLAG_COLOUR.get(flag, 'secondary')
            flag_icon = _FLAG_ICON.get(flag, 'bi-dash-circle')
            severity = _FLAG_SEVERITY.get(flag, -1)

            # Accumulate summary stats
            summary.total += 1
            if flag == FLAG_CRITICAL_GAP:
                summary.critical += 1
            elif flag == FLAG_HIGH_RISK_GAP:
                summary.needs_attention += 1
            elif flag == FLAG_OK:
                summary.evidence_present += 1
            elif flag == FLAG_MATURE:
                summary.best_practice += 1
            else:
                summary.not_assessed += 1

            # Module grouping
            module_key = (req.module_name or 'Uncategorised').strip()
            if module_key not in module_map:
                module_map[module_key] = ModuleBreakdown(module_name=module_key)
            mod = module_map[module_key]
            mod.total += 1
            if flag == FLAG_CRITICAL_GAP:
                mod.critical += 1
            elif flag == FLAG_HIGH_RISK_GAP:
                mod.needs_attention += 1
            elif flag == FLAG_OK:
                mod.evidence_present += 1
            elif flag == FLAG_MATURE:
                mod.best_practice += 1
            else:
                mod.not_assessed += 1

            # Gap rules — filter empty values
            gap_rules = [
                rule.strip()
                for rule in [
                    req.gap_rule_1 or '',
                    req.gap_rule_2 or '',
                    req.gap_rule_3 or '',
                ]
                if rule.strip()
            ]

            # Evidence bucket statuses
            status_system = (assessment.evidence_status_system if assessment else 'Not assessed') or 'Not assessed'
            status_impl = (assessment.evidence_status_implementation if assessment else 'Not assessed') or 'Not assessed'
            status_workforce = (assessment.evidence_status_workforce if assessment else 'Not assessed') or 'Not assessed'
            status_participant = (assessment.evidence_status_participant if assessment else 'Not assessed') or 'Not assessed'

            requirement_rows.append(RequirementRow(
                requirement_db_id=int(req.id),
                requirement_id=(req.requirement_id or '').strip(),
                module_name=module_key,
                module_type=(req.module_type or '').strip(),
                standard_name=(req.standard_name or '').strip(),
                audit_type=(req.audit_type or '').strip(),
                high_risk_flag=bool(req.high_risk_flag),
                status_system=status_system,
                status_implementation=status_impl,
                status_workforce=status_workforce,
                status_participant=status_participant,
                computed_flag=flag,
                computed_score=score,
                user_label=user_label,
                flag_colour=flag_colour,
                flag_icon=flag_icon,
                severity=severity,
                gap_rules=gap_rules,
                nonconformity_patterns=(req.common_nonconformity_patterns or '').strip(),
                evidence_count=link_counts.get(int(req.id), 0),
                evidence_owner_role=(req.evidence_owner_role or '').strip(),
                review_frequency=(req.review_frequency or '').strip(),
                last_assessed_at=assessment.last_assessed_at if assessment else None,
            ))

        # Sort modules: Core first, then worst readiness
        module_breakdown = sorted(
            module_map.values(),
            key=lambda m: (
                0 if m.module_name.lower().startswith('core') else 1,
                m.readiness_pct
            ),
        )

        # Sort requirements: most severe first
        requirement_rows.sort(key=lambda r: (r.severity, r.module_name, r.requirement_id))

        # Detect the framework label from the first active row
        framework_label = 'NDIS Practice Standards'

        return GapAnalysisPayload(
            summary=summary,
            module_breakdown=module_breakdown,
            requirements=requirement_rows,
            generated_at=datetime.now(timezone.utc),
            framework_label=framework_label,
            has_data=True,
        )

    @staticmethod
    def flag_label(flag: str | None) -> str:
        return _USER_LABEL.get(flag, 'Not Yet Assessed')

    @staticmethod
    def flag_colour(flag: str | None) -> str:
        return _FLAG_COLOUR.get(flag, 'secondary')

    @staticmethod
    def flag_icon(flag: str | None) -> str:
        return _FLAG_ICON.get(flag, 'bi-dash-circle')


gap_analysis_service = GapAnalysisService()
