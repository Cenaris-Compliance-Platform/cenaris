"""
Create Test Users for Performance Testing

This script creates the test users needed for Locust load testing.
Run this BEFORE running performance tests.

Usage:
    python create_test_users.py
"""

from app import create_app, db
from app.models import User, Organization
from datetime import datetime, timezone

def create_test_users():
    """Create test users for load testing"""
    app = create_app()
    
    with app.app_context():
        print("=" * 50)
        print("Creating Test Users for Performance Testing")
        print("=" * 50)
        
        # Get the first organization (or you can specify one)
        org = Organization.query.first()
        
        if not org:
            print("\n❌ ERROR: No organization found!")
            print("Please create an organization first or run with an existing organization.")
            return
        
        print(f"\n✅ Using Organization: {org.name} (ID: {org.id})")
        
        # Test users to create
        test_users_data = [
            {
                "email": "test1@example.com",
                "password": "TestPassword123!",
                "first_name": "Test",
                "last_name": "User One"
            },
            {
                "email": "test2@example.com",
                "password": "TestPassword123!",
                "first_name": "Test",
                "last_name": "User Two"
            },
            {
                "email": "test3@example.com",
                "password": "TestPassword123!",
                "first_name": "Test",
                "last_name": "User Three"
            }
        ]
        
        created_count = 0
        skipped_count = 0
        
        for user_data in test_users_data:
            # Check if user already exists
            existing_user = User.query.filter_by(email=user_data["email"]).first()
            
            if existing_user:
                print(f"\n⚠️  User {user_data['email']} already exists - skipping")
                skipped_count += 1
                continue
            
            # Create new user
            new_user = User(
                email=user_data["email"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                organization_id=org.id,
                is_active=True,
                email_verified=True,
                role='user'  # Regular user role
            )
            
            # Set password (hashed)
            new_user.set_password(user_data["password"])
            
            # Add to database
            db.session.add(new_user)
            created_count += 1
            
            print(f"\n✅ Created user: {user_data['email']}")
            print(f"   Password: {user_data['password']}")
            print(f"   Organization: {org.name}")
        
        # Commit all changes
        try:
            db.session.commit()
            print("\n" + "=" * 50)
            print(f"✅ SUCCESS: Created {created_count} test users")
            if skipped_count > 0:
                print(f"⚠️  Skipped {skipped_count} existing users")
            print("=" * 50)
            
            print("\n📝 Test User Credentials:")
            print("-" * 50)
            for user_data in test_users_data:
                print(f"Email: {user_data['email']}")
                print(f"Password: {user_data['password']}")
                print("-" * 50)
            
            print("\n🚀 You can now run Locust:")
            print("   locust -f locustfile.py --host=http://localhost:5000")
            print("   Then open: http://localhost:8089")
            
        except Exception as e:
            db.session.rollback()
            print(f"\n❌ ERROR: Failed to create users: {str(e)}")
            return


if __name__ == "__main__":
    create_test_users()
