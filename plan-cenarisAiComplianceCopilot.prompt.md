## Plan: Cenaris AI Compliance Copilot (DRAFT)

No, one PDF is not enough. For what you want (“everything in the documentation”), V1 should be strict, citation-grounded, and AU-only hosted. The build should combine deterministic rules (for auditable scoring) + RAG (for natural-language Q&A with source evidence), not RAG alone. Your current app has good foundations for tenancy, RBAC, uploads, and reports, but no requirement-level knowledge model, no chunk/citation index, and no LLM orchestration yet. We should first normalize the master mapping spreadsheet as canonical, then layer retrieval, then AI workflows, then governance and export provenance.

**Steps**
1. Define canonical compliance schema (Requirement, Module, Outcome, Indicator, EvidenceBucket, Rule, Version) and map it to existing multi-tenant structures in [app/models.py](app/models.py#L27-L423) and [migrations](migrations).
2. Build ingestion pipeline for master mapping + standards docs (validation, dedupe, versioning, effective dates, change diff) and connect to existing data-service patterns in [app/services/azure_data_service.py](app/services/azure_data_service.py#L47-L566).
3. Add document intelligence pipeline (text extraction/OCR, chunking, metadata tagging, citation spans) on top of existing upload/storage flow in [app/upload/routes.py](app/upload/routes.py#L57-L257) and [app/services/azure_storage.py](app/services/azure_storage.py#L11-L456).
4. Implement hybrid retrieval (metadata filters + lexical + vector) with strict tenant partitioning and strict extractive answer policy.
5. Implement AI orchestration: query classification, retrieval, grounded answer synthesis, citation rendering, “insufficient evidence” behavior, and confidence output.
6. Implement deterministic gap scoring engine using your spreadsheet rules (System/Implementation/Workforce/Participant buckets + best-practice tier), then optional AI-assisted explanation text.
7. Add human review workflow (approve/reject mapping, override reason, audit trail) and extend RBAC beyond current roles from [app/services/rbac.py](app/services/rbac.py#L11-L174).
8. Build UX in existing main blueprint ([app/main/routes.py](app/main/routes.py#L1388-L2529)) for: Ask AI, requirement drill-down, evidence-to-requirement mapping, review queue, and audit-ready export provenance.
9. Upgrade reporting/export to include citation provenance (source doc, snippet, timestamp, reviewer, model version) via [app/services/report_generator.py](app/services/report_generator.py#L85-L492).
10. Add evaluation + ops: golden-question set, citation precision checks, hallucination guardrails, latency/cost dashboards, and fallback behavior.

**Verification**
- Ingestion tests: schema conformance, duplicate detection, version diff correctness.
- Retrieval tests: tenant isolation, top-k relevance, citation span correctness.
- AI tests: strict grounding (no citation => no definitive answer), deterministic outputs for scoring rules.
- UAT by persona (Owner, Compliance Manager, Executive Viewer) against current RBAC + new AI permissions.
- Export audit: randomly sample requirements and confirm every score/answer is traceable to evidence artifacts.

**What you need to do now**
- Provide: master mapping spreadsheet (full), official standards PDFs, and document-version history (effective dates/superseded mapping).
- Provide: 50–100 real provider evidence samples (de-identified) for evaluation.
- Confirm: AU-only model/vector hosting and retention requirements.
- Confirm: acceptance criteria (citation precision target, max hallucination tolerance, response SLA).

**Decisions captured**
- Scope: everything requested in your documentation (full workflow target).
- Grounding: strict extractive.
- Hosting: Australia-only processing.
- Data pack available: master mapping spreadsheet + practice standards PDF + core docs index.

If you want, I can next produce a phase-by-phase delivery roadmap (e.g., 12-week plan with milestones, team roles, and risk burn-down).