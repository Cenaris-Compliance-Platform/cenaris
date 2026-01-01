# Deployment Runbook (Local → Render → Azure)

This runbook is tailored to this repo’s conventions:

- Local dev uses `FLASK_CONFIG=development` and reads the DB from `DEV_DATABASE_URL`.
- Hosted environments should use `FLASK_CONFIG=production` and read the DB from `DATABASE_URL`.

See also: ENV_SETUP.md

---

## 0) One-time prerequisites (applies everywhere)

### Secrets / credentials
- Never commit `.env` (already ignored).
- Prefer platform secret stores for hosted environments.

### SSL
Azure PostgreSQL commonly requires SSL. Use `?sslmode=require` in the connection string.

---

## 1) Local testing using Azure PostgreSQL (current setup)

### 1.1 Azure side
1. Create PostgreSQL server (Flexible Server recommended).
2. Create a database inside the server (example: `test`).
3. Networking (temporary for quick testing): allow your client IP.
   - Avoid `0.0.0.0–255.255.255.255` long-term.

### 1.2 Local `.env`
Set:
- `FLASK_CONFIG=development`
- `DEV_DATABASE_URL=postgresql://USER:PASS@HOST:5432/DBNAME?sslmode=require`

Note: URL-encode special chars in passwords (e.g. `@` → `%40`).

### 1.3 Run migrations (creates schema)
From the repo root with venv activated:

```powershell
python -m flask --app run:app db upgrade
```

### 1.4 Run app
```powershell
python run.py
```

### 1.5 Verify writes
Option A — app shell:
```powershell
python -m flask --app run:app shell
```

```python
from app.models import User
User.query.order_by(User.id.desc()).limit(10).all()
```

Option B — pgAdmin query:
```sql
SELECT id, email, role, email_verified
FROM users
ORDER BY id DESC
LIMIT 20;
```

---

## 2) Render deployment (staging/production on Render)

This repo already includes a Render blueprint: render.yaml.

### 2.1 Create the Render service
Option A: Use Blueprint (recommended)
- Render Dashboard → New → Blueprint → point to the repo

Option B: Manual
- Create a **Web Service**
- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn -w 4 -b 0.0.0.0:$PORT run:app`

### 2.2 Environment variables on Render
Minimum:
- `FLASK_CONFIG=production`
- `SECRET_KEY=...` (Render can generate)
- `DATABASE_URL=postgresql://...` (Render-managed DB or Azure Postgres)

If using Azure Storage:
- `AZURE_STORAGE_CONNECTION_STRING=...`
- `AZURE_CONTAINER_NAME=user-uploads` (documents/PDFs)
- `AZURE_LOGOS_CONTAINER_NAME=logos` (org logos/branding)

If enabling Turnstile:
- `TURNSTILE_SITE_KEY=...`
- `TURNSTILE_SECRET_KEY=...`
- Add your Render domain (e.g. `yourapp.onrender.com`) to the Turnstile allowed hostnames.

### 2.3 Database choice on Render
You can pick either:

**A) Render-managed Postgres**
- Use Render “PostgreSQL” add-on
- Render provides `DATABASE_URL`

**B) Azure PostgreSQL**
- Create a dedicated Azure database for staging (recommended)
- Put the Azure connection string into `DATABASE_URL`

### 2.4 Run migrations on Render
You must apply migrations against the deployed DB.

Options:
- Render Dashboard → Service → Shell → run:

```bash
python -m flask --app run:app db upgrade
```

Do this:
- once on first deploy
- again whenever you add a new migration

---

## 3) Azure hosting (later “official” deployment)

There are multiple valid Azure compute options. The simplest path is **Azure App Service**.

### 3.1 Azure App Service (recommended simplest)
1. Create an App Service (Linux) for Python.
2. Set application settings (Configuration) to include:
   - `FLASK_CONFIG=production`
   - `SECRET_KEY=...`
   - `DATABASE_URL=postgresql://...sslmode=require`
   - Storage + email + Turnstile vars as needed
3. Startup command:
   - `gunicorn -w 4 -b 0.0.0.0:8000 run:app`
   - Set `PORT=8000` (or `WEBSITES_PORT=8000`) if your plan requires it.

### 3.2 Apply migrations on Azure
Recommended approach:
- Run migrations as a one-off command during deployment (or from a pipeline step):

```bash
python -m flask --app run:app db upgrade
```

---

## 4) Environment variable mapping (cheat sheet)

Local dev:
- `FLASK_CONFIG=development`
- DB comes from `DEV_DATABASE_URL`

Hosted (Render/Azure):
- `FLASK_CONFIG=production`
- DB comes from `DATABASE_URL`

---

## 5) Operational notes

### 5.1 Turnstile local vs hosted domains
- Local: use `http://localhost:PORT` (not `127.0.0.1`) when Turnstile is enabled.
- Hosted: add the hosted domain to Turnstile allowed hostnames.

### 5.2 Firewall rules
- For short testing, AllowAll may be used temporarily.
- For anything longer than a quick test: restrict to your IP(s) or move to private networking.

### 5.3 Secret rotation
If secrets were shared in chat/logs:
- Rotate Azure Storage keys
- Rotate Turnstile secret
- Rotate `SECRET_KEY` for any environment exposed publicly
