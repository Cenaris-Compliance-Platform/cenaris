#!/usr/bin/env python3
"""
Automated database backup script for Cenaris.

This script creates daily backups of the database and uploads them to Azure Blob Storage.
Can be scheduled using cron (Linux) or Task Scheduler (Windows).

Usage:
    python scripts/backup_database.py

Environment Variables Required:
    - DATABASE_URL or DEV_DATABASE_URL
    - AZURE_STORAGE_CONNECTION_STRING
    - AZURE_CONTAINER_NAME (optional, defaults to 'database-backups')
"""

import os
import sys
import subprocess
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote
from dotenv import load_dotenv

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# The Azure SDK can be very verbose (HTTP request/response logging).
# Default it to WARNING so backup runs are readable.
logging.getLogger('azure').setLevel(logging.WARNING)
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)


def get_database_url():
    """Get the database URL from environment."""
    db_url = os.environ.get('DEV_DATABASE_URL') or os.environ.get('DATABASE_URL')
    if not db_url:
        raise ValueError("No DATABASE_URL or DEV_DATABASE_URL found in environment")
    return db_url


def parse_postgres_url(url: str) -> dict:
    """Parse PostgreSQL connection URL into components.

    Uses urllib parsing so URL-encoded passwords like `%40` become `@`.
    Also extracts sslmode so pg_dump uses TLS for Azure.
    """
    if not url.startswith(('postgresql://', 'postgres://')):
        raise ValueError(f"Not a PostgreSQL URL: {url}")

    parsed = urlparse(url)
    if not parsed.hostname or not parsed.path:
        raise ValueError("Invalid PostgreSQL URL format")

    username = unquote(parsed.username or '')
    password = unquote(parsed.password or '')
    database = (parsed.path or '').lstrip('/')
    port = str(parsed.port or 5432)

    qs = parse_qs(parsed.query or '')
    sslmode = (qs.get('sslmode', [None])[0] or '').strip() or None

    return {
        'host': parsed.hostname,
        'port': port,
        'username': username,
        'password': password,
        'database': database,
        'sslmode': sslmode,
    }


def backup_postgresql(db_config, backup_path):
    """Create a PostgreSQL backup using pg_dump."""
    logger.info(f"Creating PostgreSQL backup: {backup_path}")
    
    env = os.environ.copy()
    env['PGPASSWORD'] = db_config.get('password', '')
    # Azure Database for PostgreSQL requires TLS; mirror `?sslmode=require`.
    env['PGSSLMODE'] = (db_config.get('sslmode') or env.get('PGSSLMODE') or 'require')
    
    cmd = [
        'pg_dump',
        '-h', db_config['host'],
        '-p', db_config['port'],
        '-U', db_config['username'],
        '-d', db_config['database'],
        '-F', 'c',  # Custom format (compressed)
        '-f', str(backup_path),
        '--no-owner',  # Don't include ownership commands
        '--no-acl',    # Don't include ACL commands
    ]
    
    try:
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"PostgreSQL backup created successfully: {backup_path}")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"pg_dump failed: {e.stderr}")
        return False
    except FileNotFoundError:
        logger.error("pg_dump not found. Please install PostgreSQL client tools.")
        return False


def backup_sqlite(db_url, backup_path):
    """Create a SQLite backup by copying the database file."""
    import shutil
    
    # Extract database file path from URL
    # Format: sqlite:///path/to/db.db
    db_path = db_url.replace('sqlite:///', '')
    
    # Resolve relative paths
    if not os.path.isabs(db_path):
        # Relative to instance folder
        from flask import Flask
        temp_app = Flask(__name__)
        db_path = os.path.join(temp_app.instance_path, db_path)
    
    if not os.path.exists(db_path):
        logger.error(f"SQLite database not found: {db_path}")
        return False
    
    logger.info(f"Creating SQLite backup: {backup_path}")
    try:
        shutil.copy2(db_path, backup_path)
        logger.info(f"SQLite backup created successfully: {backup_path}")
        return True
    except Exception as e:
        logger.error(f"SQLite backup failed: {e}")
        return False


def upload_to_azure(backup_path, blob_name):
    """Upload backup file to Azure Blob Storage."""
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError:
        logger.error("azure-storage-blob not installed. Run: pip install azure-storage-blob")
        return False
    
    connection_string = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    if not connection_string:
        logger.error("AZURE_STORAGE_CONNECTION_STRING not set")
        return False
    
    container_name = os.environ.get('AZURE_BACKUP_CONTAINER_NAME', 'database-backups')
    
    try:
        logger.info(f"Uploading backup to Azure: {container_name}/{blob_name}")
        
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        
        # Create container if it doesn't exist
        try:
            container_client = blob_service_client.get_container_client(container_name)
            container_client.get_container_properties()
        except Exception:
            logger.info(f"Creating container: {container_name}")
            blob_service_client.create_container(container_name)
        
        # Upload file
        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )
        
        with open(backup_path, 'rb') as data:
            blob_client.upload_blob(data, overwrite=True)
        
        logger.info(f"Backup uploaded successfully: {blob_name}")
        return True
        
    except Exception as e:
        logger.error(f"Azure upload failed: {e}")
        return False


def cleanup_old_backups(backup_dir, keep_days=7):
    """Delete local backups older than keep_days."""
    if not backup_dir.exists():
        return
    
    cutoff = datetime.now(timezone.utc).timestamp() - (keep_days * 24 * 60 * 60)
    
    for backup_file in backup_dir.glob('backup_*'):
        if backup_file.stat().st_mtime < cutoff:
            logger.info(f"Removing old backup: {backup_file.name}")
            backup_file.unlink()


def main():
    """Main backup function."""
    try:
        # Create backups directory
        backup_dir = Path(__file__).parent.parent / 'backups'
        backup_dir.mkdir(exist_ok=True)
        
        # Generate backup filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        
        # Get database URL
        db_url = get_database_url()
        
        # Determine database type and create backup
        if db_url.startswith(('postgresql://', 'postgres://')):
            backup_filename = f'backup_postgres_{timestamp}.dump'
            backup_path = backup_dir / backup_filename
            
            db_config = parse_postgres_url(db_url)
            success = backup_postgresql(db_config, backup_path)
            
        elif db_url.startswith('sqlite:///'):
            backup_filename = f'backup_sqlite_{timestamp}.db'
            backup_path = backup_dir / backup_filename
            
            success = backup_sqlite(db_url, backup_path)
            
        else:
            logger.error(f"Unsupported database type: {db_url}")
            return 1
        
        if not success:
            logger.error("Backup creation failed")
            return 1
        
        # Upload to Azure Blob Storage
        blob_name = f'cenaris/{backup_filename}'
        if not upload_to_azure(backup_path, blob_name):
            logger.warning("Azure upload failed, but local backup created")
        
        # Cleanup old local backups
        cleanup_old_backups(backup_dir, keep_days=7)
        
        logger.info("Backup process completed successfully")
        return 0
        
    except Exception as e:
        logger.exception(f"Backup failed with error: {e}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
