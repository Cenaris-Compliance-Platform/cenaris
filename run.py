#!/usr/bin/env python3
"""
Run script for the Compliance Document Management System.
This script starts the Flask development server.
"""

from app import create_app
import os
import logging

# Create the Flask application
app = create_app(os.getenv('FLASK_CONFIG') or 'development')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', '8080'))
    debug = bool(app.config.get('DEBUG', False))
    logger = logging.getLogger('startup')

    logger.info('Starting Cenaris Compliance Management System')
    logger.info(f'Dashboard URL: http://localhost:{port}')
    logger.info('Sample users: admin@compliance.com / admin123, user@compliance.com / user123')
    logger.info('Azure Storage target: cenarisblobstorage/user-uploads')
    logger.info('Press Ctrl+C to stop the server')
    
    app.run(
        host='0.0.0.0',  # Allow external connections
        port=port,
        debug=debug,
        use_reloader=debug,
        threaded=True,
    )