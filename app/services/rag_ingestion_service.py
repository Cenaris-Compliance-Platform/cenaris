from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import re
from typing import Iterable


@dataclass
class RagBuildResult:
    total_pages: int
    total_chunks: int
    output_path: str


class RagIngestionService:
    """Build chunked RAG corpus files from regulatory PDFs."""

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = re.sub(r'\s+', ' ', (text or '').strip())
        return normalized

    @classmethod
    def chunk_pages(
        cls,
        page_texts: Iterable[tuple[int, str]],
        *,
        chunk_chars: int = 1200,
        overlap_chars: int = 180,
    ) -> list[dict]:
        chunk_chars = max(300, int(chunk_chars or 1200))
        overlap_chars = max(0, min(int(overlap_chars or 0), chunk_chars // 2))

        chunks: list[dict] = []
        for page_number, raw_text in page_texts:
            text = cls._normalize_text(raw_text)
            if not text:
                continue

            start = 0
            while start < len(text):
                end = min(len(text), start + chunk_chars)
                chunk_text = text[start:end].strip()
                if not chunk_text:
                    break

                chunk_hash = hashlib.sha256(
                    f'{page_number}:{start}:{chunk_text}'.encode('utf-8')
                ).hexdigest()[:16]
                chunks.append(
                    {
                        'chunk_id': f'page{page_number}_off{start}_{chunk_hash}',
                        'page_number': int(page_number),
                        'char_start': int(start),
                        'char_end': int(end),
                        'text': chunk_text,
                    }
                )

                if end >= len(text):
                    break
                start = max(0, end - overlap_chars)

        return chunks

    def extract_pdf_page_texts(self, pdf_path: str) -> list[tuple[int, str]]:
        try:
            from pypdf import PdfReader
        except Exception as e:
            raise RuntimeError(
                'Missing dependency pypdf. Install it with: pip install pypdf'
            ) from e

        reader = PdfReader(pdf_path)
        pages: list[tuple[int, str]] = []
        for idx, page in enumerate(reader.pages, start=1):
            extracted = page.extract_text() or ''
            pages.append((idx, extracted))
        return pages

    def build_pdf_corpus(
        self,
        *,
        pdf_path: str,
        output_path: str,
        source_id: str = 'ndis-practice-standards',
        chunk_chars: int = 1200,
        overlap_chars: int = 180,
    ) -> RagBuildResult:
        if not pdf_path or not os.path.exists(pdf_path):
            raise FileNotFoundError(f'PDF not found: {pdf_path}')

        page_texts = self.extract_pdf_page_texts(pdf_path)
        chunks = self.chunk_pages(
            page_texts,
            chunk_chars=chunk_chars,
            overlap_chars=overlap_chars,
        )

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            for row in chunks:
                payload = {
                    'source_id': source_id,
                    'source_path': pdf_path,
                    **row,
                }
                f.write(json.dumps(payload, ensure_ascii=False) + '\n')

        return RagBuildResult(
            total_pages=len(page_texts),
            total_chunks=len(chunks),
            output_path=output_path,
        )


rag_ingestion_service = RagIngestionService()
