# RAG Improvement Implementation Notes

Date: 2026-05-24

## What Changed

### Embedding Model Upgrade
- Switched the local embedding model from all-MiniLM-L6-v2 to BAAI/bge-large-en-v1.5.
- Added query instruction prefix for BGE and normalized embeddings for both corpus and queries.
- Updated embedding cache metadata to include model + normalization, so cache rebuilds automatically when the model changes.

### Pre-Validation Gates (Early Rejection)
- Added a single validation gate before scoring to reject invalid documents immediately.
- Rejects: very short docs, scanned/image-only PDFs, non-NDIS policies, and marketing content.
- Applies soft penalties for low-quality scans and partial templates.

### Citation Retrieval Improvements
- Increased RAG retrieval from top 3 to top 15, then filtered to 5-7 high-quality citations.
- Filtering enforces minimum score, action words, length, and terminology overlap.

### Gap-Focused RAG Query Construction
- Replaced keyword spam with structured, gap-focused queries.
- Identifies present topics and missing critical topics to form a more relevant query.

### Coverage Depth Weighting
- Coverage scoring now considers depth (procedural context) instead of pure term presence.

## What This Means
- Fewer false positives from non-policy documents.
- Stronger, more relevant citations when documents are text-based.
- Better handling of partial or low-quality PDFs by capping confidence.

## Current Test Status
- Good policy test doc is scanned, so it is being rejected by design.
- Marketing and generic docs are rejected as expected.
- Perfect policy test doc is missing.

## Docs Needed For Better Accuracy Testing
- A text-based NDIS policy or procedure PDF (not scanned), ideally 5-15 pages.
- A very strong "perfect" policy with clear procedures and responsibilities.
- One "good short" policy with clear but lighter detail.
- One partial template with placeholders but some filled content.
- One blank template (mostly placeholders).

## Files Changed (Code)
- app/services/document_analysis_service.py
- app/services/rag_query_service.py

## Supporting Test Artifacts
- docs/AI_road_map/week3_test_results.md
- scripts/run_week3_tests.py
