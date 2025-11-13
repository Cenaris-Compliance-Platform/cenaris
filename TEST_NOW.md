# Test Now - See What's Happening

## What I Added

1. **Print statements** - You'll see detailed output in your Flask console
2. **Fallback data** - If ADLS doesn't work, you'll see sample data (Aged Care 53%, NDIS 30%)

## Steps to Test

### 1. Restart Flask App

```bash
# Stop your Flask app (Ctrl+C)
# Start it again
python run.py
```

### 2. Visit Gap Analysis Page

Open in browser:
```
http://localhost:5000/gap-analysis
```

### 3. Check Your Flask Console

You should see output like this:

```
============================================================
GAP ANALYSIS - Starting data fetch
============================================================
Connection Status: Connected - Files Found
Total Files: 1
File Summaries: 1

Processing 1 file summaries...
  File: compliance_summary.csv
  Frameworks: [{'name': 'Aged Care', 'score': 5.35, 'status': 'Missing'}, {'name': 'NDIS', 'score': 3.03, 'status': 'Missing'}]
    Adding: Aged Care - 53% - Missing
    Adding: NDIS - 30% - Missing

Total gap_data items: 2
```

## What You'll See

### If ADLS Works:
- Your real data from compliance_summary.csv
- Aged Care: 53.5%
- NDIS: 30.3%

### If ADLS Doesn't Work:
- Sample fallback data (same values)
- Console will show: "No data from ADLS - using sample data"

## Troubleshooting

### Console shows "No file summaries found!"

**Problem:** ADLS connection or file not found

**Check:**
1. Is connection string correct in `.env`?
2. Did you restart Flask after changing `.env`?
3. Is your file at: `processed-doc-intel/compliance-results/2025/11/user_1/compliance_summary.csv`?

**Quick Fix:** The fallback data will show anyway, so you can see the UI working

### Console shows "Connection Status: Not Connected to ADLS"

**Problem:** Azure SDK or connection string issue

**Fix:**
```bash
pip install azure-storage-file-datalake
```

And make sure `.env` has:
```
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=cenarisblobstorage;AccountKey=YOUR_KEY;EndpointSuffix=core.windows.net
```

### Console shows "Connection Status: Connected - No Files Found"

**Problem:** File path doesn't match

**Your file location in Azure:**
- Container: ?
- Path: ?

**Code expects:**
- Container: `processed-doc-intel` (from .env)
- Path: `compliance-results/2025/11/user_1/compliance_summary.csv`

**To fix:** Update the path in Azure or change the code to match your actual path

## Debug Endpoint

Visit this to see raw data:
```
http://localhost:5000/debug-adls
```

This shows:
- Connection status
- Files found
- Raw summary data

## Copy Console Output

When you visit the Gap Analysis page, **copy the console output** and share it with me. It will show exactly what's happening!

## Expected Result

Either way (ADLS working or fallback), you should now see:

**Progress by Framework:**
- Aged Care: 53% progress bar (red, Missing)
- NDIS: 30% progress bar (red, Missing)

**Summary Stats:**
- Total: 2
- Missing: 2
- Compliance: 41%

**Table:**
- Row 1: Aged Care | Missing | 53%
- Row 2: NDIS | Missing | 30%

If you still see empty page, share the console output!
