from __future__ import annotations

from pathlib import Path
import html
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'docs' / 'NDIS_AI_DEMO_EXECUTIVE_SUMMARY.md'
TARGET = ROOT / 'docs' / 'NDIS_AI_DEMO_EXECUTIVE_SUMMARY.pdf'


def _inline_markup(text: str) -> str:
    escaped = html.escape((text or '').strip())
    escaped = re.sub(r'`([^`]+)`', r'<font name="Courier">\1</font>', escaped)
    escaped = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', escaped)
    return escaped


def build_pdf(source: Path = SOURCE, target: Path = TARGET) -> Path:
    if not source.exists():
        raise FileNotFoundError(f'Source markdown not found: {source}')

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'ExecTitle',
        parent=styles['Title'],
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        fontSize=20,
        leading=24,
        textColor=colors.HexColor('#0f3d75'),
        spaceAfter=18,
    )
    heading_style = ParagraphStyle(
        'ExecHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=colors.HexColor('#0f3d75'),
        spaceBefore=8,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        'ExecBody',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=15,
        spaceAfter=7,
    )
    list_style = ParagraphStyle(
        'ExecList',
        parent=body_style,
        leftIndent=18,
        firstLineIndent=-10,
        bulletIndent=8,
        spaceAfter=4,
    )

    story = []
    lines = source.read_text(encoding='utf-8').splitlines()

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            story.append(Spacer(1, 0.08 * inch))
            continue

        if line.startswith('# '):
            story.append(Paragraph(_inline_markup(line[2:]), title_style))
            continue

        if line.startswith('## '):
            story.append(Paragraph(_inline_markup(line[3:]), heading_style))
            continue

        ordered_match = re.match(r'^(\d+)\.\s+(.*)$', line)
        if ordered_match:
            bullet_text = f"{ordered_match.group(1)}. {_inline_markup(ordered_match.group(2))}"
            story.append(Paragraph(bullet_text, list_style))
            continue

        story.append(Paragraph(_inline_markup(line), body_style))

    target.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(target),
        pagesize=A4,
        leftMargin=0.8 * inch,
        rightMargin=0.8 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title='NDIS AI Demo Executive Summary',
        author='GitHub Copilot',
    )
    doc.build(story)
    return target


if __name__ == '__main__':
    output = build_pdf()
    print(output)