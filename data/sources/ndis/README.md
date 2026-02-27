# NDIS Source Files (Authoritative Inputs)

## Folder split
- `regulatory/` -> primary regulatory PDFs for RAG chunking
- `mapping/` -> structured rule/scoring mapping spreadsheets (loaded into PostgreSQL)
- `reference/` -> supporting guidance docs used for prompt/rubric and roadmap context
- `archive_raw/` -> untouched original drops (optional)

## Current staged files
- `regulatory/ndis-practice-standards-and-quality-indicators.pdf`
- `mapping/MASTER Cenaris_NDIS_Audit_Master_Mapping_v1.xlsx`
- `reference/FINAL Cenaris NDIS Compliance Source of Truth.docx`
- `reference/NDIS Core Documents Index.docx`
- `reference/Cenaris User Cases.docx`

## Ingestion commands
- Build RAG corpus JSONL from PDF:
  - `flask --app run:app build-ndis-rag-corpus`
- Import mapping into DB:
  - `flask --app run:app import-master-mapping --file-path "data/sources/ndis/mapping/MASTER Cenaris_NDIS_Audit_Master_Mapping_v1.xlsx" --org-id <ORG_ID> --version-label v1.0`
- Compile system prompt template from source-of-truth:
  - `flask --app run:app compile-ndis-policy-prompt`
