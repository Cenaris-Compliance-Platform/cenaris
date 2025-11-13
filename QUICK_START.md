# Quick Start - Display ADLS Compliance Scores

## What You Need to Provide

### 1. Azure Connection String
Add to your `.env` file:
```bash
AZURE_STORAGE_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=cenarisblobstorage;AccountKey=YOUR_KEY_HERE;EndpointSuffix=core.windows.net"
```

Get it from: Azure Portal → cenarisblobstorage → Access keys

### 2. That's it! 

Your ADLS structure is already configured:
- Storage Account: `cenarisblobstorage` ✓
- Container: `results` ✓
- Path: `compliance-results/2025/11/user_1/compliance_summary.csv` ✓

## Test It

```bash
# 1. Install Azure SDK (if needed)
pip install azure-storage-file-datalake

# 2. Test connection
python test_adls_connection.py

# 3. Start your app
python run.py

# 4. Login and view:
#    - Dashboard (overall scores)
#    - AI Evidence (framework details)
#    - Gap Analysis (detailed breakdown)
```

## What You'll See

### Dashboard
- Overall compliance: **3.93/10** (39.3%)
- Framework breakdown: Aged Care, NDIS
- Real-time ADLS status

### AI Evidence Page
- **Aged Care**: 53.5% confidence (Missing)
- **NDIS**: 30.3% confidence (Missing)

### Gap Analysis Page
- **Progress by Framework** section shows:
  - Aged Care: 53.5% progress bar (Missing status)
  - NDIS: 30.3% progress bar (Missing status)
- **Summary Stats**:
  - Total Requirements: 2 frameworks
  - Missing: 2
  - Compliance: 41.5% average
- **Detailed Table** with each framework as a row

## Your Data Structure

```csv
Framework,Compliance_Score,Status
Aged Care,5.35,Missing
NDIS,3.03,Missing
Overall,3.93,
```

This gets automatically:
- Parsed from ADLS
- Converted to percentages
- Displayed across all pages
- Updated in real-time

Done! Just add your connection string and you're ready to go.
