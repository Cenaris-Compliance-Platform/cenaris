from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class PolicyDraftResult:
    draft_text: str
    disclaimer: str


class PolicyDraftService:
    """Deterministic policy draft composer using retrieved citations."""

    DISCLAIMER = (
        'Draft generated for compliance support only. This is not legal advice or certification. '
        'A qualified reviewer must approve before use.'
    )

    @staticmethod
    def _read_prompt_excerpt(prompt_path: str | None) -> str:
        if not prompt_path:
            return ''
        if not os.path.exists(prompt_path):
            return ''
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                text = (f.read() or '').strip()
            if not text:
                return ''
            excerpt = text[:1200]
            return excerpt
        except Exception:
            return ''

    def build_draft(
        self,
        *,
        policy_type: str,
        organization_name: str,
        requirement_id: str,
        user_goal: str,
        citations: list[dict],
        prompt_path: str | None,
    ) -> PolicyDraftResult:
        policy_type = (policy_type or 'Policy').strip()
        organization_name = (organization_name or 'Organisation').strip()
        requirement_id = (requirement_id or 'N/A').strip()
        user_goal = (user_goal or '').strip()

        citation_lines: list[str] = []
        for idx, citation in enumerate(citations or [], start=1):
            source = citation.get('source_id') or 'ndis-practice-standards'
            page = citation.get('page_number')
            score = citation.get('score')
            text = (citation.get('text') or '').strip()
            page_label = f'page {page}' if page else 'page n/a'
            citation_lines.append(f'[{idx}] {source}, {page_label}, score={score}: {text}')

        prompt_excerpt = self._read_prompt_excerpt(prompt_path)

        body = [
            f'# {policy_type} Draft',
            '',
            f'Organisation: {organization_name}',
            f'Requirement reference: {requirement_id}',
            '',
            '## Purpose',
            f'This draft sets out controls for {policy_type.lower()} aligned to NDIS expectations and internal governance.',
            '',
            '## Scope',
            'Applies to all relevant personnel, records, systems, and evidence processes connected to this requirement.',
            '',
            '## Policy Statements',
            '- Roles and responsibilities are defined and reviewed regularly.',
            '- Required evidence is created, retained, and auditable.',
            '- Non-conformities are identified, corrected, and tracked.',
            '',
            '## Procedures',
            '1. Capture and maintain required evidence artifacts.',
            '2. Perform periodic internal checks against requirement obligations.',
            '3. Escalate and remediate any identified compliance gaps.',
            '',
            '## Monitoring and Review',
            '- Review frequency follows mapped compliance settings.',
            '- Outcomes and corrective actions are documented with ownership.',
            '',
            '## Notes from Request',
            user_goal or 'No additional notes provided.',
            '',
            '## Retrieved NDIS Citations',
            *(citation_lines if citation_lines else ['No citations were retrieved for this request.']),
        ]

        if prompt_excerpt:
            body.extend([
                '',
                '## Auditor Rubric Excerpt',
                prompt_excerpt,
            ])

        body.extend([
            '',
            '## Disclaimer',
            self.DISCLAIMER,
        ])

        return PolicyDraftResult(
            draft_text='\n'.join(body),
            disclaimer=self.DISCLAIMER,
        )


policy_draft_service = PolicyDraftService()
