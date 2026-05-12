# Cenaris Deployment and Environment Setup

## What Runs In Production
The app is a Flask web application served by Gunicorn in production and deployed on Azure.

### Main runtime pieces
- `run.py` creates the Flask app and starts the local development server.
- `run:app` is the WSGI entry point used in deployment.
- `deploy.sh` rebuilds the Azure Container Registry image and restarts the Azure container app.
- Azure Container Registry stores the built application image.
- Azure Container Apps runs the web service.
- Azure Blob Storage holds uploaded documents and related assets.
- Azure PostgreSQL stores the application data.
- Azure OpenAI supports drafting and assistant flows when enabled.
- Azure Application Insights or log monitoring supports observability.

## Local Development Flow
1. Create and activate a virtual environment.
2. Install dependencies from `requirements.txt`.
3. Set local environment variables.
4. Run migrations with `flask db upgrade`.
5. Start the app with `python run.py`.

## Production Deployment Path

### Azure Container Deployment
The current deployment direction is Azure-first:
- `deploy.sh` builds a container image into Azure Container Registry.
- The script restarts the Azure container app after the image build.
- The app expects uploaded files to live in Azure Blob Storage.
- The app reads runtime settings from Azure environment variables.
- Production should run with `FLASK_CONFIG=production`.

## Environment Variables That Matter Most
- `FLASK_CONFIG` selects development or production settings.
- `SECRET_KEY` secures sessions and signed data.
- `DATABASE_URL` points to PostgreSQL in production.
- `AZURE_STORAGE_CONNECTION_STRING` and `AZURE_CONTAINER_NAME` control file uploads.
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `MICROSOFT_CLIENT_ID`, and `MICROSOFT_CLIENT_SECRET` enable OAuth.
- `MAIL_*` variables configure email delivery.
- `RATELIMIT_STORAGE_URI` configures rate-limit storage.
- `NDIS_RAG_CORPUS_PATH` points to the RAG corpus.

## Schema And App Startup
- The app factory lives in `app/__init__.py`.
- Migrations are managed by Alembic/Flask-Migrate.
- Production config enables secure cookies and stronger defaults.
- The app uses `ProxyFix` so reverse proxies preserve scheme and host correctly.

## Operational Notes
- Always run migrations before first start on a fresh database.
- Make sure storage, database, and OAuth credentials are present before enabling production traffic.
- Keep `SECRET_KEY` and database credentials private.
- Treat any missing env var as a deployment issue, not an app issue.

## What Is Not In This Repo
The repo does not currently ship a full IaC stack in this folder.
If you want infrastructure-as-code documentation later, it should be added as a separate doc so it stays aligned with the actual hosting target.