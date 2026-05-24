import os
import re
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

def convert_md_to_pdf(md_path, pdf_path):
    if not os.path.exists(md_path):
        print(f"Error: {md_path} not found.")
        return

    # Read markdown content
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Split into lines
    lines = content.split('\n')

    # Setup document template
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=54,
        leftMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    # Styles setup
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=colors.HexColor('#003366'),
        alignment=1, # Center
        spaceAfter=15
    )
    
    h1_style = ParagraphStyle(
        'H1',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#004488'),
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True
    )
    
    h2_style = ParagraphStyle(
        'H2',
        parent=styles['Heading3'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=15,
        textColor=colors.HexColor('#006699'),
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True
    )

    h3_style = ParagraphStyle(
        'H3',
        parent=styles['Heading4'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13,
        textColor=colors.HexColor('#555555'),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#222222'),
        spaceAfter=6
    )

    bullet_style = ParagraphStyle(
        'BulletItem',
        parent=body_style,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )

    code_style = ParagraphStyle(
        'CodeBlockText',
        fontName='Courier',
        fontSize=8.5,
        leading=10.5,
        textColor=colors.HexColor('#333333'),
        spaceAfter=0
    )

    quote_style = ParagraphStyle(
        'QuoteText',
        parent=body_style,
        fontName='Helvetica-Oblique',
        leftIndent=20,
        textColor=colors.HexColor('#555555')
    )

    table_header_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=10.5,
        textColor=colors.white
    )

    table_body_style = ParagraphStyle(
        'TableBody',
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#222222')
    )

    story = []
    
    in_code_block = False
    code_lines = []
    in_table = False
    table_rows = []

    # Clean and pre-format text
    def clean_text(text):
        # Replace Markdown bold/italic/code tags with HTML tags for ReportLab Paragraph
        text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # Replace inline markdown rules
        text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text) # Bold
        text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)     # Italic
        text = re.sub(r'`(.*?)`', r'<font face="Courier" color="#990033">\1</font>', text) # Code
        text = re.sub(r'\$\$(.*?)\$\$', r'<i>\1</i>', text) # Math blocks
        text = re.sub(r'\$(.*?)\$', r'<i>\1</i>', text)     # Math inline
        return text

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Handle Code Blocks
        if stripped.startswith('```'):
            if in_code_block:
                in_code_block = False
                # Add code block with gray background
                code_text = '\n'.join(code_lines)
                # Create paragraph
                p = Paragraph(f"<pre>{code_text}</pre>", code_style)
                # Add table block for styling (background & border)
                t = Table([[p]], colWidths=[doc.width])
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F8F9FA')),
                    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor('#E2E8F0')),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    ('LEFTPADDING', (0,0), (-1,-1), 8),
                    ('RIGHTPADDING', (0,0), (-1,-1), 8),
                ]))
                story.append(t)
                story.append(Spacer(1, 8))
                code_lines = []
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            # Escape code lines
            escaped = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            code_lines.append(escaped)
            i += 1
            continue

        # Handle Tables
        if stripped.startswith('|'):
            in_table = True
            table_rows.append(stripped)
            i += 1
            continue
        elif in_table:
            in_table = False
            # Render Table
            pdf_table = render_pdf_table(table_rows, table_header_style, table_body_style, doc.width)
            if pdf_table:
                story.append(pdf_table)
                story.append(Spacer(1, 8))
            table_rows = []

        if not stripped:
            i += 1
            continue

        # Handle Headings
        if stripped.startswith('# '):
            text = clean_text(stripped[2:])
            story.append(Paragraph(text, title_style))
            story.append(Spacer(1, 10))
        elif stripped.startswith('## '):
            text = clean_text(stripped[3:])
            story.append(Paragraph(text, h1_style))
        elif stripped.startswith('### '):
            text = clean_text(stripped[4:])
            story.append(Paragraph(text, h2_style))
        elif stripped.startswith('#### '):
            text = clean_text(stripped[5:])
            story.append(Paragraph(text, h3_style))
        # Handle List Items
        elif stripped.startswith('* ') or stripped.startswith('- '):
            text = clean_text(stripped[2:])
            story.append(Paragraph(f"&bull; {text}", bullet_style))
        # Handle Blockquotes
        elif stripped.startswith('>'):
            text = clean_text(stripped[1:].strip())
            story.append(Paragraph(text, quote_style))
            story.append(Spacer(1, 4))
        # Handle Horizontal Rules
        elif stripped.startswith('---'):
            # Simple line divider via a tiny table
            t = Table([['']], colWidths=[doc.width], rowHeights=[1])
            t.setStyle(TableStyle([
                ('LINEBELOW', (0,0), (-1,-1), 1, colors.HexColor('#E2E8F0')),
                ('BOTTOMPADDING', (0,0), (-1,-1), 0),
                ('TOPPADDING', (0,0), (-1,-1), 0),
            ]))
            story.append(Spacer(1, 8))
            story.append(t)
            story.append(Spacer(1, 8))
        # Normal Paragraph
        else:
            text = clean_text(stripped)
            story.append(Paragraph(text, body_style))
            story.append(Spacer(1, 4))

        i += 1

    # Build PDF
    doc.build(story)
    print(f"Success: PDF saved to {pdf_path}")

def render_pdf_table(raw_rows, header_style, body_style, max_width):
    rows = []
    for r in raw_rows:
        cleaned = [cell.strip() for cell in r.split('|')[1:-1]]
        if all(re.match(r'^:?-+:?$', cell) for cell in cleaned if cell):
            continue
        rows.append(cleaned)

    if not rows:
        return None

    # Calculate column widths
    col_count = len(rows[0])
    col_width = max_width / col_count
    col_widths = [col_width] * col_count

    table_data = []
    for r_idx, r in enumerate(rows):
        row_data = []
        for c_idx, cell in enumerate(r):
            # Wrap cell contents in Paragraph for autowrap
            if r_idx == 0:
                p = Paragraph(cell, header_style)
            else:
                p = Paragraph(cell, body_style)
            row_data.append(p)
        table_data.append(row_data)

    t = Table(table_data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#003366')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#CBD5E1')),
    ]))
    
    # Alternate row background styling
    for i in range(1, len(rows)):
        bg_color = colors.HexColor('#F8F9FA') if i % 2 == 1 else colors.white
        t.setStyle(TableStyle([('BACKGROUND', (0, i), (-1, i), bg_color)]))

    return t

if __name__ == '__main__':
    md_file = r'c:\Users\DELL\Desktop\cenaris\docs\AI_REVIEW_ENGINE_TECHNICAL_SPEC.md'
    pdf_file = r'c:\Users\DELL\Desktop\cenaris\docs\AI_REVIEW_ENGINE_TECHNICAL_SPEC.pdf'
    convert_md_to_pdf(md_file, pdf_file)
