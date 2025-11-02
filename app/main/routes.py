from flask import render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app.main import bp
from app.models import Document
# from app.services.azure_data_service import azure_data_service  # Temporarily disabled for deployment

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
    # Get recent documents for the current user
    recent_documents = Document.get_by_user(current_user.id, limit=5)
    
    # Get total document count
    all_documents = Document.get_by_user(current_user.id)
    total_documents = len(all_documents)
    
    # Get Azure ML compliance results
    ml_summary = azure_data_service.get_dashboard_summary()
    
    return render_template('main/dashboard.html', 
                         title='Dashboard',
                         recent_documents=recent_documents,
                         total_documents=total_documents,
                         ml_summary=ml_summary)

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
            'source': 'Financial Systems Audit',
            'confidence_score': 92,
            'upload_date': '2025-09-15',
            'document_type': 'Audit Report',
            'summary': 'Comprehensive SOX compliance analysis showing strong internal controls',
            'ai_notes': 'High confidence in compliance status based on control testing results'
        },
        {
            'id': 2,
            'document_title': 'GDPR Data Processing Agreement',
            'source': 'Privacy Impact Assessment',
            'confidence_score': 87,
            'upload_date': '2025-09-10',
            'document_type': 'Legal Agreement',
            'summary': 'Data processing agreement meets GDPR requirements with minor recommendations',
            'ai_notes': 'Strong privacy controls identified, recommended annual review'
        },
        {
            'id': 3,
            'document_title': 'ISO 27001 Security Controls Matrix',
            'source': 'Security Assessment',
            'confidence_score': 95,
            'upload_date': '2025-09-08',
            'document_type': 'Security Documentation',
            'summary': 'Comprehensive security controls mapping with full ISO 27001 alignment',
            'ai_notes': 'Excellent security posture with all critical controls implemented'
        },
        {
            'id': 4,
            'document_title': 'PCI DSS Compliance Checklist',
            'source': 'Payment Systems Review',
            'confidence_score': 78,
            'upload_date': '2025-09-05',
            'document_type': 'Compliance Checklist',
            'summary': 'PCI DSS requirements assessment with identified improvement areas',
            'ai_notes': 'Good compliance foundation, requires attention to network segmentation'
        },
        {
            'id': 5,
            'document_title': 'Risk Assessment Framework',
            'source': 'Enterprise Risk Management',
            'confidence_score': 89,
            'upload_date': '2025-09-01',
            'document_type': 'Risk Documentation',
            'summary': 'Comprehensive risk assessment methodology aligned with industry standards',
            'ai_notes': 'Robust risk framework with clear mitigation strategies'
        }
    ]
    
    return render_template('main/ai_evidence.html', 
                         title='AI Evidence',
                         ai_evidence_entries=ai_evidence_entries)

@bp.route('/ai-evidence/<int:entry_id>')
@login_required
def ai_evidence_detail(entry_id):
    """AI Evidence detail view."""
    # Mock detailed data - in real app, this would fetch from database
    ai_evidence_detail = {
        'id': entry_id,
        'document_title': 'SOX Compliance Report Q3 2025',
        'source': 'Financial Systems Audit',
        'confidence_score': 92,
        'upload_date': '2025-09-15',
        'document_type': 'Audit Report',
        'summary': 'Comprehensive SOX compliance analysis showing strong internal controls with detailed testing of key financial processes and systems.',
        'ai_notes': 'High confidence in compliance status based on control testing results. AI analysis identified strong segregation of duties, proper authorization controls, and comprehensive documentation.',
        'file_size': '2.4 MB',
        'pages': 45,
        'language': 'English',
        'keywords': ['SOX', 'Internal Controls', 'Financial Reporting', 'Audit', 'Compliance'],
        'risk_level': 'Low',
        'compliance_frameworks': ['SOX', 'COSO', 'PCAOB'],
        'last_reviewed': '2025-09-20'
    }
    
    return render_template('main/ai_evidence_detail.html', 
                         title='AI Evidence Detail',
                         entry=ai_evidence_detail)

