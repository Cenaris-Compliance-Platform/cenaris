from datetime import datetime, timedelta, timezone
import os, sys
# Ensure project root is on sys.path when invoked from scripts/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app import create_app, db
from app.models import User, Organization, OrganizationRequirementAssessment
from app.services.walkthrough_service import walkthrough_service

app = create_app()

with app.app_context():
    now = datetime.now(timezone.utc)
    cutoff_user = now - timedelta(days=7)
    recent_users = User.query.filter(User.created_at >= cutoff_user).limit(50).all()
    print(f"Recent users (<7d): {len(recent_users)}")
    for u in recent_users[:20]:
        print(f" - id={u.id}, email={getattr(u, 'email', None)}, created_at={u.created_at}")

    cutoff_org = now - timedelta(days=30)
    orgs = Organization.query.filter(Organization.created_at <= cutoff_org).limit(200).all()
    low = []
    for o in orgs:
        assessments = OrganizationRequirementAssessment.query.filter_by(organization_id=o.id).all()
        total = len(assessments)
        with_evidence = sum(1 for a in assessments if getattr(a, 'has_evidence', False))
        pct = (with_evidence / total * 100) if total else 0.0
        if pct < 30.0:
            low.append((o.id, o.name, pct, o.created_at, total))
    print(f"Orgs older than 30d with coverage <30%: {len(low)}")
    for o in low[:20]:
        print(f" - id={o[0]}, name={o[1]}, coverage={o[2]:.1f}%, created_at={o[3]}, assessments={o[4]}")

    # Show eligible walkthroughs for first 20 users
    users = User.query.limit(50).all()
    print('\nSample user eligibility:')
    for u in users[:20]:
        # Try to find an org for the user
        org = getattr(u, 'organization_id', None)
        try:
            eligible = walkthrough_service.get_eligible_walkthroughs_for_user(org_id=int(org) if org else None, user_id=u.id)
        except Exception as e:
            eligible = f'error: {e}'
        print(f"user id={u.id}, email={getattr(u,'email',None)}, org_id={org}, eligible_count={len(eligible) if isinstance(eligible, list) else eligible}")

    print('\nDone')
