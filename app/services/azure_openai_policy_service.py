from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any

import requests


@dataclass
class AzurePolicyDraftResponse:
    draft_text: str
    disclaimer: str
    deployment: str
    usage: dict[str, int]


class AzureOpenAIPolicyService:
    """Generate policy drafts from Azure OpenAI chat completions."""

    @staticmethod
    def is_configured(config: dict[str, Any]) -> bool:
        return bool(
            (config.get('AZURE_OPENAI_ENDPOINT') or '').strip()
            and (config.get('AZURE_OPENAI_API_KEY') or '').strip()
            and (
                (config.get('AZURE_OPENAI_CHAT_DEPLOYMENT_WRITER') or '').strip()
                or (config.get('AZURE_OPENAI_CHAT_DEPLOYMENT') or '').strip()
            )
        )

    @staticmethod
    def select_deployment(config: dict[str, Any]) -> str:
        ai_env = (config.get('AI_ENVIRONMENT') or 'development').strip().lower()
        mini = (config.get('AZURE_OPENAI_CHAT_DEPLOYMENT_MINI') or '').strip()
        writer = (config.get('AZURE_OPENAI_CHAT_DEPLOYMENT_WRITER') or '').strip()
        legacy = (config.get('AZURE_OPENAI_CHAT_DEPLOYMENT') or '').strip()

        if ai_env != 'production':
            return mini or writer or legacy
        return writer or mini or legacy

    @staticmethod
    def _read_prompt_excerpt(prompt_path: str | None) -> str:
        if not prompt_path:
            return ''
        if not os.path.exists(prompt_path):
            return ''
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                text = (f.read() or '').strip()
            return text[:4000]
        except Exception:
            return ''

    def generate_policy_draft(
        self,
        *,
        config: dict[str, Any],
        policy_type: str,
        organization_name: str,
        requirement_id: str,
        user_goal: str,
        citations: list[dict],
        prompt_path: str | None,
    ) -> AzurePolicyDraftResponse:
        endpoint = (config.get('AZURE_OPENAI_ENDPOINT') or '').strip().rstrip('/')
        api_key = (config.get('AZURE_OPENAI_API_KEY') or '').strip()
        deployment = self.select_deployment(config)
        api_version = (config.get('AZURE_OPENAI_API_VERSION') or '2024-10-21').strip()
        timeout_seconds = int(config.get('AZURE_OPENAI_TIMEOUT_SECONDS') or 30)
        max_output_tokens = int(config.get('AZURE_OPENAI_POLICY_MAX_OUTPUT_TOKENS') or 1400)

        if not endpoint or not api_key or not deployment:
            raise RuntimeError('Azure OpenAI is not fully configured')

        url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

        citation_lines = []
        for idx, citation in enumerate(citations or [], start=1):
            source = citation.get('source_id') or 'ndis-practice-standards'
            page = citation.get('page_number')
            score = citation.get('score')
            text = (citation.get('text') or '').strip()
            page_label = f'page {page}' if page else 'page n/a'
            citation_lines.append(f'[{idx}] {source}, {page_label}, score={score}: {text}')

        prompt_excerpt = self._read_prompt_excerpt(prompt_path)

        system_prompt = (
            'You are a strict NDIS policy drafting assistant. '
            'Do not invent legal requirements. '
            'Use provided citations only. '
            'If citations are insufficient, explicitly state uncertainty. '
            'Return valid JSON only matching this schema: '
            '{"draft_text": string, "disclaimer": string}. '
            'Keep draft_text concise and implementation-ready. '
            'Do not include markdown fences.'
        )
        if prompt_excerpt:
            system_prompt += f"\n\nNDIS AUDITOR RUBRIC EXCERPT:\n{prompt_excerpt}"

        user_prompt = (
            f"Policy type: {policy_type}\n"
            f"Organisation: {organization_name}\n"
            f"Requirement reference: {requirement_id or 'N/A'}\n"
            f"User goal/context: {user_goal or 'N/A'}\n\n"
            f"Citations:\n" + ('\n'.join(citation_lines) if citation_lines else 'No citations available.') +
            "\n\nReturn JSON with keys draft_text and disclaimer only. "
            "Use this disclaimer verbatim: "
            "'Draft generated for compliance support only. This is not legal advice or certification. A qualified reviewer must approve before use.'"
        )

        response = requests.post(
            url,
            headers={
                'Content-Type': 'application/json',
                'api-key': api_key,
            },
            json={
                'messages': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                'temperature': 0.2,
                'max_tokens': max_output_tokens,
                'response_format': {
                    'type': 'json_schema',
                    'json_schema': {
                        'name': 'policy_draft_response',
                        'strict': True,
                        'schema': {
                            'type': 'object',
                            'properties': {
                                'draft_text': {'type': 'string'},
                                'disclaimer': {'type': 'string'},
                            },
                            'required': ['draft_text', 'disclaimer'],
                            'additionalProperties': False,
                        },
                    },
                },
            },
            timeout=timeout_seconds,
        )

        if response.status_code >= 400:
            text = (response.text or '').strip()
            raise RuntimeError(f'Azure OpenAI error ({response.status_code}): {text[:300]}')

        payload = response.json() or {}
        choices = payload.get('choices') or []
        if not choices:
            raise RuntimeError('Azure OpenAI returned no choices')

        message = (choices[0] or {}).get('message') or {}
        content = (message.get('content') or '').strip()
        if not content:
            raise RuntimeError('Azure OpenAI returned empty draft content')

        try:
            parsed = json.loads(content)
        except Exception as exc:
            raise RuntimeError('Azure OpenAI returned non-JSON content') from exc

        draft_text = (parsed.get('draft_text') or '').strip()
        disclaimer = (parsed.get('disclaimer') or '').strip()
        if not draft_text or not disclaimer:
            raise RuntimeError('Azure OpenAI JSON missing required fields')

        usage_payload = payload.get('usage') or {}
        usage = {
            'prompt_tokens': int(usage_payload.get('prompt_tokens') or 0),
            'completion_tokens': int(usage_payload.get('completion_tokens') or 0),
            'total_tokens': int(usage_payload.get('total_tokens') or 0),
        }

        return AzurePolicyDraftResponse(
            draft_text=draft_text,
            disclaimer=disclaimer,
            deployment=deployment,
            usage=usage,
        )


azure_openai_policy_service = AzureOpenAIPolicyService()
