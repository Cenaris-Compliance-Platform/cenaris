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

    _VALID_OUTPUT_MODES = {'template', 'template_plus', 'full_draft'}

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
        output_mode: str = 'full_draft',
        audience: str = 'Leadership team and frontline workers',
        policy_tone: str = 'Plain-English',
        strictness: str = 'Balanced',
        organization_size: str = 'Small provider',
        context_brief: str = '',
    ) -> PolicyDraftResult:
        policy_type = (policy_type or 'Policy').strip()
        organization_name = (organization_name or 'Organisation').strip()
        requirement_id = (requirement_id or 'N/A').strip()
        user_goal = (user_goal or '').strip()
        output_mode = (output_mode or 'full_draft').strip().lower()
        if output_mode not in self._VALID_OUTPUT_MODES:
            output_mode = 'full_draft'

        audience = (audience or 'Leadership team and frontline workers').strip()
        policy_tone = (policy_tone or 'Plain-English').strip()
        strictness = (strictness or 'Balanced').strip()
        organization_size = (organization_size or 'Small provider').strip()
        context_brief = (context_brief or '').strip()

        citation_lines: list[str] = []
        for idx, citation in enumerate(citations or [], start=1):
            source = citation.get('source_id') or 'ndis-practice-standards'
            page = citation.get('page_number')
            score = citation.get('score')
            text = (citation.get('text') or '').strip()
            page_label = f'page {page}' if page else 'page n/a'
            citation_lines.append(f'[{idx}] {source}, {page_label}, score={score}: {text}')

        prompt_excerpt = self._read_prompt_excerpt(prompt_path)

        metadata = [
            f'Organisation: {organization_name}',
            f'Requirement reference: {requirement_id}',
            f'Audience: {audience}',
            f'Tone: {policy_tone}',
            f'Strictness: {strictness}',
            f'Organisation size profile: {organization_size}',
        ]

        body = [f'# {policy_type} Draft', '', *metadata, '']

        if output_mode == 'template':
            body.extend([
                '## Purpose (fill in)',
                '- [Replace with a one-paragraph objective for this policy.]',
                '',
                '## Scope (fill in)',
                '- [Define which teams, roles, and services are covered.]',
                '',
                '## Roles and Responsibilities (fill in)',
                '- Policy owner: [Name/role]',
                '- Approver: [Name/role]',
                '- Responsible teams: [Teams]',
                '',
                '## Required Controls Template',
                '- Control 1: [Control description] | Evidence: [Artifact name] | Owner: [Role] | Frequency: [Cadence]',
                '- Control 2: [Control description] | Evidence: [Artifact name] | Owner: [Role] | Frequency: [Cadence]',
                '- Control 3: [Control description] | Evidence: [Artifact name] | Owner: [Role] | Frequency: [Cadence]',
                '',
                '## Review and Improvement (fill in)',
                '- Review cadence: [e.g., quarterly]',
                '- Escalation path: [Who is notified and when]',
                '- Corrective action tracking method: [Tool/register]',
            ])
        elif output_mode == 'template_plus':
            body.extend([
                '## Purpose',
                f'This template outlines the minimum structure for a {policy_type.lower()} aligned to NDIS expectations.',
                '',
                '## Scope',
                f'This policy applies to all workers and contractors involved in services for {organization_name}.',
                '',
                '## Core Policy Clauses (example wording)',
                '- The organisation defines and maintains clear controls with named owners and review cadence.',
                '- Required evidence must be complete, current, and auditable at any review point.',
                '- Non-conformities are logged, escalated, remediated, and closed with accountability.',
                '',
                '## Procedure Skeleton',
                '1. Identify required evidence and map each artifact to the relevant requirement.',
                '2. Capture evidence according to approved templates and retention controls.',
                '3. Perform periodic checks and address identified gaps through corrective actions.',
                '',
                '## Placeholders You Must Complete',
                '- Policy owner: [Insert role]',
                '- Approval authority: [Insert role]',
                '- Review frequency: [Insert cadence]',
                '- Evidence register location: [Insert location]',
            ])
        else:
            body.extend([
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
            ])

        body.extend([
            '',
            '## Request Notes',
            user_goal or 'No additional notes provided.',
        ])

        if context_brief:
            body.extend([
                '',
                '## Context Brief',
                context_brief,
            ])

        body.extend([
            '',
            '## Retrieved NDIS Citations',
            *(citation_lines if citation_lines else ['No citations were retrieved for this request.']),
        ])

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
