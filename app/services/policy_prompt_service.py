from __future__ import annotations

import os
import re


class PolicyPromptService:
    """Compile source-of-truth guidance into a reusable system prompt file."""

    @staticmethod
    def _clean_text(text: str) -> str:
        text = (text or '').replace('\r', '\n')
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def _read_docx(self, file_path: str) -> str:
        try:
            from docx import Document
        except Exception as e:
            raise RuntimeError(
                'Missing dependency python-docx. Install it with: pip install python-docx'
            ) from e

        doc = Document(file_path)
        paragraphs = [p.text.strip() for p in doc.paragraphs if (p.text or '').strip()]
        return '\n\n'.join(paragraphs)

    def read_source_text(self, source_path: str) -> str:
        if not source_path or not os.path.exists(source_path):
            raise FileNotFoundError(f'Prompt source not found: {source_path}')

        lower = source_path.lower()
        if lower.endswith('.docx'):
            return self._clean_text(self._read_docx(source_path))

        with open(source_path, 'r', encoding='utf-8') as f:
            return self._clean_text(f.read())

    def compile_prompt_file(self, *, source_path: str, output_path: str) -> str:
        source_text = self.read_source_text(source_path)
        compiled = (
            'You are a strict NDIS compliance auditor assistant.\n'
            'Use only provided regulatory evidence and do not invent requirements.\n'
            'When evidence is insufficient, say so explicitly.\n\n'
            '=== NDIS AUDITOR RUBRIC (SOURCE OF TRUTH) ===\n'
            f'{source_text}\n'
        )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(compiled)

        return output_path


policy_prompt_service = PolicyPromptService()
