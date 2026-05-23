from datetime import datetime, timezone

from app import db
from app.models import (
    ComplianceFrameworkVersion,
    ComplianceRequirement,
    Organization,
    OrganizationRequirementAssessment,
    User,
)
from app.services.compliance_mapping_service import compliance_mapping_service


def _create_org() -> Organization:
    org = Organization(
        name="Import Test Org",
        abn="12345678901",
        organization_type="Company",
        contact_email="org@example.com",
        address="1 Test Street",
        industry="Other",
        operates_in_australia=True,
        declarations_accepted_at=datetime.now(timezone.utc),
        data_processing_ack_at=datetime.now(timezone.utc),
    )
    db.session.add(org)
    db.session.flush()
    return org


def _create_user(org_id: int) -> User:
    user = User(
        email="importer@example.com",
        email_verified=True,
        is_active=True,
        organization_id=org_id,
    )
    user.set_password("Passw0rd1")
    db.session.add(user)
    db.session.flush()
    return user


def test_import_master_mapping_csv_creates_framework_requirements_and_assessments(app, tmp_path):
    csv_file = tmp_path / "mapping.csv"
    csv_file.write_text(
        "requirement_id,module_type,quality_indicator_code,scheme,jurisdiction,evidence_status_system,computed_score,last_reviewed_date,applies_to_all_providers,high_risk_flag\n"
        "REQ-1,Core,QI.1,NDIS,AU,Present,2,2025-01-20,yes,no\n"
        "REQ-2,Core,QI.2,NDIS,AU,Not assessed,1,2025-01-21,no,yes\n",
        encoding="utf-8",
    )

    with app.app_context():
        org = _create_org()
        user = _create_user(int(org.id))
        db.session.commit()

        result = compliance_mapping_service.import_master_mapping(
            str(csv_file),
            organization_id=int(org.id),
            imported_by_user_id=int(user.id),
            version_label="v2025.01",
        )

        assert result.total_rows == 2
        assert result.imported_requirements == 2
        assert result.imported_assessments == 2

        framework = ComplianceFrameworkVersion.query.filter_by(
            organization_id=int(org.id),
            scheme="NDIS",
            version_label="v2025.01",
        ).first()
        assert framework is not None
        assert framework.checksum

        requirements = ComplianceRequirement.query.filter_by(framework_version_id=int(framework.id)).all()
        assert len(requirements) == 2

        assessments = OrganizationRequirementAssessment.query.filter_by(organization_id=int(org.id)).all()
        assert len(assessments) == 2


def test_reimport_replaces_framework_requirements_and_org_assessments(app, tmp_path):
    csv_first = tmp_path / "mapping_first.csv"
    csv_first.write_text(
        "requirement_id,scheme,jurisdiction,evidence_status_system,computed_score\n"
        "REQ-1,NDIS,AU,Present,2\n"
        "REQ-2,NDIS,AU,Missing,1\n",
        encoding="utf-8",
    )

    csv_second = tmp_path / "mapping_second.csv"
    csv_second.write_text(
        "requirement_id,scheme,jurisdiction,evidence_status_system,computed_score\n"
        "REQ-3,NDIS,AU,Present,3\n",
        encoding="utf-8",
    )

    with app.app_context():
        org = _create_org()
        user = _create_user(int(org.id))
        db.session.commit()

        compliance_mapping_service.import_master_mapping(
            str(csv_first),
            organization_id=int(org.id),
            imported_by_user_id=int(user.id),
            version_label="v2025.01",
        )

        compliance_mapping_service.import_master_mapping(
            str(csv_second),
            organization_id=int(org.id),
            imported_by_user_id=int(user.id),
            version_label="v2025.01",
        )

        frameworks = ComplianceFrameworkVersion.query.filter_by(
            organization_id=int(org.id),
            scheme="NDIS",
            version_label="v2025.01",
        ).all()
        assert len(frameworks) == 1

        remaining_requirements = ComplianceRequirement.query.filter_by(
            framework_version_id=int(frameworks[0].id)
        ).all()
        assert len(remaining_requirements) == 1
        assert remaining_requirements[0].requirement_id == "REQ-3"

        assessments = OrganizationRequirementAssessment.query.filter_by(organization_id=int(org.id)).all()
        assert len(assessments) == 1
        assert assessments[0].computed_score == 3
