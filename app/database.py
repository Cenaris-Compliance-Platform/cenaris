from sqlalchemy import inspect

from app import db
from app.models import User

def init_database():
    """Initialize the database with required tables (SQLAlchemy)."""
    db.create_all()
    print("Database initialized successfully!")

def check_database_exists():
    """Check if database has required tables (SQLAlchemy)."""
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    return {'organizations', 'users', 'documents'}.issubset(tables)

def create_sample_data():
    """Create sample data for development/testing."""
    try:
        admin_email = 'admin@compliance.com'
        user_email = 'user@compliance.com'

        if not User.query.filter_by(email=admin_email).first():
            admin_user = User(email=admin_email, email_verified=True)
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            print("Sample admin user created: admin@compliance.com / admin123")
        else:
            print("Admin user already exists")

        if not User.query.filter_by(email=user_email).first():
            user = User(email=user_email, email_verified=True)
            user.set_password('user123')
            db.session.add(user)
            print("Sample user created: user@compliance.com / user123")
        else:
            print("Regular user already exists")

        db.session.commit()
            
    except Exception as e:
        db.session.rollback()
        print(f"Error creating sample data: {e}")

def reset_database():
    """Reset database by dropping and recreating all tables."""
    try:
        db.drop_all()
        db.create_all()
        print("Database reset successfully!")

    except Exception as e:
        db.session.rollback()
        print(f"Error resetting database: {e}")
        raise