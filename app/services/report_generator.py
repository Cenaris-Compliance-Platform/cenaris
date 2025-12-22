"""
Report generation service for compliance reports.
Generates PDF reports for Gap Analysis, Accreditation Plan, and Audit Pack.
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.platypus import Image as RLImage
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from datetime import datetime
import io
import logging

logger = logging.getLogger(__name__)


def safe_datetime_format(dt, format_str='%d %B %Y'):
    """Safely format datetime object."""
    if dt is None:
        return datetime.now().strftime(format_str)
    if isinstance(dt, str):
        return dt
    try:
        return dt.strftime(format_str)
    except:
        return datetime.now().strftime(format_str)


def format_file_size(size_bytes):
    """Return a human-readable file size string."""
    if not size_bytes:
        return "Unknown"
    size = float(size_bytes)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


class ReportGenerator:
    """Generate compliance reports in PDF format."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Section header
        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1976d2'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        ))
        
        # Subsection
        self.styles.add(ParagraphStyle(
            name='SubSection',
            parent=self.styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#424242'),
            spaceAfter=6,
            fontName='Helvetica-Bold'
        ))
    
    def generate_gap_analysis_report(self, org_data, gap_data, summary_stats):
        """Generate Gap Analysis Report PDF."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        
        # Title
        story.append(Paragraph("Gap Analysis Report", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.2*inch))
        
        # Organization Information
        story.append(Paragraph("Organisation Information", self.styles['SectionHeader']))
        org_info = [
            ['Organisation:', org_data.get('name', 'N/A')],
            ['ABN:', org_data.get('abn', 'N/A')],
            ['Address:', org_data.get('address', 'N/A')],
            ['Primary Contact:', org_data.get('contact_name', 'N/A')],
            ['Email:', org_data.get('email', 'N/A')],
            ['Accreditation Framework:', org_data.get('framework', 'N/A')],
            ['Export Date:', datetime.now().strftime('%d %B %Y')]
        ]
        
        org_table = Table(org_info, colWidths=[2*inch, 4.5*inch])
        org_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e3f2fd')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        story.append(org_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Executive Summary
        story.append(Paragraph("1. Executive Summary", self.styles['SectionHeader']))
        
        story.append(Paragraph("<b>Purpose of the Assessment:</b>", self.styles['Normal']))
        story.append(Paragraph(
            "This gap analysis report identifies compliance gaps and provides recommendations "
            "for achieving full accreditation readiness.",
            self.styles['Normal']
        ))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph("<b>Frameworks Reviewed:</b>", self.styles['Normal']))
        frameworks = ', '.join([item['requirement_name'] for item in gap_data]) if gap_data else 'N/A'
        story.append(Paragraph(frameworks, self.styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph("<b>Overall Readiness Score:</b>", self.styles['Normal']))
        score = summary_stats.get('compliance_percentage', 0)
        story.append(Paragraph(f"{score}%", self.styles['Normal']))
        story.append(Spacer(1, 0.1*inch))
        
        # Key Statistics
        stats_data = [
            ['Metric', 'Count'],
            ['Total Requirements', str(summary_stats.get('total', 0))],
            ['Requirements Met', str(summary_stats.get('met', 0))],
            ['Pending Review', str(summary_stats.get('pending', 0))],
            ['Gaps Identified', str(summary_stats.get('not_met', 0))]
        ]
        
        stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
        stats_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')])
        ]))
        story.append(stats_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Assessment Methodology
        story.append(Paragraph("2. Assessment Methodology", self.styles['SectionHeader']))
        story.append(Paragraph(
            "This assessment was conducted using automated compliance analysis tools, "
            "reviewing uploaded evidence against framework requirements.",
            self.styles['Normal']
        ))
        story.append(Spacer(1, 0.1*inch))
        
        story.append(Paragraph("<b>Rating Scale:</b>", self.styles['Normal']))
        rating_data = [
            ['Rating', 'Description'],
            ['Complete', 'Requirements met consistently with documented evidence'],
            ['Needs Review', 'Partial or inconsistent implementation'],
            ['Missing', 'No evidence found or requirement not addressed']
        ]
        
        rating_table = Table(rating_data, colWidths=[1.5*inch, 4.5*inch])
        rating_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4caf50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        story.append(rating_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Detailed Gap Analysis
        story.append(PageBreak())
        story.append(Paragraph("3. Detailed Gap Analysis", self.styles['SectionHeader']))
        
        if gap_data:
            gap_table_data = [['Framework', 'Status', 'Score', 'Evidence']]
            
            for item in gap_data:
                gap_table_data.append([
                    Paragraph(item['requirement_name'], self.styles['Normal']),
                    item['status'],
                    f"{item['completion_percentage']}%",
                    Paragraph(item.get('supporting_evidence', 'N/A'), self.styles['Normal'])
                ])
            
            gap_table = Table(gap_table_data, colWidths=[2*inch, 1.2*inch, 0.8*inch, 2.5*inch])
            gap_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')])
            ]))
            story.append(gap_table)
        else:
            story.append(Paragraph("No gap data available.", self.styles['Normal']))
        
        story.append(Spacer(1, 0.3*inch))
        
        # Recommendations
        story.append(PageBreak())
        story.append(Paragraph("4. Recommendations", self.styles['SectionHeader']))
        
        recommendations = []
        for item in gap_data:
            if item['status'] in ['Missing', 'Needs Review']:
                recommendations.append([
                    item['requirement_name'],
                    'High' if item['status'] == 'Missing' else 'Medium',
                    f"Address {item['status'].lower()} status for {item['requirement_name']}"
                ])
        
        if recommendations:
            rec_table_data = [['Area', 'Priority', 'Recommended Action']]
            rec_table_data.extend(recommendations)
            
            rec_table = Table(rec_table_data, colWidths=[2*inch, 1*inch, 3.5*inch])
            rec_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ff9800')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP')
            ]))
            story.append(rec_table)
        else:
            story.append(Paragraph("All requirements are met. No immediate actions required.", self.styles['Normal']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def generate_accreditation_plan(self, org_data, gap_data, summary_stats):
        """Generate Accreditation Plan PDF."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        
        # Title
        story.append(Paragraph("Accreditation Plan", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.2*inch))
        
        # Organization Information (same as gap analysis)
        story.append(Paragraph("1. Provider & Accreditation Summary", self.styles['SectionHeader']))
        
        provider_info = [
            ['Field', 'Entry'],
            ['Organisation', org_data.get('name', 'N/A')],
            ['Accreditation Type', org_data.get('framework', 'N/A')],
            ['Audit Type', org_data.get('audit_type', 'Initial')],
            ['Date Prepared', datetime.now().strftime('%d %B %Y')],
            ['Readiness Score', f"{summary_stats.get('compliance_percentage', 0)}%"]
        ]
        
        provider_table = Table(provider_info, colWidths=[2.5*inch, 4*inch])
        provider_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('BACKGROUND', (0, 1), (0, -1), colors.HexColor('#e3f2fd')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        story.append(provider_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Readiness Overview
        story.append(Paragraph("2. Readiness Overview", self.styles['SectionHeader']))
        
        readiness_data = [
            ['Category', '% Complete', 'Key Gaps', 'Priority'],
            ['Overall Compliance', f"{summary_stats.get('compliance_percentage', 0)}%", 
             str(summary_stats.get('not_met', 0)), 'High' if summary_stats.get('not_met', 0) > 0 else 'Low']
        ]
        
        # Add framework-specific data
        for item in gap_data[:5]:  # Top 5 frameworks
            priority = 'High' if item['status'] == 'Missing' else 'Medium' if item['status'] == 'Needs Review' else 'Low'
            readiness_data.append([
                item['requirement_name'],
                f"{item['completion_percentage']}%",
                item['status'],
                priority
            ])
        
        readiness_table = Table(readiness_data, colWidths=[2.5*inch, 1.2*inch, 1.5*inch, 1.3*inch])
        readiness_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4caf50')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')])
        ]))
        story.append(readiness_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Action Plan
        story.append(PageBreak())
        story.append(Paragraph("3. Action Plan", self.styles['SectionHeader']))
        
        action_data = [['Task', 'Framework', 'Owner', 'Due Date', 'Status']]
        
        for item in gap_data:
            if item['status'] in ['Missing', 'Needs Review']:
                due_date = datetime.now().strftime('%d %B %Y')
                action_data.append([
                    f"Address {item['requirement_name']}",
                    item['requirement_name'],
                    'Compliance Manager',
                    due_date,
                    'Not Started'
                ])
        
        if len(action_data) > 1:
            action_table = Table(action_data, colWidths=[2.2*inch, 1.5*inch, 1.3*inch, 1*inch, 1*inch])
            action_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ff9800')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP')
            ]))
            story.append(action_table)
        else:
            story.append(Paragraph("No actions required. All requirements are met.", self.styles['Normal']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer
    
    def generate_audit_pack(self, org_data, gap_data, summary_stats, documents):
        """Generate Audit Pack Export PDF."""
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        
        # Title
        story.append(Paragraph("Audit Pack Export", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.2*inch))
        
        # Organization Information
        story.append(Paragraph("Organisation Information", self.styles['SectionHeader']))
        org_info = [
            ['Organisation:', org_data.get('name', 'N/A')],
            ['ABN:', org_data.get('abn', 'N/A')],
            ['Address:', org_data.get('address', 'N/A')],
            ['Primary Contact:', org_data.get('contact_name', 'N/A')],
            ['Email:', org_data.get('email', 'N/A')],
            ['Accreditation Framework:', org_data.get('framework', 'N/A')],
            ['Export Date:', datetime.now().strftime('%d %B %Y')]
        ]
        
        org_table = Table(org_info, colWidths=[2*inch, 4.5*inch])
        org_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e3f2fd')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        story.append(org_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Readiness Summary
        story.append(Paragraph("Readiness Summary", self.styles['SectionHeader']))
        story.append(Paragraph(
            f"<b>Overall Readiness:</b> {summary_stats.get('compliance_percentage', 0)}%",
            self.styles['Normal']
        ))
        story.append(Spacer(1, 0.1*inch))
        
        # Framework Summary Table
        framework_summary = [
            ['Framework', 'Readiness %', 'Compliant', 'Gaps'],
        ]
        
        for item in gap_data:
            status_count = '1 Complete' if item['status'] == 'Complete' else '1 Gap'
            framework_summary.append([
                item['requirement_name'],
                f"{item['completion_percentage']}%",
                '1' if item['status'] == 'Complete' else '0',
                '0' if item['status'] == 'Complete' else '1'
            ])
        
        framework_table = Table(framework_summary, colWidths=[2.5*inch, 1.5*inch, 1.2*inch, 1.3*inch])
        framework_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1976d2')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')])
        ]))
        story.append(framework_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Evidence Repository
        story.append(PageBreak())
        story.append(Paragraph("Evidence Repository", self.styles['SectionHeader']))
        
        if documents:
            doc_data = [['Document Name', 'Size', 'Upload Date', 'Status']]
            
            for document in documents[:20]:  # Limit to 20 documents
                doc_data.append([
                    Paragraph(document.filename, self.styles['Normal']),
                    format_file_size(document.file_size),
                    safe_datetime_format(document.uploaded_at, '%d %b %Y'),
                    'Active' if document.is_active else 'Inactive'
                ])
            
            doc_table = Table(doc_data, colWidths=[3*inch, 1*inch, 1.2*inch, 1.3*inch])
            doc_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4caf50')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')])
            ]))
            story.append(doc_table)
        else:
            story.append(Paragraph("No documents in evidence repository.", self.styles['Normal']))
        
        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer


# Global instance
report_generator = ReportGenerator()
