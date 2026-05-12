"""
Quick bootstrap script for global NDIS framework.
Bypasses pandas compatibility issues.
"""
import csv
from datetime import datetime, timezone
from app import create_app, db
from app.models import ComplianceFrameworkVersion, ComplianceRequirement

app = create_app('development')

def bootstrap_global_framework():
    with app.app_context():
        # Check if global framework already exists
        existing = ComplianceFrameworkVersion.query.filter_by(
            organization_id=None,
            scheme='NDIS',
        ).first()
        
        if existing:
            print(f"✓ Global framework already exists (ID: {existing.id})")
            req_count = existing.requirements.count()
            print(f"  Requirements: {req_count}")
            return
        
        # Create global framework
        framework = ComplianceFrameworkVersion(
            organization_id=None,  # Global
            scheme='NDIS',
            jurisdiction='AU',
            version_label='v1.0',
            source_authority='NDIS Commission',
            source_document='NDIS Practice Standards',
            is_active=True,
            imported_at=datetime.now(timezone.utc),
        )
        db.session.add(framework)
        db.session.flush()
        
        # Read CSV and create requirements
        csv_path = 'data/sources/ndis/mapping/MASTER Cenaris_NDIS_Audit_Master_Mapping_v1.csv'
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                count = 0
                for row in reader:
                    # Normalize header keys (lowercase, underscores)
                    normalized_row = {k.lower().replace(' ', '_'): v for k, v in row.items()}
                    
                    req_id = (normalized_row.get('requirement_id') or '').strip()
                    if not req_id:
                        req_id = f"ROW-{count+1}"
                    
                    req = ComplianceRequirement(
                        framework_version_id=framework.id,
                        requirement_id=req_id,
                        module_type=(normalized_row.get('module_type') or '').strip() or None,
                        module_name=(normalized_row.get('module_name') or '').strip() or None,
                        standard_name=(normalized_row.get('standard_name') or '').strip() or None,
                        outcome_code=(normalized_row.get('outcome_code') or '').strip() or None,
                        outcome_text=(normalized_row.get('outcome_text') or '').strip() or None,
                        quality_indicator_code=(normalized_row.get('quality_indicator_code') or '').strip() or None,
                        quality_indicator_text=(normalized_row.get('quality_indicator_text') or '').strip() or None,
                    )
                    db.session.add(req)
                    count += 1
                
                db.session.commit()
                print(f"✓ Global framework created (ID: {framework.id})")
                print(f"  Requirements imported: {count}")
        
        except FileNotFoundError:
            print(f"✗ CSV file not found: {csv_path}")
            db.session.rollback()
            return False
        except Exception as e:
            print(f"✗ Error: {e}")
            db.session.rollback()
            return False
        
        return True

if __name__ == '__main__':
    bootstrap_global_framework()
