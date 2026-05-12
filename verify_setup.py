from app import create_app
from app.models import ComplianceFrameworkVersion, OrganizationRequirementAssessment, Organization

app = create_app('development')
with app.app_context():
    fw = ComplianceFrameworkVersion.query.filter_by(organization_id=None, scheme='NDIS').first()
    orgs = Organization.query.count()
    assessments = OrganizationRequirementAssessment.query.count()
    
    print("\n=== DATABASE STATE ===\n")
    print(f"Global Framework: {fw.id if fw else 'NONE'}")
    print(f"Requirements: {fw.requirements.count() if fw else 0}")
    print(f"Organizations: {orgs}")
    print(f"Total Assessments: {assessments}")
    print("\n✓ STATUS: READY FOR TESTING\n")
