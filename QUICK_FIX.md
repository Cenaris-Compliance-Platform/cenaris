# Quick Fix - Show Data Immediately

If you want to see the Gap Analysis page working RIGHT NOW while we debug ADLS, here's a quick fix:

## Option 1: Add Mock Data Fallback

Add this to your `gap_analysis()` route in `app/main/routes.py` (after line 206, before `summary_stats =`):

```python
    # TEMPORARY: Add mock data if ADLS returns nothing
    if not gap_data:
        from datetime import datetime
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

## Option 2: Check Your Exact ADLS Path

The most common issue is the path doesn't match. 

**Your code expects:**
```
Container: results
Path: compliance-results/2025/11/user_1/compliance_summary.csv
```

**But your file might actually be at:**
```
Container: results  
Path: compliance-results/2025/11/user_1/compliance_summary.csv
```

OR

```
Container: processed-doc-intel
Path: compliance-results/compliance_summary.csv
```

**To fix, update line 27 in `app/services/azure_data_service.py`:**

```python
# If your container is actually 'processed-doc-intel':
self.container_name = "processed-doc-intel"

# And if file is at root of compliance-results (no user folders):
# Comment out lines 68-73 and just use:
search_path = self.results_path
```

## Option 3: Test Direct File Read

Add this test route to see if you can read the file directly:

```python
@bp.route('/test-read-file')
@login_required
def test_read_file():
    """Test reading file directly"""
    try:
        # Try different paths
        paths_to_try = [
            "compliance-results/2025/11/user_1/compliance_summary.csv",
            "compliance-results/compliance_summary.csv",
            "2025/11/user_1/compliance_summary.csv",
        ]
        
        results = {}
        for path in paths_to_try:
            try:
                data = azure_data_service.read_adls_file(path)
                results[path] = {
                    'success': True,
                    'rows': len(data),
                    'data': data
                }
            except Exception as e:
                results[path] = {
                    'success': False,
                    'error': str(e)
                }
        
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)})
```

Visit: `http://localhost:5000/test-read-file`

This will tell you which path actually works!

## What to Do Next

1. **Start your Flask app**
2. **Visit:** `http://localhost:5000/debug-adls`
3. **Check the output** - it will tell you:
   - Is ADLS connected?
   - How many files found?
   - What's the error?

4. **Share the output with me** and I can give you the exact fix!

## Most Likely Issue

Based on your setup, I suspect the container name is wrong. Try changing line 27 in `app/services/azure_data_service.py`:

```python
# FROM:
self.container_name = "results"

# TO:
self.container_name = "processed-doc-intel"
```

Because your .env file shows:
```
AZURE_ML_CONTAINER=processed-doc-intel
```

But the code is using `"results"`!