@bp.route('/gap-analysis')
@login_required
def gap_analysis():
    """Gap Analysis route to display compliance gaps from Azure ML results."""
    # Get Azure ML compliance results
    ml_summary = azure_data_service.get_dashboard_summary()
    
    # Convert ML results to gap analysis format
    gap_analysis_data = []
    
    for file_summary in ml_summary['file_summaries']:
        # Get detailed requirements for this file
        detailed_analysis = azure_data_service.get_file_analysis_summary(f"compliance-results/{file_summary['file_name']}")
        
        for req in detailed_analysis.get('requirements', []):
            # Debug: print the actual keys in req
            print(f"DEBUG: req keys = {list(req.keys())}")
            print(f"DEBUG: req = {req}")
            
            # Map ML status to gap analysis status
            status_mapping = {
                'Complete': 'Met',
                'Needs Review': 'Pending', 
                'Missing': 'Not Met'
            }
            
            # Use safe access with .get() to avoid KeyError
            gap_analysis_data.append({
                'requirement_name': f"{file_summary['framework']} - {req.get('Requirement', 'Unknown Requirement')}",
                'status': status_mapping.get(req.get('Status', 'Unknown'), 'Not Met'),
                'supporting_evidence': f"ML Analysis (Similarity: {req.get('Similarity', 0):.2f})",
                'completion_percentage': int(req.get('Status_Score', 0) * 100),
                'last_updated': file_summary['last_updated'].strftime('%Y-%m-%d'),
                'framework': file_summary['framework'],
                'similarity_score': req.get('Similarity', 0),
                'weighted_score': req.get('Weighted_Score', 0)
            })
    
    # If no ML data, fall back to mock data
    if not gap_analysis_data:
        gap_analysis_data = [
            {
                'requirement_name': 'SOX Section 404 - Internal Controls',
                'status': 'Met',
                'supporting_evidence': 'Internal Control Assessment Report, Management Certification',
                'completion_percentage': 100,
                'last_updated': '2025-09-15',
                'framework': 'SOX',
                'similarity_score': 0.92,
                'weighted_score': 4.0
            },
            {
                'requirement_name': 'GDPR Article 30 - Records of Processing',
                'status': 'Pending',
                'supporting_evidence': 'Data Processing Inventory (In Progress)',
                'completion_percentage': 65,
                'last_updated': '2025-09-10',
                'framework': 'GDPR',
                'similarity_score': 0.65,
                'weighted_score': 2.5
            }
        ]
    
    # Calculate summary statistics from ML data
    summary_stats = {
        'total': ml_summary['total_requirements'],
        'met': ml_summary['total_complete'],
        'pending': ml_summary['total_needs_review'],
        'not_met': ml_summary['total_missing'],
        'compliance_percentage': ml_summary['avg_compliancy_rate']
    }
    
    return render_template('main/gap_analysis.html', 
                         title='Gap Analysis',
                         gap_data=gap_analysis_data,
                         summary_stats=summary_stats,
                         ml_summary=ml_summary)

@bp.route('/user-roles')
@login_required
def user_roles():
    """User Roles route to display user roles and permissions."""
    # Mock user roles data
    user_roles_data = [
        {
            'id': 1,
            'role_name': 'System Administrator',
            'permissions': ['View', 'Edit', 'Delete', 'Approve', 'Manage Users', 'System Config'],
            'assigned_users': ['admin@compliance.com', 'sysadmin@cenaris.com'],
            'user_count': 2,
            'created_date': '2025-01-15',
            'description': 'Full system access with administrative privileges'
        },
        {
            'id': 2,
            'role_name': 'Compliance Manager',
            'permissions': ['View', 'Edit', 'Approve', 'Generate Reports'],
            'assigned_users': ['manager@cenaris.com', 'compliance.lead@cenaris.com'],
            'user_count': 2,
            'created_date': '2025-01-15',
            'description': 'Manage compliance processes and approve submissions'
        },
        {
            'id': 3,
            'role_name': 'Compliance Reviewer',
            'permissions': ['View', 'Edit', 'Comment'],
            'assigned_users': ['reviewer1@cenaris.com', 'reviewer2@cenaris.com', 'audit@cenaris.com'],
            'user_count': 3,
            'created_date': '2025-01-15',
            'description': 'Review and provide feedback on compliance documents'
        },
        {
            'id': 4,
            'role_name': 'Document Contributor',
            'permissions': ['View', 'Upload', 'Edit Own Documents'],
            'assigned_users': ['user@compliance.com', 'contributor1@cenaris.com', 'contributor2@cenaris.com', 'team@cenaris.com'],
            'user_count': 4,
            'created_date': '2025-01-15',
            'description': 'Upload and manage own compliance documents'
        },
        {
            'id': 5,
            'role_name': 'Read-Only Viewer',
            'permissions': ['View'],
            'assigned_users': ['viewer@cenaris.com', 'guest@cenaris.com'],
            'user_count': 2,
            'created_date': '2025-01-15',
            'description': 'View-only access to compliance documents and reports'
        }
    ]
    
    # Permission definitions for reference
    all_permissions = [
        {'name': 'View', 'description': 'View documents and reports'},
        {'name': 'Upload', 'description': 'Upload new documents'},
        {'name': 'Edit', 'description': 'Edit documents and metadata'},
        {'name': 'Delete', 'description': 'Delete documents'},
        {'name': 'Approve', 'description': 'Approve document submissions'},
        {'name': 'Comment', 'description': 'Add comments and feedback'},
        {'name': 'Generate Reports', 'description': 'Create compliance reports'},
        {'name': 'Manage Users', 'description': 'Manage user accounts'},
        {'name': 'System Config', 'description': 'Configure system settings'},
        {'name': 'Edit Own Documents', 'description': 'Edit only own uploaded documents'}
    ]
    
    return render_template('main/user_roles.html', 
                         title='User Roles',
                         roles_data=user_roles_data,
                         all_permissions=all_permissions)

