#!/usr/bin/env python3
"""
Database initialization script for the Compliance Document Management System.
Run this script to set up the database with required tables and sample data.
"""

import os
import sys
from app import create_app
from app import db

def main():
    """Main function to initialize the database."""
    print("Initializing Compliance Document Management System Database...")
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        try:
            db.drop_all()
            db.create_all()
            
            print("\n✅ Database initialization completed successfully!")
            print("\nYou can now run the application with: python app.py")
            print("\nTip: prefer migrations via `flask db migrate` + `flask db upgrade`.")
            
        except Exception as e:
            print(f"\n❌ Error during database initialization: {e}")
            sys.exit(1)

if __name__ == '__main__':
    main()