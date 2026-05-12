"""
Test the compliance setup service for global framework initialization.
"""

import pytest
from datetime import datetime, timezone
from app import db
from app.models import (
    Organization,
    User,
    ComplianceFrameworkVersion,
    ComplianceRequirement,
    OrganizationRequirementAssessment,
)
from app.services.compliance_setup_service import compliance_setup_service, ComplianceSetupError


def _create_org(name: str) -> Organization:
    org = Organization(
        name=name,
        abn="12345678901",
        organization_type="Company",
        contact_email=f"test-{name.lower().replace(' ', '-')}@example.com",
        address="1 Test Street",
        industry="Other",
        operates_in_australia=True,
        declarations_accepted_at=datetime.now(timezone.utc),
        data_processing_ack_at=datetime.now(timezone.utc),
    )
    db.session.add(org)
    db.session.flush()
    return org


def _create_user(org_id: int, email: str) -> User:
    user = User(
        email=email,
        email_verified=True,
        is_active=True,
        organization_id=org_id,
    )
    user.set_password("Passw0rd1")
    db.session.add(user)
    db.session.flush()
    return user


def _create_global_ndis_framework() -> ComplianceFrameworkVersion:
    """Create a minimal global NDIS framework with test requirements."""
    framework = ComplianceFrameworkVersion(
        organization_id=None,  # Global
        scheme='NDIS',
        jurisdiction='AU',
        version_label='v1.0',
        is_active=True,
    )
    db.session.add(framework)
    db.session.flush()
    
    # Add a few test requirements
    for i in range(1, 4):
        req = ComplianceRequirement(
            framework_version_id=framework.id,
            requirement_id=f"REQ-TEST-{i}",
            module_name="Test Module",
            standard_name=f"Test Standard {i}",
            quality_indicator_text=f"Test QI {i}",
        )
        db.session.add(req)
    
    db.session.flush()
    return framework


def test_get_global_ndis_framework(app):
    """Test retrieving the global NDIS framework."""
    with app.app_context():
        # Should return None initially
        result = compliance_setup_service.get_global_ndis_framework()
        assert result is None
        
        # Create a global framework
        fw = _create_global_ndis_framework()
        db.session.commit()
        
        # Should now find it
        result = compliance_setup_service.get_global_ndis_framework()
        assert result is not None
        assert result.id == fw.id
        assert result.organization_id is None
        assert result.scheme == 'NDIS'


def test_create_org_assessments_from_global_framework(app):
    """Test creating assessment records for an org from global framework."""
    with app.app_context():
        # Setup
        org = _create_org("Test Org")
        user = _create_user(org.id, "admin@test.com")
        global_fw = _create_global_ndis_framework()
        db.session.commit()
        
        # Get requirement count from global framework
        global_req_count = (
            ComplianceRequirement.query
            .filter_by(framework_version_id=global_fw.id)
            .count()
        )
        assert global_req_count == 3
        
        # Create assessments
        created = compliance_setup_service.create_org_assessments_from_global_framework(
            org_id=org.id,
            user_id=user.id,
        )
        
        # Verify
        assert created == 3
        
        assessments = (
            OrganizationRequirementAssessment.query
            .filter_by(organization_id=org.id)
            .all()
        )
        assert len(assessments) == 3
        
        # Verify all assessments point to global requirements
        for assessment in assessments:
            assert assessment.organization_id == org.id
            assert assessment.evidence_status_system == 'Not assessed'
            assert assessment.requirement.framework_version_id == global_fw.id


def test_create_org_assessments_idempotent(app):
    """Test that creating assessments twice doesn't create duplicates."""
    with app.app_context():
        # Setup
        org = _create_org("Test Org Idempotent")
        user = _create_user(org.id, "admin-idempotent@test.com")
        global_fw = _create_global_ndis_framework()
        db.session.commit()
        
        # Create assessments first time
        created1 = compliance_setup_service.create_org_assessments_from_global_framework(
            org_id=org.id,
            user_id=user.id,
        )
        assert created1 == 3
        
        # Create assessments second time (should create 0)
        created2 = compliance_setup_service.create_org_assessments_from_global_framework(
            org_id=org.id,
            user_id=user.id,
        )
        assert created2 == 0
        
        # Verify total count is still 3
        assessments = (
            OrganizationRequirementAssessment.query
            .filter_by(organization_id=org.id)
            .all()
        )
        assert len(assessments) == 3


def test_create_org_assessments_without_global_framework_raises_error(app):
    """Test that creating assessments without global framework raises error."""
    with app.app_context():
        org = _create_org("Test Org No Framework")
        
        # Should raise ComplianceSetupError
        with pytest.raises(ComplianceSetupError, match="Global NDIS framework not found"):
            compliance_setup_service.create_org_assessments_from_global_framework(
                org_id=org.id,
                user_id=None,
            )


def test_multi_org_isolation(app):
    """Test that assessments are properly isolated between organizations."""
    with app.app_context():
        # Setup
        org1 = _create_org("Org 1 Isolation")
        org2 = _create_org("Org 2 Isolation")
        user1 = _create_user(org1.id, "user1@test.com")
        user2 = _create_user(org2.id, "user2@test.com")
        global_fw = _create_global_ndis_framework()
        db.session.commit()
        
        # Create assessments for both orgs
        created1 = compliance_setup_service.create_org_assessments_from_global_framework(
            org_id=org1.id,
            user_id=user1.id,
        )
        created2 = compliance_setup_service.create_org_assessments_from_global_framework(
            org_id=org2.id,
            user_id=user2.id,
        )
        
        assert created1 == 3
        assert created2 == 3
        
        # Verify org1 sees only their assessments
        org1_assessments = (
            OrganizationRequirementAssessment.query
            .filter_by(organization_id=org1.id)
            .all()
        )
        assert len(org1_assessments) == 3
        for a in org1_assessments:
            assert a.organization_id == org1.id
        
        # Verify org2 sees only their assessments
        org2_assessments = (
            OrganizationRequirementAssessment.query
            .filter_by(organization_id=org2.id)
            .all()
        )
        assert len(org2_assessments) == 3
        for a in org2_assessments:
            assert a.organization_id == org2.id
        
        # Verify they're truly separate (no cross-org leakage)
        org1_ids = {a.id for a in org1_assessments}
        org2_ids = {a.id for a in org2_assessments}
        assert org1_ids.isdisjoint(org2_ids)
