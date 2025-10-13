#!/usr/bin/env python3
"""
Run script for the Compliance Document Management System.
This script starts the Flask development server.
"""

from app import create_app
from app.database import init_database, check_database_exists
import os

# Create the Flask application
app = create_app(os.getenv('FLASK_CONFIG') or 'development')

# Initialize database if it doesn't exist
with app.app_context():
    if not check_database_exists():
        print("Database not found. Initializing...")
        init_database()
        print("Database initialized successfully!")

if __name__ == '__main__':
    print("🚀 Starting Cenaris Compliance Management System...")
    print("📊 Dashboard will be available at: http://127.0.0.1:8080")
    print("🔐 Create an account or use sample users:")
    print("   • admin@compliance.com / admin123")
    print("   • user@compliance.com / user123")
    print("\n✅ Azure Storage is configured and ready!")
    print("   Files will be stored in: cenarisblobstorage/user-uploads")
    print("\n🛑 Press Ctrl+C to stop the server\n")
    
    app.run(
        host='0.0.0.0',  # Allow external connections
        port=8081,
        debug=True,
        use_reloader=True
    )