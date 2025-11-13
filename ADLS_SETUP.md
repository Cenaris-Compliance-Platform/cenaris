# ADLS Integration Setup Guide

## What's Been Updated

Your compliance app now fetches **real data** from Azure Data Lake Storage (ADLS) and displays it on:
- **Dashboard** - Overall compliance scores
- **AI Evidence Page** - Framework-specific compliance entries
- **Gap Analysis Page** - Detailed breakdown with scores and status

## Configuration Required

### 1. Add Azure Connection String to `.env`

Add this line to your `.env` file:

```bash
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=cenarisblobstorage;AccountKey=YOUR_ACCOUNT_KEY;EndpointSuffix=core.windows.net"
```

**To get your connection string:**
1. Go to Azure Portal
2. Navigate to your storage account: `cenarisblobstorage`
3. Go to "Access keys" under Security + networking
4. Copy "Connection string" from key1 or key2

### 2. Install Azure SDK (if not already installed)

```bash
pip install azure-storage-file-datalake
```

### 3. Verify Your ADLS Structure

Your files should be at:
```
Container: results
Path: compliance-results/2025/11/user_1/compliance_summary.csv
```

CSV Format:
```
Framework,Compliance_Score,Status
Aged Care,5.35,Missing
NDIS,3.03,Missing
Overall,3.93,
```

## Testing the Connection

Run the test script:

```bash
python test_adls_connection.py
```

This will:
- ✓ Check if connection string is set
- ✓ List files in ADLS
- ✓ Read and parse CSV data
- ✓ Show processed compliance scores
- ✓ Display dashboard summary

## How It Works

### Data Flow:
1. **User logs in** → System identifies user_id
2. **Routes call** → `azure_data_service.get_dashboard_summary(user_id=current_user.id)`
3. **Service fetches** → Files from `compliance-results/2025/11/user_{id}/`
4. **CSV parsed** → Framework, Compliance_Score, Status columns
5. **Data displayed** → On Dashboard, AI Evidence, Gap Analysis pages

### Score Conversion:
- Your scores (0-10 scale) → Converted to percentages for display
- Example: `5.35` → `53.5%` compliance rate
- Status mapping: `Missing`, `Complete`, `Needs Review`

## Pages Updated

### 1. Dashboard (`/dashboard`)
- Shows overall compliance score from "Overall" row
- Displays total requirements by framework count
- Real-time ADLS connection status

### 2. AI Evidence (`/ai-evidence`)
- Each framework becomes an evidence entry
- Confidence score = Compliance_Score × 10
- Shows framework name, score, and status

### 3. Gap Analysis (`/gap-analysis`)
- Framework-by-framework breakdown
- Progress bars based on compliance scores
- Status badges (Complete/Missing/Needs Review)
- Summary statistics from ADLS data

## Troubleshooting

### No data showing?
1. Check connection string is correct in `.env`
2. Verify file path: `compliance-results/2025/11/user_1/compliance_summary.csv`
3. Run test script to see detailed error messages
4. Check logs for ADLS connection errors

### Wrong user data?
- System uses `current_user.id` to build path
- Path format: `compliance-results/{year}/{month}/user_{id}/`
- Make sure your user_id matches the folder structure

### CSV parsing errors?
- Ensure columns are: `Framework`, `Compliance_Score`, `Status`
- Check for extra spaces in column names
- Verify CSV encoding is UTF-8

## Next Steps

1. Add your Azure connection string to `.env`
2. Run the test script to verify connection
3. Start your Flask app and login
4. Navigate to Dashboard, AI Evidence, or Gap Analysis
5. You should see your real ADLS compliance scores!

## Support

If you see mock data instead of real data:
- Connection string might be missing
- ADLS path might be incorrect
- Check browser console and Flask logs for errors
