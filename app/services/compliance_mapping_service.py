from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
import re
from typing import Any

import pandas as pd

from app import db
from app.models import (
    ComplianceFrameworkVersion,
    ComplianceRequirement,
    OrganizationRequirementAssessment,
)


def _normalize_header(value: Any) -> str:
    text = str(value or '').strip().lower()
    text = re.sub(r'[^a-z0-9]+', '_', text)
    return text.strip('_')


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {'nan', 'none', 'null'}:
        return None
    return text


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    if text in {'y', 'yes', 'true', '1', 't'}:
        return True
    if text in {'n', 'no', 'false', '0', 'f'}:
        return False
    return default


def _as_int(value: Any) -> int | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(float(text))
    except Exception:
        return None


def _as_date(value: Any):
    if value is None:
        return None
    text = _clean_text(value)
    if not text:
        return None

    try:
        parsed = pd.to_datetime(text, errors='coerce')
        if pd.isna(parsed):
            return None
        return parsed.date()
    except Exception:
        return None


def _first_non_empty(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key not in row:
            continue
        value = row.get(key)
        if _clean_text(value) is not None:
            return value
    return None


@dataclass
class ImportResult:
    framework_version_id: int
    total_rows: int
    imported_requirements: int
    imported_assessments: int


class ComplianceMappingImportError(Exception):
    pass


class ComplianceMappingService:
    REQUIRED_COLUMNS = {'requirement_id'}

    def import_master_mapping(
        self,
        file_path: str,
        *,
        organization_id: int | None = None,
        imported_by_user_id: int | None = None,
        version_label: str = 'v1.0',
    ) -> ImportResult:
        if not file_path or not os.path.exists(file_path):
            raise ComplianceMappingImportError(f'File not found: {file_path}')

        df = self._read_table(file_path)
        if df.empty:
            raise ComplianceMappingImportError('Input file is empty.')

        renamed = {_normalize_header(col): col for col in df.columns}
        normalized_rows: list[dict[str, Any]] = []
        for _, raw in df.iterrows():
            row = {k: raw[v] for k, v in renamed.items()}
            normalized_rows.append(row)

        available = set(normalized_rows[0].keys())
        missing = self.REQUIRED_COLUMNS - available
        if missing:
            raise ComplianceMappingImportError(
                'Missing required column(s): ' + ', '.join(sorted(missing))
            )

        checksum = self._file_checksum(file_path)
        first = normalized_rows[0]
        scheme = _clean_text(first.get('scheme')) or 'NDIS'
        jurisdiction = _clean_text(first.get('jurisdiction')) or 'AU'

        framework = (
            ComplianceFrameworkVersion.query
            .filter_by(
                organization_id=organization_id,
                scheme=scheme,
                version_label=(version_label or 'v1.0').strip() or 'v1.0',
            )
            .first()
        )

        if framework is None:
            framework = ComplianceFrameworkVersion(
                organization_id=organization_id,
                scheme=scheme,
                jurisdiction=jurisdiction,
                version_label=(version_label or 'v1.0').strip() or 'v1.0',
            )
            db.session.add(framework)
            db.session.flush()
        else:
            ComplianceRequirement.query.filter_by(framework_version_id=framework.id).delete(synchronize_session=False)

        framework.source_authority = _clean_text(first.get('source_authority'))
        framework.source_document = _clean_text(first.get('source_document'))
        framework.source_url = _clean_text(first.get('source_url'))
        framework.imported_by_user_id = imported_by_user_id
        framework.imported_at = datetime.now(timezone.utc)
        framework.checksum = checksum
        framework.is_active = True

        if organization_id is not None:
            OrganizationRequirementAssessment.query.filter_by(organization_id=int(organization_id)).delete(synchronize_session=False)

        imported_requirements = 0
        imported_assessments = 0

        for index, row in enumerate(normalized_rows, start=1):
            requirement_identifier = _clean_text(row.get('requirement_id')) or _clean_text(row.get('quality_indicator_code'))
            if not requirement_identifier:
                requirement_identifier = f'ROW-{index}'

            requirement = ComplianceRequirement(
                framework_version_id=framework.id,
                requirement_id=requirement_identifier,
                module_type=_clean_text(row.get('module_type')),
                module_name=_clean_text(row.get('module_name')),
                standard_name=_clean_text(row.get('standard_name')),
                outcome_code=_clean_text(row.get('outcome_code')),
                outcome_text=_clean_text(row.get('outcome_text')),
                quality_indicator_code=_clean_text(row.get('quality_indicator_code')),
                quality_indicator_text=_clean_text(row.get('quality_indicator_text')),
                applies_to_all_providers=_as_bool(row.get('applies_to_all_providers')),
                registration_group_numbers=_clean_text(row.get('registration_group_numbers')),
                registration_group_names=_clean_text(row.get('registration_group_names')),
                registration_group_source_url=_clean_text(row.get('registration_group_source_url')),
                audit_type=_clean_text(row.get('audit_type')),
                high_risk_flag=_as_bool(row.get('high_risk_flag')),
                stage_1_applies=_as_bool(row.get('stage_1_applies')),
                stage_2_applies=_as_bool(row.get('stage_2_applies')),
                audit_test_methods=_clean_text(row.get('audit_test_methods')),
                sampling_required=_as_bool(row.get('sampling_required')),
                sampling_subject=_clean_text(row.get('sampling_subject')),
                system_evidence_required=_clean_text(row.get('system_evidence_required')),
                implementation_evidence_required=_clean_text(row.get('implementation_evidence_required')),
                workforce_evidence_required=_clean_text(row.get('workforce_evidence_required')),
                participant_evidence_required=_clean_text(row.get('participant_evidence_required')),
                requires_workforce_evidence=_as_bool(row.get('requires_workforce_evidence')),
                requires_participant_evidence=_as_bool(row.get('requires_participant_evidence')),
                minimum_evidence_score_2=_clean_text(row.get('minimum_evidence_score_2')),
                best_practice_evidence_score_3=_clean_text(row.get('best_practice_evidence_score_3')),
                common_nonconformity_patterns=_clean_text(row.get('common_nonconformity_patterns')),
                gap_rule_1=_clean_text(row.get('gap_rule_1')),
                gap_rule_2=_clean_text(row.get('gap_rule_2')),
                gap_rule_3=_clean_text(row.get('gap_rule_3')),
                nc_severity_default=_clean_text(row.get('nc_severity_default')),
                evidence_owner_role=_clean_text(row.get('evidence_owner_role')),
                review_frequency=_clean_text(row.get('review_frequency')),
                system_of_record=_clean_text(row.get('system_of_record')),
                audit_export_label=_clean_text(row.get('audit_export_label')),
                source_version=_clean_text(row.get('version')),
                source_last_reviewed_date=_as_date(row.get('last_reviewed_date')),
                change_trigger=_clean_text(row.get('change_trigger')),
                notes=_clean_text(row.get('notes')),
            )
            db.session.add(requirement)
            db.session.flush()
            imported_requirements += 1

            if organization_id is not None:
                assessment = OrganizationRequirementAssessment(
                    organization_id=int(organization_id),
                    requirement_id=requirement.id,
                    evidence_status_system=_clean_text(row.get('evidence_status_system')) or 'Not assessed',
                    evidence_status_implementation=_clean_text(row.get('evidence_status_implementation')) or 'Not assessed',
                    evidence_status_workforce=_clean_text(row.get('evidence_status_workforce')) or 'Not assessed',
                    evidence_status_participant=_clean_text(row.get('evidence_status_participant')) or 'Not assessed',
                    best_practice_evidence_present=_as_bool(row.get('best_practice_evidence_present')),
                    computed_score=_as_int(row.get('computed_score')),
                    computed_flag=_clean_text(row.get('computed_flag')),
                    last_assessed_by_user_id=imported_by_user_id,
                    last_assessed_at=datetime.now(timezone.utc),
                )
                db.session.add(assessment)
                imported_assessments += 1

        db.session.commit()

        return ImportResult(
            framework_version_id=int(framework.id),
            total_rows=len(normalized_rows),
            imported_requirements=imported_requirements,
            imported_assessments=imported_assessments,
        )

    @staticmethod
    def _file_checksum(file_path: str) -> str:
        h = hashlib.sha256()
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _read_table(file_path: str) -> pd.DataFrame:
        lower = file_path.lower()
        if lower.endswith('.csv'):
            return pd.read_csv(file_path)
        if lower.endswith('.xlsx') or lower.endswith('.xlsm'):
            try:
                workbook = pd.ExcelFile(file_path)
                preferred = None
                for sheet in workbook.sheet_names:
                    if (sheet or '').strip().lower() == 'master_mapping':
                        preferred = sheet
                        break
                if preferred is None:
                    for sheet in workbook.sheet_names:
                        if 'mapping' in (sheet or '').strip().lower():
                            preferred = sheet
                            break
                return pd.read_excel(file_path, sheet_name=preferred or 0)
            except Exception:
                return pd.read_excel(file_path)
        if lower.endswith('.xls'):
            return pd.read_excel(file_path)
        raise ComplianceMappingImportError(
            'Unsupported file format. Use CSV or Excel (.xlsx/.xlsm/.xls).'
        )


compliance_mapping_service = ComplianceMappingService()
