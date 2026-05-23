import sys
import os

# Add the parent directory to sys.path so we can import 'app'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models import User, Organization
from app.services.walkthrough_service import walkthrough_service

def backfill_walkthroughs(org_id=None, walkthrough_key='getting-started'):
    """
    Force create a walkthrough state for existing users so they see the launcher card.
    By default, old users (> 7 days) are not eligible for 'getting-started' automatically.
    This script bypasses eligibility and creates the state directly.
    """
    app = create_app()
    with app.app_context():
        # Query users, optionally filtering by organization
        query = User.query
        if org_id:
            query = query.filter_by(organization_id=org_id)
        
        users = query.all()
        print(f"Found {len(users)} users to process.")
        
        count = 0
        for user in users:
            # Only process users who have an organization
            if not user.organization_id:
                continue
                
            # Create or get state
            state = walkthrough_service.get_or_create_state(
                org_id=user.organization_id,
                user_id=user.id,
                walkthrough_key=walkthrough_key,
                auto_triggered=True
            )
            
            # If the state was already completed or dismissed, skip modifying it
            if state.state in ['completed', 'dismissed'] or state.permanently_dismissed:
                continue
                
            # Force it to be eligible so it shows up in the dashboard
            if not state.eligible:
                state.eligible = True
                db.session.commit()
            
            count += 1
            print(f"Processed User {user.id} ({user.email}) for '{walkthrough_key}'.")
            
        print(f"\nSuccessfully backfilled {count} users.")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Backfill walkthroughs for existing users.')
    parser.add_argument('--org', type=int, help='Optional: restrict to a specific Organization ID')
    parser.add_argument('--key', type=str, default='getting-started', help='Walkthrough key (default: getting-started)')
    
    args = parser.parse_args()
    backfill_walkthroughs(org_id=args.org, walkthrough_key=args.key)
