# CCM (Cenaris Compliance Management)

CCM is a Flask web app for compliance document management with:

- Flask app-factory + Flask-Login
- SQLAlchemy + Alembic migrations (Flask-Migrate)
- Azure Storage (Blob/ADLS Gen2) for uploads
- Optional: SMTP email (forgot-password) + Google/Microsoft OAuth

## Documentation

- Environment + credentials setup (Azure PostgreSQL, Azure Storage, SMTP, OAuth): [ENV_SETUP.md](ENV_SETUP.md)

This README focuses on **how to run and work with the repo**.

## Quick Start (Windows)

### 1) Create & activate venv

```bat
python -m venv venv
venv\Scripts\activate
```

### 2) Install dependencies

```bat
pip install -r requirements.txt
```

### 3) Configure environment

- Copy `.env.example` → `.env`
- For local dev you can keep SQLite (default) via:
	- `FLASK_CONFIG=development`
	- `DEV_DATABASE_URL=sqlite:///compliance_dev.db`

### 4) Run migrations + start server

```bat
flask db upgrade
python run.py
```

## Useful Commands

### Reset local dev DB (clean slate)

```bat
flask reset-local-db
```

### Apply DB migrations

```bat
flask db upgrade
```

## Deployment Notes (High Level)

- Set `FLASK_CONFIG=production` and a strong `SECRET_KEY`
- Use Azure PostgreSQL via `DATABASE_URL` (see ENV_SETUP)
- Run `flask db upgrade` against production DB
- Configure Azure Storage env vars for uploads

For the step-by-step credential walkthrough, use: [ENV_SETUP.md](ENV_SETUP.md)
