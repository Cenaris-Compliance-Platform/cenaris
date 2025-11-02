from flask import render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app.main import bp
from app.models import Document

def get_mock_ml_summary():
    """Get mock ML summary data"""
    from datetime import datetime
    
    class FileSummary:
        def __init__(self, data):
            self.file_name = data['file_name']
            self.overall_status = data['overall_status']
            self.compliance_score = data['compliance_score']
            self.compliancy_rate = data['compliance_score']  # Add this for templates
            self.requirements_met = data['requirements_met']
            self.requirements_total = data['requirements_total']
            self.total_requirements = data['requirements_total']  # Add this for templates
            self.last_analyzed = data['last_analyzed']
    
    class MLSummary:
        def __init__(self):
            self.total_files = len(Document.get_by_user(current_user.id)) if current_user.is_authenticated else 3
            self.avg_compliancy_rate = 85.5
            self.total_complete = 3
            self.total_needs_review = 1
            self.total_missing = 1
            self.last_updated = datetime.now()
            self.connection_status = 'Connected'
            self.adls_path = 'abfss://processed-doc-intel@cenarisblobstorage.dfs.core.windows.net/compliance-results'
            self.file_summaries = [
                FileSummary({
                    'file_name': 'policy_document.csv',
                    'overall_status': 'Complete',
                    'compliance_score': 92,
                    'requirements_met': 15,
                    'requirements_total': 18,
                    'last_analyzed': '2025-11-02'
                }),
                FileSummary({
                    'file_name': 'access_control.csv',
                    'overall_status': 'Needs Review',
                    'compliance_score': 78,
                    'requirements_met': 12,
                    'requirements_total': 16,
                    'last_analyzed': '2025-11-01'
                })
            ]
    
    return MLSummary()

@bp.route('/')
def index():
    """Home page route."""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    return render_template('main/index.html', title='Home')

@bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard route for authenticated users."""
    recent_documents = Document.get_by_user(current_user.id, limit=5)
    all_documents = Document.get_by_user(current_user.id)
    total_documents = len(all_documents)
    ml_summary = get_mock_ml_summary()
    
    return render_template('main/dashboard.html', 
                         title='Dashboard',
                         recent_documents=recent_documents,
                         total_documents=total_documents,
                         ml_summary=ml_summary)

@bp.route('/upload')
@login_required
def upload():
    """Upload page route."""
    return render_template('main/upload.html', title='Upload Document')

@bp.route('/documents')
@login_required
def documents():
    """Documents listing route."""
    user_documents = Document.get_by_user(current_user.id)
    return render_template('main/documents.html', 
                         title='My Documents',
                         documents=user_documents)

@bp.route('/evidence-repository')
@login_required
def evidence_repository():
    """Evidence repository route to display all documents."""
    documents = Document.get_by_user(current_user.id)
    return render_template('main/evidence_repository.html', 
                         title='Evidence Repository',
                         documents=documents)

@bp.route('/ai-evidence')
@login_required
def ai_evidence():
    """AI Evidence route to display AI-generated evidence entries."""
    # Mock AI evidence data
    ai_evidence_entries = [
        {
            'id': 1,
            'document_title': 'SOX Compliance Report Q3 2025',
            'framework': 'SOX',
            'requirement': 'Section 404 - Internal Controls',
            'confidence_score': 92,
            'status': 'Complete',
            'date_analyzed': '2025-11-01',
            'evidence_type': 'Policy Document',
            'key_findings': 'Strong internal control framework documented',
            'summary': 'Comprehensive SOX compliance documentation covering internal control requirements and audit procedures.'
        },
        {
            'id': 2,
            'document_title': 'ISO 27001 Access Control Policy',
            'framework': 'ISO 27001',
            'requirement': 'A.9.2 User Access Management',
            'confidence_score': 88,
            'status': 'Needs Review',
            'date_analyzed': '2025-10-28',
            'evidence_type': 'Policy Document',
            'key_findings': 'Access control procedures well defined',
            'summary': 'Detailed access control policy with user management procedures and authentication requirements.'
        },
        {
            'id': 3,
            'document_title': 'Data Backup Procedures',
            'framework': 'ISO 27001',
            'requirement': 'A.12.3 Information Backup',
            'confidence_score': 95,
            'status': 'Complete',
            'date_analyzed': '2025-10-25',
            'evidence_type': 'Procedure',
            'key_findings': 'Comprehensive backup strategy documented',
            'summary': 'Complete backup and recovery procedures including schedules, testing protocols, and restoration processes.'
        }
    ]
    
    return render_template('main/ai_evidence.html', 
                         title='AI Evidence',
                         ai_evidence_entries=ai_evidence_entries)

@bp.route('/ai-evidence/<int:entry_id>')
@login_required
def ai_evidence_detail(entry_id):
    """AI Evidence detail view."""
    # Mock detailed data
    ai_evidence_detail = {
        'id': entry_id,
        'document_title': 'SOX Compliance Report Q3 2025',
        'framework': 'SOX',
        'requirement': 'Section 404 - Internal Controls',
        'confidence_score': 92,
        'status': 'Complete',
        'date_analyzed': '2025-11-01',
        'evidence_type': 'Policy Document',
        'key_findings': 'Strong internal control framework documented',
        'summary': 'Comprehensive SOX compliance documentation covering internal control requirements and audit procedures.',
        'detailed_analysis': 'The document provides comprehensive coverage of internal control requirements...',
        'recommendations': ['Continue monitoring', 'Update quarterly']
    }
    
    return render_template('main/ai_evidence_detail.html', 
                         title='AI Evidence Detail',
                         entry=ai_evidence_detail)

@bp.route('/document/<int:doc_id>')
@login_required
def document_detail(doc_id):
    """Document detail route."""
    document = Document.get_by_id(doc_id)
    if not document or document.user_id != current_user.id:
        return redirect(url_for('main.documents'))
    
    return render_template('main/document_detail.html',
                         title=f'Document: {document.filename}',
                         document=document)

@bp.route('/gap-analysis')
@login_required
def gap_analysis():
    """Gap Analysis route."""
    gaps = [
        {
            'framework': 'ISO 27001',
            'requirement': 'A.12.1.2 Change Management',
            'status': 'Missing',
            'severity': 'High',
            'description': 'No evidence of formal change management procedures'
        },
        {
            'framework': 'SOC 2',
            'requirement': 'CC6.1 Logical Access Controls',
            'status': 'Needs Review',
            'severity': 'Medium',
            'description': 'Access controls documented but need validation'
        }
    ]
    
    summary_stats = {
        'total': 25,
        'met': 15,
        'pending': 5,
        'not_met': 5,
        'compliance_percentage': 60
    }
    
    return render_template('main/gap_analysis.html',
                         title='Gap Analysis',
                         gaps=gaps,
                         summary_stats=summary_stats,
                         ml_summary=get_mock_ml_summary())

@bp.route('/reports')
@login_required
def reports():
    """Reports route."""
    reports = [
        {
            'id': 1,
            'name': 'ISO 27001 Compliance Report',
            'description': 'Comprehensive assessment of ISO 27001 compliance status',
            'type': 'Compliance Assessment',
            'generated_date': '2024-10-13',
            'status': 'Complete',
            'download_url': '#'
        }
    ]
    
    return render_template('main/reports.html', 
                         title='Compliance Reports',
                         reports=reports)

@bp.route('/settings')
@login_required
def settings():
    """Settings route."""
    return render_template('main/settings.html', title='Settings')

@bp.route('/help')
@login_required
def help():
    """Help route."""
    return render_template('main/help.html', title='Help & Documentation')

@bp.route('/profile')
@login_required
def profile():
    """User profile route."""
    return render_template('main/profile.html', title='My Profile')

@bp.route('/notifications')
@login_required
def notifications():
    """Notifications route."""
    notifications = [
        {
            'id': 1,
            'title': 'New compliance requirement detected',
            'message': 'ISO 27001:2022 update requires additional documentation',
            'type': 'warning',
            'timestamp': '2024-10-13 14:30:00',
            'read': False
        }
    ]
    
    return render_template('main/notifications.html', 
                         title='Notifications',
                         notifications=notifications)

@bp.route('/ml-results')
@login_required
def ml_results():
    """ML Results dashboard."""
    compliance_files = [
        {
            'file_name': 'policy_document.pdf',
            'compliance_score': 85,
            'status': 'Complete',
            'last_analyzed': '2025-11-02'
        }
    ]
    
    return render_template('main/ml_results.html',
                         title='ML Analysis Results',
                         ml_summary=get_mock_ml_summary(),
                         compliance_files=compliance_files)

@bp.route('/ml-file-detail/<path:file_path>')
@login_required
def ml_file_detail(file_path):
    """Detailed view of ML analysis file."""
    file_analysis = {
        'file_name': file_path,
        'compliance_score': 85,
        'compliancy_rate': 85,  # Add this for templates
        'requirements': [
            {'name': 'Access Control', 'status': 'Met', 'confidence': 0.9}
        ]
    }
    
    return render_template('main/ml_file_detail.html',
                         title=f'Analysis: {file_path}',
                         file_analysis=file_analysis)

@bp.route('/api/ml-summary')
@login_required
def api_ml_summary():
    """API endpoint for ML summary data."""
    return jsonify(get_mock_ml_summary())

@bp.route('/adls-raw-data')
@login_required
def adls_raw_data():
    """Show raw ADLS data."""
    return render_template('main/adls_raw_data.html',
                         title='ADLS Raw Data',
                         ml_summary=get_mock_ml_summary())

@bp.route('/adls-connection')
@login_required
def adls_connection():
    """Show ADLS connection status."""
    return render_template('main/adls_connection.html',
                         title='ADLS Connection',
                         ml_summary=get_mock_ml_summary())

@bp.route('/audit-export')
@login_required
def audit_export():
    """Audit export route for generating compliance reports."""
    export_stats = {
        'total_reports': 12,
        'ready_reports': 8,
        'recent_exports': 5,
        'total_size': '45.2 MB'
    }
    
    return render_template('main/audit_export.html',
                         title='Audit Export',
                         export_stats=export_stats)

@bp.route('/user-roles')
@login_required
def user_roles():
    """User roles management route."""
    return render_template('main/user_roles.html',
                         title='User Roles')
