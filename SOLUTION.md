# Solution - Fixed Container Name Issue

## What Was Wrong

Your `.env` file specified:
```
AZURE_ML_CONTAINER=processed-doc-intel
```

But the code was hardcoded to use:
```python
self.container_name = "results"
```

## What I Fixed

Updated `app/services/azure_data_service.py` to read from environment variables:

```python
self.container_name = os.getenv('AZURE_ML_CONTAINER', 'results')
self.results_path = os.getenv('AZURE_ML_RESULTS_PATH', 'compliance-results')
```

Now it will use:
- Container: `processed-doc-intel` (from your .env)
- Path: `compliance-results` (from your .env)

## Test It Now

1. **Restart your Flask app** (important - to reload .env)
   ```bash
   # Stop the app (Ctrl+C)
   # Start it again
   python run.py
   ```

2. **Visit the debug endpoint:**
   ```
   http://localhost:5000/debug-adls
   ```
   
   You should see:
   ```json
   {
     "connection_string_set": true,
     "service_client_initialized": true,
     "files_found": 1,
     "files": [...]
   }
   ```

3. **Visit Gap Analysis:**
   ```
   http://localhost:5000/gap-analysis
   ```
   
   You should now see:
   - **Progress by Framework** showing Aged Care (53.5%) and NDIS (30.3%)
   - **Summary Stats** showing 2 total, 2 missing
   - **Table** with both frameworks listed

## If Still Not Working

### Check 1: Verify File Path in Azure

In Azure Portal, confirm your file is at:
```
Container: processed-doc-intel
Path: compliance-results/2025/11/user_1/compliance_summary.csv
```

### Check 2: Check Flask Logs

Look for these log messages:
```
INFO:app.services.azure_data_service:Found X compliance files in ADLS at compliance-results/2025/11/user_1
INFO:app.services.azure_data_service:Successfully read X rows from ...
```

If you see:
```
WARNING:app.services.azure_data_service:No ADLS client available
```

Then the connection string isn't being read. Make sure to restart Flask!

### Check 3: Verify User ID

The code looks for files at:
```
compliance-results/2025/11/user_{current_user.id}/
```

If your user ID is not 1, the path will be different. Check what user you're logged in as.

To see all files regardless of user, temporarily change line 71 in `azure_data_service.py`:
```python
# FROM:
search_path = f"{self.results_path}/{year}/{month:02d}/user_{user_id}"

# TO (temporary):
search_path = self.results_path  # Search all files
```

## Expected Result

After the fix, your Gap Analysis page should show:

**Progress by Framework:**
```
Aged Care          53.5%
[████████░░░░░░░░░░] 
Status: Missing

NDIS               30.3%
[███░░░░░░░░░░░░░░░]
Status: Missing
```

**Summary Stats:**
- Total Requirements: 2
- Requirements Met: 0
- Pending Review: 0
- Gaps Identified: 2
- Compliance: 41.5%

**Table:**
| Framework | Status | Progress | Evidence | Last Updated |
|-----------|--------|----------|----------|--------------|
| Aged Care | Missing | 53.5% | compliance_summary.csv | Today |
| NDIS | Missing | 30.3% | compliance_summary.csv | Today |

## Next Steps

Once this is working:
1. Add more frameworks to your CSV
2. Update statuses (Complete, Needs Review, Missing)
3. The page will automatically update!

No more hardcoded values - everything comes from your ADLS file!
