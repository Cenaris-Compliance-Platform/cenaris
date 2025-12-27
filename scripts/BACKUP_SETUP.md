# Database Backup Setup

## Automated Daily Backups

### Prerequisites
- PostgreSQL client tools (for pg_dump): `apt install postgresql-client` or `brew install postgresql`
- Azure Storage Blob library: Already in requirements.txt

### Environment Variables
Add to `.env`:
```bash
AZURE_BACKUP_CONTAINER_NAME=database-backups  # Optional, defaults to 'database-backups'
```

### Windows Task Scheduler Setup

1. **Open Task Scheduler** → Create Basic Task
2. **Name**: "Cenaris Database Backup"
3. **Trigger**: Daily at 2:00 AM
4. **Action**: Start a program
   - Program: `C:\Users\DELL\AppData\Local\Programs\Python\Python312\python.exe`
   - Arguments: `C:\Users\DELL\Desktop\cenaris\scripts\backup_database.py`
   - Start in: `C:\Users\DELL\Desktop\cenaris`
5. **Settings**: 
   - ☑ Run whether user is logged on or not
   - ☑ Run with highest privileges

### Linux/Mac Cron Setup

Add to crontab (`crontab -e`):
```bash
# Run daily at 2:00 AM
0 2 * * * cd /path/to/cenaris && /usr/bin/python3 scripts/backup_database.py >> logs/backup.log 2>&1
```

### Manual Backup

Run anytime:
```bash
python scripts/backup_database.py
```

### Backup Storage

- **Local**: `backups/` directory (kept for 7 days)
- **Azure**: `database-backups` container in Azure Blob Storage
- **Format**: 
  - PostgreSQL: `.dump` (compressed custom format)
  - SQLite: `.db` (file copy)

### Restore from Backup

**PostgreSQL**:
```bash
pg_restore -h hostname -U username -d database_name backup_postgres_20250127_020000.dump
```

**SQLite**:
```bash
cp backup_sqlite_20250127_020000.db instance/compliance.db
```

### Monitoring

Check logs:
- Task Scheduler: Right-click task → Properties → History
- Cron: Check `logs/backup.log`
- Azure Portal: Navigate to storage account → Containers → database-backups
