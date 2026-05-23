# NDIS RAG Build Artifacts

This folder stores generated artifacts used by the RAG indexing pipeline.

## Expected outputs
- `ndis_chunks.jsonl` -> chunked text corpus generated from regulatory PDF.

## Generate
- `flask --app run:app build-ndis-rag-corpus`

Note: this JSONL corpus is a pre-index step. You can feed it into Azure AI Search / pgvector / other vector stores.