@bp.route('/audit-export')
@login_required
def audit_export():
    """Audit Export route to display export options and generate reports."""
    # Mock audit export data
    available_reports = [
        {
            'id': 1,
            'name': 'SOX Compliance Report',
            'description': 'Comprehensive Sarbanes-Oxley compliance assessment and evidence summary',
            'type': 'Compliance Report',
            'format': ['PDF', 'Excel', 'Word'],
            'last_generated': '2025-09-20',
            'file_size': '2.4 MB',
            'status': 'Ready',
            'frameworks': ['SOX', 'COSO'],
            'estimated_time': '2-3 minutes'
        },
        {
            'id': 2,
            'name': 'GDPR Data Protection Audit',
            'description': 'Data protection compliance status and privacy impact assessment',
            'type': 'Privacy Report',
            'format': ['PDF', 'Excel'],
            'last_generated': '2025-09-15',
            'file_size': '1.8 MB',
            'status': 'Ready',
            'frameworks': ['GDPR'],
            'estimated_time': '1-2 minutes'
        },
        {
            'id': 3,
            'name': 'ISO 27001 Security Assessment',
            'description': 'Information security management system compliance evaluation',
            'type': 'Security Report',
            'format': ['PDF', 'Word'],
            'last_generated': '2025-09-10',
            'file_size': '3.1 MB',
            'status': 'Ready',
            'frameworks': ['ISO 27001'],
            'estimated_time': '3-4 minutes'
        },
        {
            'id': 4,
            'name': 'PCI DSS Compliance Gap Analysis',
            'description': 'Payment card industry data security standard gap assessment',
            'type': 'Gap Analysis',
            'format': ['PDF', 'Excel'],
            'last_generated': '2025-09-05',
            'file_size': '1.5 MB',
            'status': 'Needs Update',
            'frameworks': ['PCI DSS'],
            'estimated_time': '2-3 minutes'
        },
        {
            'id': 5,
            'name': 'Comprehensive Compliance Dashboard',
            'description': 'Executive summary of all compliance frameworks and current status',
            'type': 'Executive Summary',
            'format': ['PDF', 'PowerPoint'],
            'last_generated': '2025-08-30',
            'file_size': '4.2 MB',
            'status': 'Needs Update',
            'frameworks': ['SOX', 'GDPR', 'ISO 27001', 'PCI DSS', 'HIPAA'],
            'estimated_time': '5-7 minutes'
        }
    ]
    
    # Mock recent exports
    recent_exports = [
        {
            'report_name': 'SOX Compliance Report',
            'exported_by': current_user.email,
            'export_date': '2025-09-20',
            'format': 'PDF',
            'file_size': '2.4 MB',
            'status': 'Completed'
        },
        {
            'report_name': 'GDPR Data Protection Audit',
            'exported_by': 'manager@cenaris.com',
            'export_date': '2025-09-18',
            'format': 'Excel',
            'file_size': '1.8 MB',
            'status': 'Completed'
        },
        {
            'report_name': 'ISO 27001 Security Assessment',
            'exported_by': current_user.email,
            'export_date': '2025-09-15',
            'format': 'PDF',
            'file_size': '3.1 MB',
            'status': 'Completed'
        }
    ]
    
    # Export statistics
    export_stats = {
        'total_reports': len(available_reports),
        'ready_reports': len([r for r in available_reports if r['status'] == 'Ready']),
        'recent_exports': len(recent_exports),
        'total_size': '12.0 MB'
    }
    
    return render_template('main/audit_export.html', 
                         title='Audit Export',
                         available_reports=available_reports,
                         recent_exports=recent_exports,
                         export_stats=export_stats)

@bp.route('/ml-results')
@login_required
def ml_results():
    """ML Results dashboard showing Azure ML compliance analysis."""
    # Get Azure ML compliance results
    ml_summary = azure_data_service.get_dashboard_summary()
    compliance_files = azure_data_service.get_compliance_files()
    
    return render_template('main/ml_results.html',
                         title='ML Compliance Results',
                         ml_summary=ml_summary,
                         compliance_files=compliance_files)

@bp.route('/ml-results/<path:file_path>')
@login_required
def ml_file_detail(file_path):
    """Detailed view of a specific ML analysis file."""
    file_analysis = azure_data_service.get_file_analysis_summary(file_path)
    
    return render_template('main/ml_file_detail.html',
                         title='ML File Analysis',
                         file_analysis=file_analysis)

@bp.route('/api/ml-summary')
@login_required
def api_ml_summary():
    """API endpoint for ML summary data (for auto-refresh)."""
    ml_summary = azure_data_service.get_dashboard_summary()
    return jsonify(ml_summary)

@bp.route('/adls-raw-data')
@login_required
def adls_raw_data():
    """Show raw ADLS data exactly as it appears in the JSON files."""
    ml_summary = azure_data_service.get_dashboard_summary()
    
    return render_template('main/adls_raw_data.html',
                         title='ADLS Raw Data',
                         ml_summary=ml_summary,
                         azure_data_service=azure_data_service)

@bp.route('/adls-connection')
@login_required
def adls_connection():
    """Show ADLS connection status and setup instructions."""
    ml_summary = azure_data_service.get_dashboard_summary()
    
    return render_template('main/adls_connection.html',
                         title='ADLS Connection',
                         ml_summary=ml_summary)