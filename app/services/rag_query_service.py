from __future__ import annotations

import json
import logging
import os
import re
import threading
from collections import Counter
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger(__name__)


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
    retrieval_mode: str = 'lexical'  # 'hybrid' | 'lexical'


class RagQueryService:
    """
    Hybrid semantic + lexical retriever over JSONL chunk corpus.

    Retrieval strategy
    ------------------
    1. Semantic score  – cosine similarity between sentence-transformer
       embeddings of the query and each chunk.  Captures meaning even
       when the exact words differ (e.g. "participant choice" ↔ "autonomy").
    2. Lexical score   – normalised term-frequency count (original approach).
    3. Final score     = SEMANTIC_WEIGHT × semantic + LEXICAL_WEIGHT × lexical_norm
       + topic-overlap bonus + requirement_id exact-match boost.

    Embeddings are pre-computed once and cached to disk next to the corpus
    file (``<corpus>_embeddings.npy`` + ``<corpus>_embeddings_meta.json``).
    On subsequent calls the cache is validated by corpus file mtime, so
    changing the JSONL automatically triggers a re-encode.

    If ``sentence-transformers`` is not installed the service falls back
    transparently to pure-lexical scoring (same behaviour as before).
    """

    EMBEDDING_MODEL = 'all-MiniLM-L6-v2'
    # Weights must sum to 1.0
    SEMANTIC_WEIGHT: float = 0.60
    LEXICAL_WEIGHT: float  = 0.40

    _TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
        'rights': ('rights', 'privacy', 'dignity', 'consent', 'confidentiality', 'choice'),
        'complaints': ('complaint', 'complaints', 'feedback', 'resolution', 'grievance'),
        'service_agreements': ('service agreement', 'service agreements', 'agreement', 'supports'),
        'support_planning': ('support plan', 'support planning', 'care plan', 'assessment', 'goals', 'preferences'),
        'governance': ('governance', 'risk management', 'quality management', 'information management', 'incident management'),
        'culture': ('culture', 'cultural', 'diversity', 'inclusive', 'inclusion', 'values', 'beliefs'),
        'behaviour_support': ('behaviour support', 'behavior support', 'restrictive practice', 'restrictive practices'),
    }

    def __init__(self):
        # Corpus text cache
        self._rows_lock = threading.Lock()
        self._rows_path: str | None = None
        self._rows_mtime: float | None = None
        self._rows: list[dict] = []

        # Embedding model (lazy-loaded once)
        self._model_lock = threading.Lock()
        self._model = None          # SentenceTransformer instance or None
        self._model_checked = False  # True once we've attempted to load

        # Embedding matrix cache (in-memory)
        self._emb_lock = threading.Lock()
        self._emb_path: str | None = None
        self._emb_mtime: float | None = None
        self._emb_matrix: np.ndarray | None = None

    # ------------------------------------------------------------------
    # Sentence-transformer helpers
    # ------------------------------------------------------------------

    def _get_model(self):
        """Lazy-load the embedding model exactly once per process."""
        with self._model_lock:
            if self._model_checked:
                return self._model
            self._model_checked = True
            try:
                from sentence_transformers import SentenceTransformer  # type: ignore
                self._model = SentenceTransformer(self.EMBEDDING_MODEL)
                logger.info('RAG: loaded embedding model %s', self.EMBEDDING_MODEL)
            except Exception as exc:
                logger.warning('RAG: sentence-transformers not available (%s); using lexical-only fallback.', exc)
                self._model = None
            return self._model

    @staticmethod
    def _embedding_cache_paths(corpus_path: str) -> tuple[str, str]:
        base = os.path.splitext(corpus_path)[0]
        return base + '_embeddings.npy', base + '_embeddings_meta.json'

    def _load_embed_matrix(self, corpus_path: str, rows: list[dict]) -> np.ndarray | None:
        """
        Return an (N, D) float32 embedding matrix for *rows*.
        Loads from disk cache when valid, otherwise encodes and saves.
        """
        model = self._get_model()
        if model is None:
            return None

        corpus_mtime = os.path.getmtime(corpus_path)
        npy_path, meta_path = self._embedding_cache_paths(corpus_path)

        with self._emb_lock:
            # 1. In-memory hit
            if (
                self._emb_path == corpus_path
                and self._emb_mtime == corpus_mtime
                and self._emb_matrix is not None
                and self._emb_matrix.shape[0] == len(rows)
            ):
                return self._emb_matrix

            # 2. Disk cache hit
            if os.path.exists(npy_path) and os.path.exists(meta_path):
                try:
                    with open(meta_path, 'r', encoding='utf-8') as fh:
                        meta = json.load(fh)
                    if (
                        abs(float(meta.get('corpus_mtime', 0)) - corpus_mtime) < 1.0
                        and int(meta.get('chunk_count', 0)) == len(rows)
                    ):
                        matrix = np.load(npy_path).astype(np.float32)
                        self._emb_path = corpus_path
                        self._emb_mtime = corpus_mtime
                        self._emb_matrix = matrix
                        logger.info('RAG: loaded embedding cache (%d chunks) from disk.', len(rows))
                        return matrix
                except Exception as exc:
                    logger.warning('RAG: embedding cache corrupt, will recompute (%s)', exc)

            # 3. Compute embeddings
            try:
                logger.info('RAG: computing embeddings for %d chunks (first run or corpus changed)…', len(rows))
                texts = [str(r.get('text') or '') for r in rows]
                matrix = model.encode(
                    texts,
                    convert_to_numpy=True,
                    show_progress_bar=False,
                    batch_size=32,
                ).astype(np.float32)
                # Persist to disk
                np.save(npy_path, matrix)
                with open(meta_path, 'w', encoding='utf-8') as fh:
                    json.dump({'corpus_mtime': corpus_mtime, 'chunk_count': len(rows)}, fh)
                self._emb_path = corpus_path
                self._emb_mtime = corpus_mtime
                self._emb_matrix = matrix
                logger.info('RAG: embeddings saved to %s', npy_path)
                return matrix
            except Exception as exc:
                logger.exception('RAG: failed to compute embeddings (%s); using lexical-only.', exc)
                return None

    @staticmethod
    def _cosine_sim(matrix: np.ndarray, query_vec: np.ndarray) -> np.ndarray:
        """Return cosine similarities between each row of *matrix* and *query_vec*."""
        row_norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        row_norms = np.where(row_norms == 0, 1e-9, row_norms)
        q_norm = float(np.linalg.norm(query_vec)) or 1e-9
        return (matrix / row_norms) @ (query_vec / q_norm)

    # ------------------------------------------------------------------
    # Lexical helpers (unchanged from original)
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", (text or "").lower())

    @classmethod
    def _phrase_candidates(cls, text: str) -> list[str]:
        cleaned = re.sub(r'[^a-z0-9\s-]+', ' ', (text or '').lower())
        phrases: list[str] = []
        seen: set[str] = set()
        for raw_part in re.split(r'[\n,;:()]+', cleaned):
            part = re.sub(r'\s+', ' ', (raw_part or '').strip())
            if not part or len(cls._tokenize(part)) < 2 or part in seen:
                continue
            seen.add(part)
            phrases.append(part)
        return phrases[:8]

    @classmethod
    def _row_search_text(cls, row: dict) -> str:
        parts = [
            str(row.get('title') or ''),
            str(row.get('heading') or ''),
            str(row.get('requirement_id') or ''),
            str(row.get('module_name') or ''),
            str(row.get('standard_name') or ''),
            str(row.get('source_id') or ''),
            str(row.get('text') or ''),
        ]
        return ' '.join(part for part in parts if part).lower()

    @classmethod
    def _topic_labels(cls, text: str) -> set[str]:
        lower = (text or '').lower()
        labels = set()
        for label, keywords in cls._TOPIC_KEYWORDS.items():
            if any(keyword in lower for keyword in keywords):
                labels.add(label)
        return labels

    # ------------------------------------------------------------------
    # Corpus loading (file-mtime cached)
    # ------------------------------------------------------------------

    def _load_rows(self, corpus_path: str) -> list[dict]:
        if not corpus_path or not os.path.exists(corpus_path):
            raise FileNotFoundError(f'RAG corpus file not found: {corpus_path}')

        mtime = os.path.getmtime(corpus_path)
        with self._rows_lock:
            if (
                self._rows_path == corpus_path
                and self._rows_mtime is not None
                and self._rows_mtime == mtime
                and self._rows
            ):
                return list(self._rows)

            rows: list[dict] = []
            with open(corpus_path, 'r', encoding='utf-8') as fh:
                for line in fh:
                    line = (line or '').strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except Exception:
                        continue

            self._rows_path = corpus_path
            self._rows_mtime = mtime
            self._rows = rows
            return list(rows)

    # ------------------------------------------------------------------
    # Public query interface
    # ------------------------------------------------------------------

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

        rows = self._load_rows(corpus_path)
        search_text = ' '.join(part for part in [query_text, requirement_id] if part).strip()
        terms = self._tokenize(search_text)
        unique_terms = list(dict.fromkeys(term for term in terms if term))
        phrases = self._phrase_candidates(search_text)
        if requirement_id:
            terms.extend(self._tokenize(requirement_id))
        query_topics = self._topic_labels(search_text)

        # ---- Lexical scores ----------------------------------------
        lex_raw: list[float] = []
        for row in rows:
            row_search_text = self._row_search_text(row)
            row_terms = Counter(self._tokenize(row_search_text))
            matched_terms = 0
            term_score = 0.0
            for term in unique_terms:
                term_hits = int(row_terms.get(term, 0))
                if term_hits <= 0:
                    continue
                matched_terms += 1
                term_score += min(float(term_hits), 3.0)

            coverage_bonus = (float(matched_terms) / float(len(unique_terms))) if unique_terms else 0.0
            phrase_bonus = sum(1.8 for phrase in phrases if phrase and phrase in row_search_text)
            s = term_score + coverage_bonus + phrase_bonus
            lex_raw.append(s)

        max_lex = max(lex_raw) if lex_raw else 0.0
        lex_norm = [s / max_lex if max_lex > 0 else 0.0 for s in lex_raw]

        # ---- Semantic scores (hybrid) -------------------------------
        sem_norm: list[float] | None = None
        retrieval_mode = 'lexical'
        emb_matrix = self._load_embed_matrix(corpus_path, rows)
        if emb_matrix is not None and len(emb_matrix) == len(rows):
            model = self._get_model()
            if model is not None:
                try:
                    q_vec = model.encode(
                        [search_text],
                        convert_to_numpy=True,
                        show_progress_bar=False,
                    )[0].astype(np.float32)
                    sims = self._cosine_sim(emb_matrix, q_vec)  # in [-1, 1]
                    sem_norm = ((sims + 1.0) / 2.0).tolist()    # shift to [0, 1]
                    retrieval_mode = 'hybrid'
                except Exception as exc:
                    logger.warning('RAG: semantic scoring failed (%s); using lexical-only.', exc)

        # ---- Combine scores ----------------------------------------
        scored: list[tuple[float, dict]] = []
        for i, row in enumerate(rows):
            lex = lex_norm[i]
            if sem_norm is not None:
                base = self.SEMANTIC_WEIGHT * float(sem_norm[i]) + self.LEXICAL_WEIGHT * lex
            else:
                base = lex

            # Topic-overlap bonus (relative, works for both modes)
            row_search_text = self._row_search_text(row)
            row_topics = self._topic_labels(row_search_text)
            if query_topics and row_topics:
                overlap = len(query_topics & row_topics)
                base += 0.12 * float(overlap) if overlap > 0 else -0.04

            # Exact requirement_id boost
            if requirement_id and requirement_id.lower() in row_search_text:
                base += 0.40

            if base > 0:
                scored.append((base, row))

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

        return RagQueryResult(answer=answer, citations=citations, retrieval_mode=retrieval_mode)


rag_query_service = RagQueryService()
