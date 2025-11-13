# Data Not Updating from ADLS - Troubleshooting Guide

## Quick Fixes

### 1. Click the "Refresh Data" Button
I just added a **"Refresh Data"** button to the Gap Analysis page (top right).
- Click it to force reload the page and fetch fresh data from ADLS

### 2. Hard Refresh Your Browser
- **Windows/Linux:** `Ctrl + Shift + R`
- **Mac:** `Cmd + Shift + R`
- This clears browser cache and forces fresh data

### 3. Check What's Actually in ADLS Right Now

Visit this debug endpoint:
```
http://localhost:5000/debug-adls
```

This shows:
- ✅ Connection status
- ✅ Files found in ADLS
- ✅ Raw framework data
- ✅ Scores and statuses
- ✅ Timestamp of when data was fetched

**Look for:** `raw_frameworks` section - this shows exactly what's in your ADLS file RIGHT NOW

## Verify Your ADLS File

### Check in Azure Portal:
1. Go to Storage Account: `cenarisblobstorage`
2. Navigate to Container: `processed-doc-intel` (or `results`)
3. Go to: `compliance-results/2025/11/user_1/compliance_summary.csv`
4. Click "Edit" to see the contents
5. Verify your new scores are there

### Expected Format:
```csv
Framework,Compliance_Score,Status
Aged Care,7.50,Complete
NDIS,8.20,Complete
Overall,7.85,
```

## Common Issues

### Issue 1: File Not Updated in ADLS
**Check:** Did you actually upload the new file to ADLS?
- File must be at: `compliance-results/2025/11/user_1/compliance_summary.csv`
- Old file might still be there

**Solution:** Re-upload the file to ADLS

### Issue 2: Wrong User ID
**Check:** Are you logged in as user_1?
- The path includes `user_1` folder
- If you're user_2, it looks in `user_2` folder

**Solution:** Check your user ID at `/debug-adls` endpoint

### Issue 3: Browser Cache
**Check:** Browser might be showing cached data

**Solution:** 
- Click "Refresh Data" button
- Or hard refresh: `Ctrl+Shift+R`

### Issue 4: Flask Not Restarted
**Check:** Did you restart Flask after updating ADLS?

**Solution:** You don't need to restart Flask - data is fetched fresh each time. But if you changed code, restart Flask.

## How to Force Fresh Data

### Method 1: Use Debug Endpoint
```
http://localhost:5000/debug-adls
```
This fetches data fresh from ADLS and shows you exactly what it found.

### Method 2: Check Flask Console
When you visit Gap Analysis page, check Flask console for:
```
GAP ANALYSIS - Starting data fetch
Connection Status: Connected - Files Found
Total Files: 1
File Summaries: 1

Processing 1 file summaries...
  File: compliance_summary.csv
  Frameworks: [{'name': 'Aged Care', 'score': 7.50, 'status': 'Complete'}, ...]
```

This shows the actual data being read from ADLS.

### Method 3: Add Timestamp Check
I added a timestamp to the Gap Analysis page showing when data was last fetched.
Look for: "Last updated: Nov 13, 2025 2:30 PM"

## Test Sequence

1. **Update your CSV in ADLS** with new scores
2. **Visit debug endpoint:** `http://localhost:5000/debug-adls`
3. **Check `raw_frameworks`** - do you see new scores?
4. **If YES:** Click "Refresh Data" on Gap Analysis page
5. **If NO:** File not updated in ADLS correctly

## Expected Behavior

When you update the CSV in ADLS:
1. ✅ New scores should appear immediately (no restart needed)
2. ✅ Gap Analysis page shows new data on refresh
3. ✅ Reports include new scores
4. ✅ Progress bars update automatically

## Still Not Working?

### Check These:

1. **File Path Correct?**
   ```
   Container: processed-doc-intel
   Path: compliance-results/2025/11/user_1/compliance_summary.csv
   ```

2. **File Format Correct?**
   - Must be CSV
   - Must have headers: Framework,Compliance_Score,Status
   - No extra spaces in column names

3. **Connection Working?**
   - Visit `/debug-adls`
   - Check `connection_status`
   - Should say "Connected - Files Found"

4. **User ID Matches?**
   - Check `user_id` in `/debug-adls`
   - Path must include correct user folder

## Quick Test

1. Visit: `http://localhost:5000/debug-adls`
2. Copy the output
3. Look for `raw_frameworks` section
4. Check if scores match your updated CSV
5. If YES → Click "Refresh Data" button
6. If NO → File not uploaded correctly to ADLS

Share the `/debug-adls` output if you need help debugging!
