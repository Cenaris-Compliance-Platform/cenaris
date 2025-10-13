# Azure ML Compliance Analysis Integration

This document explains how to integrate your Azure Machine Learning compliance analysis results with the Cenaris dashboard.

## 🎯 Overview

Your ML work on Azure generates compliance analysis results stored in Azure Data Lake Storage. This integration automatically displays those results in a dynamic, interactive dashboard that updates when new analysis files are added.

## 📊 Data Structure

The system expects your ML results in this format:

### File Location
```
abfss://processed-doc-intel@cenarisblobstorage.dfs.core.windows.net/compliance-results/
```

### Expected Columns
- `Best Match Page` - Page reference
- `Outcome Code` - Analysis outcome identifier  
- `Requirement` - Compliance requirement description
- `Rule` - Rule definition for compliance
- `Rule_Status` - Status of the rule (Complete/Needs Review/Missing)
- `Similarity` - ML similarity score (0.0 to 1.0)
- `Status` - Overall status assessment
- `Status_Score` - Numeric status score (0.0 to 1.0)
- `Weight` - Importance weight for the requirement
- `Weighted_Score` - Calculated weighted score

### Example Data
```csv
Best Match Page,Outcome Code,Requirement,Rule,Rule_Status,Similarity,Status,Status_Score,Weight,Weighted_Score
1,1.3,Choice independence and quality of life,Complete if informed decision,Complete,0.3007,Missing,0,4,0
1,1.1,Person-centred care,Complete if person-centred policy,Complete,0.4766,Needs Review,0.5,2.5,1.25
```

## 🚀 Quick Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Update your `.env` file:
```env
# Azure ML Results Configuration
AZURE_ML_STORAGE_ACCOUNT=cenarisblobstorage
AZURE_ML_CONTAINER=processed-doc-intel
AZURE_ML_RESULTS_PATH=compliance-results
AZURE_STORAGE_CONNECTION_STRING=your_connection_string
```

### 3. Test Configuration
```bash
python3 setup_azure_ml.py
```

### 4. Start the Application
```bash
python3 run.py
```

## 📱 Dashboard Features

### Main Dashboard
- **ML Compliance Rate**: Real-time average compliance across all frameworks
- **ML Analysis Files**: Number of processed analysis files
- **Auto-refresh**: Updates every 2 minutes when new files appear
- **Framework Breakdown**: Visual progress bars for each compliance framework

### ML Results Page (`/ml-results`)
- **File-by-file Analysis**: Detailed view of each ML analysis file
- **Status Indicators**: Color-coded status (Excellent/Good/Needs Attention/Critical)
- **Compliance Rates**: Percentage compliance for each framework
- **Real-time Updates**: Auto-refresh functionality
- **Export Options**: Download and report generation

### Gap Analysis Integration
- **ML-driven Insights**: Gap analysis updated with ML similarity scores
- **Requirement Details**: Drill-down to individual requirement analysis
- **Status Mapping**: ML status automatically mapped to compliance status

## 🔄 Auto-Refresh Functionality

The dashboard automatically checks for new ML results:

- **Frequency**: Every 2 minutes
- **Detection**: Monitors file count and last modified timestamps
- **Notification**: Toast notifications when new results are available
- **Auto-reload**: Seamless refresh of dashboard data

## 🎨 UI Components

### Status Color Coding
- 🟢 **Excellent** (90%+): Green - All requirements met
- 🔵 **Good** (70-89%): Blue - Most requirements met
- 🟡 **Needs Attention** (50-69%): Yellow - Some gaps identified
- 🔴 **Critical** (<50%): Red - Significant compliance gaps

### Progress Indicators
- **Circular Charts**: Overall compliance percentage
- **Progress Bars**: Framework-specific compliance rates
- **Status Badges**: Quick visual status identification
- **Similarity Scores**: ML confidence indicators

## 🔧 Configuration Options

### Azure Connection Methods

#### Method 1: Connection String (Recommended for Development)
```env
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...
```

#### Method 2: Account Key
```env
AZURE_STORAGE_ACCOUNT_KEY=your_account_key
```

#### Method 3: SAS Token
```env
AZURE_STORAGE_SAS_TOKEN=your_sas_token
```

#### Method 4: Azure AD (Production)
```env
AZURE_TENANT_ID=your_tenant_id
AZURE_CLIENT_ID=your_client_id
AZURE_CLIENT_SECRET=your_client_secret
```

### Customization Options

Edit `azure_config.py` to customize:
- Auto-refresh intervals
- Status mappings
- Color schemes
- File processing limits

## 📊 API Endpoints

### Get ML Summary
```
GET /api/ml-summary
```
Returns JSON with current ML analysis summary for auto-refresh functionality.

### ML Results Dashboard
```
GET /ml-results
```
Main ML results dashboard with file listings and summaries.

### File Detail View
```
GET /ml-results/<file_path>
```
Detailed analysis view for a specific ML results file.

## 🔍 Troubleshooting

### Common Issues

#### 1. No ML Data Showing
- Check Azure connection string in `.env`
- Verify container and path names
- Run `python3 setup_azure_ml.py` to test connection

#### 2. Auto-refresh Not Working
- Check browser console for JavaScript errors
- Verify API endpoint is accessible
- Ensure proper authentication

#### 3. File Format Issues
- Ensure CSV files have the expected column structure
- Check file encoding (UTF-8 recommended)
- Verify file permissions in Azure Storage

### Mock Data Mode

For development/demo purposes, the system includes mock data:
- SOX Compliance: 83.3% compliant
- GDPR Analysis: 62.5% compliant  
- ISO 27001: 93.3% compliant
- PCI DSS: 33.3% compliant

## 🚀 Production Deployment

### Azure Authentication
For production, use Azure AD authentication:

1. Create an Azure AD application
2. Grant Storage Blob Data Reader permissions
3. Configure environment variables
4. Update `azure_data_service.py` to use Azure AD

### Performance Optimization
- Implement caching for frequently accessed data
- Use Azure CDN for static assets
- Consider Azure Functions for serverless processing
- Set up monitoring and alerting

## 📈 Future Enhancements

### Planned Features
- Real-time WebSocket updates
- Advanced filtering and search
- Custom report generation
- Integration with Azure Monitor
- Machine learning model performance tracking
- Automated compliance scoring algorithms

### Integration Possibilities
- Power BI dashboards
- Microsoft Teams notifications
- Azure Logic Apps workflows
- Custom API integrations

## 🆘 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review Azure Storage logs
3. Test connection with `setup_azure_ml.py`
4. Verify file formats and permissions

The integration preserves your beautiful UI design while adding powerful ML-driven compliance insights!