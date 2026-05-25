# RAG Improvement Implementation Notes

Date: 2026-05-24

<<<<<<< HEAD
## Current State Summary
- The app uses two different AI components:
	- Embedding model for RAG search: `BAAI/bge-large-en-v1.5` in production and when explicitly selected.
	- LLM for narrative output: `gpt-4o-mini` via OpenRouter / Azure OpenAI depending on config.
- For local development, the app can temporarily fall back to `sentence-transformers/all-MiniLM-L6-v2` unless `RAG_EMBEDDING_MODEL` is set.
- The warmup harness and app startup now honor `RAG_EMBEDDING_MODEL`, `RAG_EMBED_CACHE_DIR`, `HF_HOME`, and `RAG_WARMUP`.

## Current Issue Observed Locally
- The UI message `Analysis failed` is not a model-crash message by itself. It usually means the `/api/ai/demo/analyze` endpoint returned `success: false` or a non-200 response.
- The main failure path we traced was the AI Review endpoint always trying to re-download the stored document before analysis. If that download fails, the frontend shows a generic failure state.
- The second bottleneck was request-time hybrid retrieval: when the embedding cache is missing or still warming, the request could block while computing embeddings for the whole corpus, which is long enough to hit the browser timeout.
- The embedding build path now uses batched corpus encoding and a non-blocking request-time lock fallback, so AI Review can return lexical results immediately while the warmup thread finishes hybrid embeddings in the background.
- The route now prefers cached `document.extracted_text` first and only falls back to Azure blob download when cached text is missing.
- RAG request paths now fall back to lexical-only retrieval immediately if embeddings are not yet cached, while the warmup process builds the hybrid cache in the background.
- Additional logging has been added so the next failure should show whether the blocker is org access, storage download, extraction, retrieval mode, or LLM fallback.

=======
>>>>>>> origin/Preview
## What Changed

### Embedding Model Upgrade
- Switched the local embedding model from all-MiniLM-L6-v2 to BAAI/bge-large-en-v1.5.
- Added query instruction prefix for BGE and normalized embeddings for both corpus and queries.
- Updated embedding cache metadata to include model + normalization, so cache rebuilds automatically when the model changes.

<<<<<<< HEAD
### Local Model Selection Behavior
- The code now prefers a smaller development model only when `FLASK_CONFIG=development` and no explicit `RAG_EMBEDDING_MODEL` is provided.
- You can force the previous model at any time with `RAG_EMBEDDING_MODEL=BAAI/bge-large-en-v1.5`.
- The warmup script was updated to respect the same environment variable so the selected model is consistent across warmup and runtime.

=======
>>>>>>> origin/Preview
### Pre-Validation Gates (Early Rejection)
- Added a single validation gate before scoring to reject invalid documents immediately.
- Rejects: very short docs, scanned/image-only PDFs, non-NDIS policies, and marketing content.
- Applies soft penalties for low-quality scans and partial templates.

### Citation Retrieval Improvements
- Increased RAG retrieval from top 3 to top 15, then filtered to 5-7 high-quality citations.
- Filtering enforces minimum score, action words, length, and terminology overlap.

<<<<<<< HEAD
### OOM / Startup Stability Fix
- Corpus embedding generation now runs in small batches instead of one large encode call.
- Request-time retrieval no longer waits for the embedding build lock; it returns lexical-only results until the cache is ready.

=======
>>>>>>> origin/Preview
### Gap-Focused RAG Query Construction
- Replaced keyword spam with structured, gap-focused queries.
- Identifies present topics and missing critical topics to form a more relevant query.

### Coverage Depth Weighting
- Coverage scoring now considers depth (procedural context) instead of pure term presence.

## What This Means
- Fewer false positives from non-policy documents.
- Stronger, more relevant citations when documents are text-based.
- Better handling of partial or low-quality PDFs by capping confidence.
<<<<<<< HEAD
- If the app still shows `Analysis failed`, the next place to inspect is the route log line from `ai_demo_analyze_api`, but the likely culprit is now the request timing out before warmup completes.
- On a cold start, the first result may be lexical-only until the embedding cache finishes building.
=======
>>>>>>> origin/Preview

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
<<<<<<< HEAD
- app/main/routes.py
=======
>>>>>>> origin/Preview

## Supporting Test Artifacts
- docs/AI_road_map/week3_test_results.md
- scripts/run_week3_tests.py
