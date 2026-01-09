#!/usr/bin/env python3
"""
Run script for the Compliance Document Management System.
This script starts the Flask development server.
"""

from app import create_app
import os

# Create the Flask application
app = create_app(os.getenv('FLASK_CONFIG') or 'development')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8080'))
    debug = bool(app.config.get('DEBUG', False))

    print("🚀 Starting Cenaris Compliance Management System...")
    print(f"📊 Dashboard will be available at: http://localhost:{port}")
    print("🔐 Create an account or use sample users:")
    print("   • admin@compliance.com / admin123")
    print("   • user@compliance.com / user123")
    print("\n✅ Azure Storage is configured and ready!")
    print("   Files will be stored in: cenarisblobstorage/user-uploads")
    print("\n🛑 Press Ctrl+C to stop the server\n")
    
    app.run(
        host='0.0.0.0',  # Allow external connections
        port=port,
        debug=debug,
        use_reloader=debug,
        threaded=True,
    )