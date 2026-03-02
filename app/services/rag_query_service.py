from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import dataclass


@dataclass
class RagCitation:
    chunk_id: str
    source_id: str
    page_number: int | None
    score: float
    text: str


@dataclass
class RagQueryResult:
    answer: str
    citations: list[RagCitation]


class RagQueryService:
    """Simple lexical retriever over JSONL chunk corpus."""

    def __init__(self):
        self._cache_lock = threading.Lock()
        self._cache_path: str | None = None
        self._cache_mtime: float | None = None
        self._cache_rows: list[dict] = []

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", (text or "").lower())

    def _load_rows(self, corpus_path: str) -> list[dict]:
        if not corpus_path or not os.path.exists(corpus_path):
            raise FileNotFoundError(f'RAG corpus file not found: {corpus_path}')

        mtime = os.path.getmtime(corpus_path)
        with self._cache_lock:
            if (
                self._cache_path == corpus_path
                and self._cache_mtime is not None
                and self._cache_mtime == mtime
                and self._cache_rows
            ):
                return list(self._cache_rows)

            rows: list[dict] = []
            with open(corpus_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = (line or '').strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue

            self._cache_path = corpus_path
            self._cache_mtime = mtime
            self._cache_rows = rows
            return list(rows)

    def query(
        self,
        *,
        corpus_path: str,
        query_text: str,
        requirement_id: str | None = None,
        top_k: int = 3,
    ) -> RagQueryResult:
        query_text = (query_text or '').strip()
        requirement_id = (requirement_id or '').strip()
        if not query_text and not requirement_id:
            raise ValueError('query_text or requirement_id is required')

        terms = self._tokenize(query_text)
        if requirement_id:
            terms.extend(self._tokenize(requirement_id))

        rows = self._load_rows(corpus_path)
        scored: list[tuple[float, dict]] = []

        for row in rows:
            text = str(row.get('text') or '')
            if not text:
                continue

            text_lower = text.lower()
            score = 0.0
            for term in terms:
                if not term:
                    continue
                score += float(text_lower.count(term))

            if requirement_id and requirement_id.lower() in text_lower:
                score += 8.0

            if score > 0:
                scored.append((score, row))

        scored.sort(key=lambda item: item[0], reverse=True)

        top_k = max(1, min(int(top_k or 3), 10))
        selected = scored[:top_k]

        citations: list[RagCitation] = []
        for score, row in selected:
            text = str(row.get('text') or '').strip()
            snippet = text if len(text) <= 480 else (text[:480].rstrip() + '…')
            citations.append(
                RagCitation(
                    chunk_id=str(row.get('chunk_id') or ''),
                    source_id=str(row.get('source_id') or 'ndis-practice-standards'),
                    page_number=(int(row.get('page_number')) if row.get('page_number') is not None else None),
                    score=round(float(score), 3),
                    text=snippet,
                )
            )

        if citations:
            answer = 'Retrieved relevant NDIS source passages for this query. Review citations below before final compliance judgment.'
        else:
            answer = 'No relevant NDIS passages were retrieved. Refine the query or include requirement ID.'

        return RagQueryResult(answer=answer, citations=citations)


rag_query_service = RagQueryService()
