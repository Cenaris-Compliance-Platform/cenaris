#!/usr/bin/env python
"""Initialize global NDIS framework and org assessments."""
import csv
from datetime import datetime, timezone
from app import create_app, db
from app.models import (
    ComplianceFrameworkVersion,
    ComplianceRequirement,
    Organization,
    OrganizationRequirementAssessment,
)

app = create_app('development')

def main():
    with app.app_context():
        print("\n=== Global NDIS Framework Bootstrap ===\n")
        
        # Check/create global framework
        fw = ComplianceFrameworkVersion.query.filter_by(
            organization_id=None, scheme='NDIS'
        ).first()
        
        if fw:
            print(f"✓ Global framework exists (ID: {fw.id})")
            req_count = fw.requirements.count()
            print(f"  Requirements: {req_count}")
        else:
            print("→ Creating global framework...")
            fw = ComplianceFrameworkVersion(
                organization_id=None,
                scheme='NDIS',
                jurisdiction='AU',
                version_label='v1.0',
                is_active=True,
                imported_at=datetime.now(timezone.utc),
            )
            db.session.add(fw)
            db.session.flush()
            
            # Read and import requirements from CSV
            csv_path = 'data/sources/ndis/mapping/MASTER Cenaris_NDIS_Audit_Master_Mapping_v1.csv'
            try:
                with open(csv_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    count = 0
                    for i, row in enumerate(reader, 1):
                        req_id = (row.get('requirement_id') or '').strip() or f'ROW-{i}'
                        req = ComplianceRequirement(
                            framework_version_id=fw.id,
                            requirement_id=req_id,
                            module_name=(row.get('module_name') or '').strip() or None,
                            standard_name=(row.get('standard_name') or '').strip() or None,
                        )
                        db.session.add(req)
                        count += 1
                        if i % 100 == 0:
                            print(f"  Imported {count} requirements...")
                
                db.session.commit()
                print(f"✓ Global framework created with {count} requirements\n")
            except FileNotFoundError:
                print(f"✗ CSV not found: {csv_path}\n")
                return False
        
        # Create assessments for all orgs
        print("→ Creating assessment records...\n")
        orgs = Organization.query.filter(Organization.id > 0).all()
        
        for org in orgs:
            existing = OrganizationRequirementAssessment.query.filter_by(
                organization_id=org.id
            ).count()
            
            if existing > 0:
                print(f"  Org {org.id:3d} ({org.name[:30]:30s}): {existing:5d} assessments exist")
            else:
                # Create assessments
                reqs = ComplianceRequirement.query.filter_by(
                    framework_version_id=fw.id
                ).all()
                
                for req in reqs:
                    a = OrganizationRequirementAssessment(
                        organization_id=org.id,
                        requirement_id=req.id,
                        evidence_status_system='Not assessed',
                        evidence_status_implementation='Not assessed',
                        evidence_status_workforce='Not assessed',
                        evidence_status_participant='Not assessed',
                    )
                    db.session.add(a)
                
                db.session.commit()
                print(f"  Org {org.id:3d} ({org.name[:30]:30s}): Created {len(reqs):5d} assessments")
        
        print("\n✓ Bootstrap complete!\n")
        return True

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n✗ Error: {e}\n")
        import traceback
        traceback.print_exc()
