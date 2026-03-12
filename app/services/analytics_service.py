from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import io
from statistics import median
import zipfile
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app import db
from app.models import (
    ComplianceFrameworkVersion,
    ComplianceRequirement,
    Document,
    LoginEvent,
    OrganizationMembership,
    OrganizationRequirementAssessment,
    RequirementEvidenceLink,
)
from sqlalchemy import or_


_COMPLIANT_FLAGS = {'OK', 'Mature'}
_GAP_FLAGS = {'Critical gap', 'High risk gap'}


class AnalyticsService:
    """Aggregate organisation analytics for dashboard visualisation and exports."""

    def _utcnow(self) -> datetime:
        return datetime.now(timezone.utc)

    def _to_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _weekly_labels(self, weeks: int = 12) -> list[datetime]:
        now = self._utcnow()
        monday_this_week = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        start = monday_this_week - timedelta(weeks=max(1, int(weeks)) - 1)
        return [start + timedelta(weeks=idx) for idx in range(max(1, int(weeks)))]

    def _week_key(self, dt: datetime) -> datetime:
        base = self._to_utc(dt) or self._utcnow()
        return (base - timedelta(days=base.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)

    def build_dashboard_payload(self, *, organization_id: int, weeks: int = 12) -> dict:
        org_id = int(organization_id)
        week_points = self._weekly_labels(weeks=weeks)
        week_keys = {w: idx for idx, w in enumerate(week_points)}

        assessments = (
            OrganizationRequirementAssessment.query
            .filter_by(organization_id=org_id)
            .all()
        )

        requirements = (
            db.session.query(
                ComplianceRequirement.id,
                ComplianceFrameworkVersion.id,
                ComplianceFrameworkVersion.scheme,
                ComplianceFrameworkVersion.version_label,
            )
            .join(ComplianceFrameworkVersion, ComplianceFrameworkVersion.id == ComplianceRequirement.framework_version_id)
            .filter(
                ComplianceFrameworkVersion.is_active.is_(True),
                or_(
                    ComplianceFrameworkVersion.organization_id.is_(None),
                    ComplianceFrameworkVersion.organization_id == org_id,
                ),
            )
            .all()
        )
        requirement_to_framework: dict[int, tuple[int, str]] = {}
        for req_id, framework_id, scheme, version in requirements:
            requirement_to_framework[int(req_id)] = (int(framework_id), f"{(scheme or 'NDIS').strip()} {(version or 'v1').strip()}")

        documents = (
            Document.query
            .filter_by(organization_id=org_id, is_active=True)
            .all()
        )

        member_ids = [
            int(m.user_id)
            for m in OrganizationMembership.query.filter_by(organization_id=org_id, is_active=True).all()
            if m.user_id is not None
        ]

        login_events = []
        if member_ids:
            login_events = (
                LoginEvent.query
                .filter(LoginEvent.user_id.in_(member_ids))
                .all()
            )

        evidence_links = (
            RequirementEvidenceLink.query
            .filter_by(organization_id=org_id)
            .all()
        )

        total_requirements = max(len(assessments), len(requirements))
        compliant_count = sum(1 for row in assessments if (row.computed_flag or '').strip() in _COMPLIANT_FLAGS)
        gap_count = sum(1 for row in assessments if (row.computed_flag or '').strip() in _GAP_FLAGS)
        compliance_rate = round((compliant_count / max(1, len(assessments))) * 100, 1) if assessments else 0.0

        status_counts = {
            'Critical gap': 0,
            'High risk gap': 0,
            'OK': 0,
            'Mature': 0,
            'Unassessed': 0,
        }
        for row in assessments:
            flag = (row.computed_flag or '').strip()
            if flag in status_counts:
                status_counts[flag] += 1
            else:
                status_counts['Unassessed'] += 1

        framework_bucket: dict[int, dict] = defaultdict(lambda: {
            'framework': 'Unknown',
            'total': 0,
            'compliant': 0,
            'gaps': 0,
        })
        for row in assessments:
            mapping = requirement_to_framework.get(int(row.requirement_id))
            if not mapping:
                continue
            framework_id, framework_label = mapping
            bucket = framework_bucket[framework_id]
            bucket['framework'] = framework_label
            bucket['total'] += 1
            if (row.computed_flag or '').strip() in _COMPLIANT_FLAGS:
                bucket['compliant'] += 1
            if (row.computed_flag or '').strip() in _GAP_FLAGS:
                bucket['gaps'] += 1

        framework_analytics = []
        for item in framework_bucket.values():
            total = int(item['total'])
            compliant = int(item['compliant'])
            item['compliance_rate'] = round((compliant / max(1, total)) * 100, 1) if total else 0.0
            framework_analytics.append(item)
        framework_analytics.sort(key=lambda x: x['framework'])

        compliance_updates = [0 for _ in week_points]
        compliant_updates = [0 for _ in week_points]
        for row in assessments:
            updated = self._to_utc(row.updated_at)
            if not updated:
                continue
            key = self._week_key(updated)
            idx = week_keys.get(key)
            if idx is None:
                continue
            compliance_updates[idx] += 1
            if (row.computed_flag or '').strip() in _COMPLIANT_FLAGS:
                compliant_updates[idx] += 1

        compliance_percent_by_week = []
        for idx in range(len(week_points)):
            total = compliance_updates[idx]
            percent = round((compliant_updates[idx] / max(1, total)) * 100, 1) if total else 0.0
            compliance_percent_by_week.append(percent)

        uploads_by_week = [0 for _ in week_points]
        upload_content_types: dict[str, int] = defaultdict(int)
        uploader_activity: dict[int, int] = defaultdict(int)
        for doc in documents:
            uploaded = self._to_utc(doc.uploaded_at)
            if uploaded:
                key = self._week_key(uploaded)
                idx = week_keys.get(key)
                if idx is not None:
                    uploads_by_week[idx] += 1
            ctype = ((doc.content_type or 'unknown').split(';')[0] or 'unknown').strip() or 'unknown'
            upload_content_types[ctype] += 1
            if doc.uploaded_by:
                uploader_activity[int(doc.uploaded_by)] += 1

        login_success_by_week = [0 for _ in week_points]
        login_failure_by_week = [0 for _ in week_points]
        active_users_last_30_days: set[int] = set()
        thirty_days_ago = self._utcnow() - timedelta(days=30)

        for event in login_events:
            created = self._to_utc(event.created_at)
            if created:
                key = self._week_key(created)
                idx = week_keys.get(key)
                if idx is not None:
                    if bool(event.success):
                        login_success_by_week[idx] += 1
                    else:
                        login_failure_by_week[idx] += 1
                if created >= thirty_days_ago and event.user_id:
                    active_users_last_30_days.add(int(event.user_id))

        for user_id, _count in uploader_activity.items():
            active_users_last_30_days.add(int(user_id))

        gap_rows_last_90_days = [
            row for row in assessments
            if self._to_utc(row.updated_at) and self._to_utc(row.updated_at) >= (self._utcnow() - timedelta(days=90))
        ]
        closed_gap_rows = [row for row in gap_rows_last_90_days if (row.computed_flag or '').strip() in _COMPLIANT_FLAGS]
        gap_closure_rate = round((len(closed_gap_rows) / max(1, len(gap_rows_last_90_days))) * 100, 1) if gap_rows_last_90_days else 0.0

        first_link_by_requirement: dict[int, datetime] = {}
        for link in evidence_links:
            linked = self._to_utc(link.linked_at)
            if not linked:
                continue
            req_id = int(link.requirement_id)
            current = first_link_by_requirement.get(req_id)
            if current is None or linked < current:
                first_link_by_requirement[req_id] = linked

        durations_days: list[float] = []
        for row in assessments:
            if (row.computed_flag or '').strip() not in _COMPLIANT_FLAGS:
                continue
            assessed = self._to_utc(row.last_assessed_at or row.updated_at)
            first_link = first_link_by_requirement.get(int(row.requirement_id))
            if not assessed or not first_link:
                continue
            delta = (assessed - first_link).total_seconds() / 86400.0
            if delta >= 0:
                durations_days.append(delta)

        avg_time_to_compliance_days = round((sum(durations_days) / len(durations_days)), 1) if durations_days else None
        median_time_to_compliance_days = round(float(median(durations_days)), 1) if durations_days else None

        week_labels = [w.strftime('%Y-%m-%d') for w in week_points]

        return {
            'summary': {
                'total_requirements': int(total_requirements),
                'assessed_requirements': int(len(assessments)),
                'compliant_requirements': int(compliant_count),
                'gap_requirements': int(gap_count),
                'compliance_rate': compliance_rate,
                'document_count': int(len(documents)),
                'active_users_30d': int(len(active_users_last_30_days)),
                'gap_closure_rate_90d': gap_closure_rate,
                'avg_time_to_compliance_days': avg_time_to_compliance_days,
                'median_time_to_compliance_days': median_time_to_compliance_days,
            },
            'status_distribution': status_counts,
            'framework_analytics': framework_analytics,
            'trends': {
                'labels': week_labels,
                'compliance_updates': compliance_updates,
                'compliant_updates': compliant_updates,
                'compliance_percent': compliance_percent_by_week,
                'uploads': uploads_by_week,
                'login_success': login_success_by_week,
                'login_failure': login_failure_by_week,
            },
            'uploads': {
                'content_type_distribution': dict(sorted(upload_content_types.items(), key=lambda kv: kv[1], reverse=True)),
            },
        }

    def build_excel(self, payload: dict) -> io.BytesIO:
        summary_rows = [
            ['metric', 'value'],
            *[[key, value] for key, value in (payload.get('summary') or {}).items()],
        ]

        framework_rows = [['framework', 'total', 'compliant', 'gaps', 'compliance_rate']]
        for row in payload.get('framework_analytics') or []:
            framework_rows.append([
                row.get('framework') or 'Unknown',
                row.get('total') or 0,
                row.get('compliant') or 0,
                row.get('gaps') or 0,
                row.get('compliance_rate') or 0,
            ])

        status_rows = [
            ['status', 'count'],
            *[[key, value] for key, value in (payload.get('status_distribution') or {}).items()],
        ]

        trends = payload.get('trends') or {}
        trends_rows = [['week', 'compliance_updates', 'compliant_updates', 'compliance_percent', 'uploads', 'login_success', 'login_failure']]
        labels = trends.get('labels') or []
        for idx, label in enumerate(labels):
            trends_rows.append([
                label,
                (trends.get('compliance_updates') or [])[idx] if idx < len(trends.get('compliance_updates') or []) else 0,
                (trends.get('compliant_updates') or [])[idx] if idx < len(trends.get('compliant_updates') or []) else 0,
                (trends.get('compliance_percent') or [])[idx] if idx < len(trends.get('compliance_percent') or []) else 0,
                (trends.get('uploads') or [])[idx] if idx < len(trends.get('uploads') or []) else 0,
                (trends.get('login_success') or [])[idx] if idx < len(trends.get('login_success') or []) else 0,
                (trends.get('login_failure') or [])[idx] if idx < len(trends.get('login_failure') or []) else 0,
            ])

        upload_types_rows = [
            ['content_type', 'count'],
            *[[key, value] for key, value in ((payload.get('uploads') or {}).get('content_type_distribution') or {}).items()],
        ]

        sheets = [
            ('Summary', summary_rows),
            ('Framework', framework_rows),
            ('Status', status_rows),
            ('Trends', trends_rows),
            ('Uploads', upload_types_rows),
        ]
        return self._build_minimal_xlsx(sheets)

    def _build_minimal_xlsx(self, sheets: list[tuple[str, list[list]]]) -> io.BytesIO:
        buffer = io.BytesIO()

        with zipfile.ZipFile(buffer, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                '[Content_Types].xml',
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                    '<Default Extension="xml" ContentType="application/xml"/>'
                    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
                    '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
                    + ''.join(
                        f'<Override PartName="/xl/worksheets/sheet{i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                        for i, _ in enumerate(sheets)
                    )
                    + '</Types>'
                ),
            )

            zf.writestr(
                '_rels/.rels',
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
                    '</Relationships>'
                ),
            )

            zf.writestr(
                'xl/workbook.xml',
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                    '<sheets>'
                    + ''.join(
                        f'<sheet name="{escape(name[:31])}" sheetId="{i + 1}" r:id="rId{i + 1}"/>'
                        for i, (name, _rows) in enumerate(sheets)
                    )
                    + '</sheets></workbook>'
                ),
            )

            zf.writestr(
                'xl/_rels/workbook.xml.rels',
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                    + ''.join(
                        f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i + 1}.xml"/>'
                        for i, _ in enumerate(sheets)
                    )
                    + f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                    + '</Relationships>'
                ),
            )

            zf.writestr(
                'xl/styles.xml',
                (
                    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                    '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
                    '<fills count="1"><fill><patternFill patternType="none"/></fill></fills>'
                    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
                    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                    '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
                    '</styleSheet>'
                ),
            )

            for idx, (_name, rows) in enumerate(sheets, start=1):
                zf.writestr(f'xl/worksheets/sheet{idx}.xml', self._sheet_xml(rows))

        buffer.seek(0)
        return buffer

    def _sheet_xml(self, rows: list[list]) -> str:
        body = []
        for r_index, row in enumerate(rows, start=1):
            cells = []
            for c_index, value in enumerate(row, start=1):
                cell_ref = f'{self._col_name(c_index)}{r_index}'
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    cells.append(f'<c r="{cell_ref}"><v>{value}</v></c>')
                else:
                    cells.append(f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(str(value if value is not None else ""))}</t></is></c>')
            body.append(f'<row r="{r_index}">{"".join(cells)}</row>')
        return (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(body)}</sheetData>'
            '</worksheet>'
        )

    def _col_name(self, index: int) -> str:
        name = ''
        value = int(index)
        while value > 0:
            value, remainder = divmod(value - 1, 26)
            name = chr(65 + remainder) + name
        return name

    def build_pdf(self, payload: dict, *, organization_name: str) -> io.BytesIO:
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        story = []

        story.append(Paragraph('Analytics Dashboard Export', styles['Title']))
        story.append(Paragraph(f'Organisation: {organization_name}', styles['Normal']))
        story.append(Paragraph(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M")}', styles['Normal']))
        story.append(Spacer(1, 16))

        summary = payload.get('summary') or {}
        summary_rows = [['Metric', 'Value']]
        summary_rows.extend([[k.replace('_', ' ').title(), str(v)] for k, v in summary.items()])
        summary_table = Table(summary_rows, colWidths=[250, 200])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f4e78')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')]),
        ]))
        story.append(Paragraph('Summary', styles['Heading2']))
        story.append(summary_table)
        story.append(Spacer(1, 16))

        framework_rows = [['Framework', 'Total', 'Compliant', 'Gaps', 'Compliance Rate %']]
        for row in payload.get('framework_analytics') or []:
            framework_rows.append([
                row.get('framework') or 'Unknown',
                str(row.get('total') or 0),
                str(row.get('compliant') or 0),
                str(row.get('gaps') or 0),
                str(row.get('compliance_rate') or 0),
            ])
        framework_table = Table(framework_rows, colWidths=[170, 70, 70, 60, 90])
        framework_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2f6b9a')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f7fa')]),
        ]))
        story.append(Paragraph('Framework Analytics', styles['Heading2']))
        story.append(framework_table)

        doc.build(story)
        buffer.seek(0)
        return buffer


analytics_service = AnalyticsService()
