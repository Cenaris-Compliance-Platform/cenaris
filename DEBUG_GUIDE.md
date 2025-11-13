# Debugging Guide - No Data Showing in Gap Analysis

## Quick Checks

### 1. Visit the Debug Endpoint

Start your Flask app and visit:
```
http://localhost:5000/debug-adls
```

This will show you:
- ✓ Is connection string set?
- ✓ Is service client initialized?
- ✓ How many files were found?
- ✓ What's in the summary?

### 2. Check Flask Logs

When you visit the Gap Analysis page, check your Flask console output for lines like:
```
Gap Analysis - Summary: {...}
Gap Analysis - File summaries count: X
Gap Analysis - Frameworks in compliance_summary.csv: [...]
Gap Analysis - Total gap_data items: X
Gap Analysis - Summary stats: {...}
```

## Common Issues & Solutions

### Issue 1: Connection String Not Set
**Symptom:** `service_client_initialized: false`

**Solution:**
1. Check `.env` file has `AZURE_STORAGE_CONNECTION_STRING`
2. Restart Flask app after adding it
3. Make sure the connection string is valid

### Issue 2: Wrong Container Name
**Symptom:** `files_found: 0` or connection error

**Current config:**
- Container: `results`
- Path: `compliance-results/2025/11/user_1/`

**Check if your actual path is different:**
```python
# In Azure Portal, check:
# Storage Account → Containers → results → Browse
# Look for: compliance-results/2025/11/user_1/compliance_summary.csv
```

**If your path is different, update `app/services/azure_data_service.py`:**
```python
self.container_name = "YOUR_ACTUAL_CONTAINER"  # Line 27
```

### Issue 3: File Not Found
**Symptom:** `files_found: 0`

**Possible reasons:**
1. File is in a different path
2. File doesn't exist yet
3. User ID doesn't match folder structure

**Check your actual file location in Azure:**
- Is it at: `compliance-results/2025/11/user_1/compliance_summary.csv`?
- Or somewhere else like: `compliance-results/compliance_summary.csv`?

**If file is at root of compliance-results:**

Update `get_compliance_files()` in `app/services/azure_data_service.py`:
```python
# Comment out the user-specific path logic (lines 68-73)
search_path = self.results_path  # Just use base path
```

### Issue 4: CSV Format Mismatch
**Symptom:** Files found but no frameworks showing

**Check your CSV has these exact columns:**
```csv
Framework,Compliance_Score,Status
```

**Not:**
- `framework` (lowercase)
- `Compliance Score` (with space)
- `compliance_score` (underscore)

### Issue 5: Empty CSV or Only "Overall" Row
**Symptom:** `total_requirements: 0`

**Your CSV must have framework rows (not just Overall):**
```csv
Framework,Compliance_Score,Status
Aged Care,5.35,Missing
NDIS,3.03,Missing
Overall,3.93,
```

## Step-by-Step Debugging

### Step 1: Verify Azure Connection

```bash
# Run this in your terminal
python3 simple_debug.py
```

This will show:
- All containers in your storage account
- All paths in compliance-results/

### Step 2: Check Actual File Path

In Azure Portal:
1. Go to Storage Account: `cenarisblobstorage`
2. Click "Containers"
3. Find your container (is it `results` or something else?)
4. Navigate to find `compliance_summary.csv`
5. Note the EXACT path

### Step 3: Update Code if Needed

If your path is different, update these lines in `app/services/azure_data_service.py`:

```python
# Line 27 - Container name
self.container_name = "YOUR_CONTAINER_NAME"

# Lines 68-73 - Path logic
# If file is at: compliance-results/compliance_summary.csv (no user folders)
search_path = self.results_path  # Remove user_id logic
```

### Step 4: Test with Hardcoded Path

Temporarily hardcode the path to test:

In `get_compliance_files()`, replace lines 68-73 with:
```python
# Hardcode your exact path for testing
search_path = "compliance-results"  # Or your exact path
```

### Step 5: Check Flask Logs

Start Flask and visit Gap Analysis page. Look for:
```
INFO:app.services.azure_data_service:Found X compliance files in ADLS at ...
INFO:app.services.azure_data_service:Successfully read X rows from ...
INFO:app.main.routes:Gap Analysis - Total gap_data items: X
```

## Quick Fix: Use Mock Data Temporarily

If you need to see the UI working while debugging ADLS, add this to `gap_analysis()` route:

```python
# Temporary mock data for testing UI
if not gap_data:
    gap_data = [
        {
            'requirement_name': 'Aged Care',
            'status': 'Missing',
            'completion_percentage': 53,
            'supporting_evidence': 'compliance_summary.csv',
            'last_updated': datetime.now()
        },
        {
            'requirement_name': 'NDIS',
            'status': 'Missing',
            'completion_percentage': 30,
            'supporting_evidence': 'compliance_summary.csv',
            'last_updated': datetime.now()
        }
    ]
```

## Need Help?

Share the output of:
1. `/debug-adls` endpoint
2. Flask console logs when visiting Gap Analysis
3. Your actual file path in Azure Portal

This will help identify the exact issue!
