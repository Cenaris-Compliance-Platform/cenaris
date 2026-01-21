#!/usr/bin/env python3
"""Fix organization spelling from American to Australian English."""

from app import create_app, db
from app.models import Organization

def main():
    app = create_app()
    
    with app.app_context():
        # Update all organizations that have "Organization" in the name
        orgs = Organization.query.all()
        
        updated = 0
        for org in orgs:
            if org.name and 'Organization' in org.name:
                old_name = org.name
                org.name = org.name.replace('Organization', 'Organisation')
                print(f"✓ Updated: '{old_name}' → '{org.name}'")
                updated += 1
        
        if updated > 0:
            db.session.commit()
            print(f"\n✅ Updated {updated} organisation(s)")
        else:
            print("No organisations found with 'Organization' in the name")

if __name__ == '__main__':
    main()
