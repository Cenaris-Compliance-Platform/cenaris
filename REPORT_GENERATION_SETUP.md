# Report Generation Setup Guide

## ✅ What's Been Added

Three professional PDF reports that can be downloaded from the Gap Analysis page:

1. **Gap Analysis Report** - Detailed compliance gap analysis
2. **Accreditation Plan Template** - Readiness overview and action plan
3. **Audit Pack Export** - Complete audit documentation package

## 📦 Installation Required

Install the ReportLab library for PDF generation:

```bash
pip install reportlab
```

Or add to your `requirements.txt`:
```
reportlab==4.0.7
```

Then install:
```bash
pip install -r requirements.txt
```

## 🚀 How to Use

### Step 1: Restart Flask
```bash
python run.py
```

### Step 2: Go to Gap Analysis Page
```
http://localhost:5000/gap-analysis
```

### Step 3: Generate Reports
1. Click the **"Generate Report"** button (top right)
2. Choose from dropdown:
   - Gap Analysis Report
   - Accreditation Plan
   - Audit Pack Export
3. PDF downloads automatically!

## 📊 What Each Report Contains

### 1. Gap Analysis Report

**Sections:**
- **Organisation Information** - Name, ABN, address, contact, framework
- **Executive Summary** - Purpose, frameworks reviewed, readiness score
- **Key Statistics** - Total requirements, met, pending, gaps
- **Assessment Methodology** - Rating scale and definitions
- **Detailed Gap Analysis Table** - Framework-by-framework breakdown
- **Recommendations** - Priority actions for gaps

**Data Source:** Real-time from ADLS compliance data

### 2. Accreditation Plan Template

**Sections:**
- **Provider & Accreditation Summary** - Organisation details, readiness score
- **Readiness Overview** - Category-by-category completion percentages
- **Action Plan** - Tasks, owners, due dates, status
- **Linked Templates** - Evidence files and templates

**Data Source:** Real-time from ADLS compliance data

### 3. Audit Pack Export

**Sections:**
- **Organisation Information** - Complete org details
- **Readiness Summary** - Overall compliance percentage
- **Framework Summary Table** - Per-framework readiness
- **Evidence Repository** - List of all uploaded documents
- **Clause-to-Evidence Mapping** - Requirements linked to evidence

**Data Source:** ADLS compliance data + Evidence Repository documents

## 🎨 Report Features

### Professional Design
- ✅ Color-coded sections (blue headers, green success, red warnings)
- ✅ Formatted tables with alternating row colors
- ✅ Proper spacing and typography
- ✅ Page breaks for readability
- ✅ Consistent branding

### Dynamic Content
- ✅ Real data from your ADLS compliance files
- ✅ Current date/time stamps
- ✅ Actual framework scores and statuses
- ✅ Your uploaded documents list
- ✅ Calculated statistics

### Export Ready
- ✅ PDF format (universally compatible)
- ✅ Printable (Letter size, proper margins)
- ✅ Shareable (email, upload to portals)
- ✅ Archivable (date-stamped filenames)

## 📝 Customizing Organization Data

Edit the `org_data` dictionary in `app/main/routes.py` (line ~340):

```python
org_data = {
    'name': 'Your Organisation Name',  # ← Change this
    'abn': '12 345 678 901',           # ← Change this
    'address': '123 Main St, City',    # ← Change this
    'contact_name': 'Contact Person',  # ← Change this
    'email': current_user.email,       # ← Auto from user
    'framework': 'NDIS / Aged Care',   # ← Change this
    'audit_type': 'Initial'            # ← Change this
}
```

Or better yet, store this in a database table and fetch it dynamically!

## 🔧 Technical Details

### Files Created:
1. **`app/services/report_generator.py`** - PDF generation service
   - `generate_gap_analysis_report()` - Gap analysis PDF
   - `generate_accreditation_plan()` - Accreditation plan PDF
   - `generate_audit_pack()` - Audit pack PDF

2. **Route added to `app/main/routes.py`:**
   - `/reports/generate/<report_type>` - Generate and download reports

3. **Updated `app/templates/main/gap_analysis.html`:**
   - Added "Generate Report" dropdown button

### Report Generation Flow:
```
User clicks button
    ↓
Route: /reports/generate/gap-analysis
    ↓
Fetch data from ADLS (azure_data_service)
    ↓
Fetch documents from database
    ↓
Generate PDF (report_generator)
    ↓
Download to user's computer
```

### PDF Library: ReportLab
- Industry-standard Python PDF library
- Supports tables, styling, images
- Professional output quality
- Highly customizable

## 📋 Report Filenames

Reports are automatically named with date stamps:
- `Gap_Analysis_Report_20251113.pdf`
- `Accreditation_Plan_20251113.pdf`
- `Audit_Pack_Export_20251113.pdf`

## 🎯 What Gets Included

### From ADLS:
- Framework names (Aged Care, NDIS, etc.)
- Compliance scores (converted to percentages)
- Status (Complete, Missing, Needs Review)
- Overall readiness percentage

### From Database:
- Uploaded documents list
- Document names, sizes, dates
- User information

### Calculated:
- Total requirements
- Requirements met/pending/missing
- Average compliance percentage
- Priority levels
- Recommended actions

## 🔒 Security

- ✅ Login required to generate reports
- ✅ Only user's own data included
- ✅ No sensitive credentials in PDFs
- ✅ Temporary buffer (not saved on server)
- ✅ Direct download to user

## 🐛 Troubleshooting

### Error: "No module named 'reportlab'"
**Solution:**
```bash
pip install reportlab
```

### Error: "Invalid report type"
**Check:** URL should be one of:
- `/reports/generate/gap-analysis`
- `/reports/generate/accreditation-plan`
- `/reports/generate/audit-pack`

### PDF is empty or has errors
**Check:**
1. Do you have data in ADLS? (Visit Gap Analysis page first)
2. Check Flask console for error messages
3. Verify ADLS connection is working

### Download doesn't start
**Check:**
1. Browser pop-up blocker settings
2. Flask console for errors
3. Try different browser

## 📈 Future Enhancements (Optional)

- Add company logo to reports
- Include charts/graphs
- Add digital signatures
- Email reports directly
- Schedule automatic report generation
- Add more report templates
- Customize report styling per organization

## ✨ Benefits

1. **Professional Documentation** - Audit-ready reports
2. **Time Saving** - Auto-generated from your data
3. **Always Current** - Real-time data from ADLS
4. **Shareable** - PDF format works everywhere
5. **Compliant** - Meets accreditation requirements

## 🎉 You're Ready!

1. Install reportlab: `pip install reportlab`
2. Restart Flask
3. Go to Gap Analysis page
4. Click "Generate Report"
5. Download your professional compliance reports!

All three reports are now available! 📄✨
