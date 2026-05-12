# Cenaris Product Architecture

## Purpose
Cenaris is a compliance management platform for evidence review, requirement mapping, AI-assisted analysis, and organization-level reporting.

## Main Building Blocks

### 1. Web Application
- Built with Flask.
- App entry points live in `app.py` and `run.py`.
- The Flask app uses blueprints for modular features.

### 2. Authentication and Organization Context
- Users sign in through the auth routes.
- The active organization is part of the user context.
- Most data access is filtered by organization.

### 3. Evidence Repository
- Users upload documents into the repository.
- Documents can be previewed, downloaded, tagged, and analyzed.
- The repository is the source for AI Review and compliance mapping.

### 4. AI Review Workspace
- Users select a repository document and ask a compliance question.
- The app extracts text, finds matching requirements, retrieves supporting citations, and returns a scored result.
- Reviewers can mark the result as false positive, false negative, or correct.

### 5. Compliance Requirements Workboard
- Documents are linked to compliance requirements.
- Requirement status is tracked through evidence links and assessments.
- This is the operational workboard for closing gaps.

### 6. RAG and Citation Layer
- The system uses a local NDIS corpus for supporting evidence.
- Retrieval combines document text, requirement context, and corpus citations.
- Citations help reduce unsupported or overconfident scores.

### 7. Analytics and Logging
- Usage and feedback events are stored for analysis.
- AI usage logs help track performance, latency, and reviewer feedback.
- This is used to improve scoring rules and detect weak spots.

### 8. Storage and Database
- Azure Blob Storage holds uploaded files.
- PostgreSQL stores users, organizations, documents, requirements, and AI usage events.
- Alembic migrations manage schema changes.

## Deployment Architecture

### Azure Runtime Target
The current deployment direction is Azure-based.

The application is designed to run as a stateless web service with these Azure pieces:
- Azure Container Registry for image builds and storage.
- Azure Container Apps for the web runtime.
- Azure Blob Storage for uploaded files and org assets.
- Azure PostgreSQL for the relational application data.
- Azure OpenAI for drafting and assistant flows when enabled.
- Azure Application Insights or platform logging for observability.

### Why This Shape Matters
- It keeps the web tier stateless.
- It separates application runtime from stored evidence.
- It allows storage, database, and AI services to scale independently.
- It fits the org-scoped security model used throughout the app.

### Production Request Flow
1. A user opens the Azure-hosted app.
2. Flask authenticates the request and resolves the organization context.
3. Uploaded files are read from Azure Blob Storage.
4. Business data is read from Azure PostgreSQL.
5. AI-assisted features call Azure OpenAI or the RAG layer as needed.
6. Logs and telemetry capture the important operational events.
7. The user receives the document, compliance, or admin response.

## End-to-End Flow
1. A user uploads a document.
2. The file is stored in blob storage and represented in the database.
3. AI Review extracts text from the file.
4. The app matches the document against NDIS requirements.
5. RAG retrieves evidence citations from the NDIS corpus.
6. Scoring rules produce a status and confidence.
7. Diagnostics explain why the score was assigned.
8. Reviewers can give feedback to record whether the result was right.
9. Feedback is stored for later analysis and threshold tuning.

## Operational Idea
The product is not a single AI model. It is a workflow system that combines:
- document management,
- compliance rule matching,
- evidence retrieval,
- review feedback,
- and org-level reporting.

That is why the scoring and diagnostics matter as much as the AI output itself.
