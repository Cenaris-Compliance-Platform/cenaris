# CCM (Cenaris Compliance Management)

CCM is a Flask web app for compliance document management with:

- Flask app-factory + Flask-Login
- SQLAlchemy + Alembic migrations (Flask-Migrate)
- Azure Storage (Blob/ADLS Gen2) for uploads
- Optional: SMTP email (forgot-password) + Google/Microsoft OAuth

## Link: https://cenaris-preview.onrender.com/dashboard

## Documentation

- Environment + credentials setup (Azure PostgreSQL, Azure Storage, SMTP, OAuth): [ENV_SETUP.md](ENV_SETUP.md)
- Public API guide (auth, versioning, tenant isolation, security): [docs/PUBLIC_API.md](docs/PUBLIC_API.md)
- Postman collection for `/api/v1`: [docs/Cenaris-Public-API.postman_collection.json](docs/Cenaris-Public-API.postman_collection.json)

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

## QA Checklist (Document + Notifications)

Use this checklist after each release affecting uploads, reports, or notifications.

### Pre-check

```bat
venv\Scripts\activate
python -m flask db upgrade
python run.py
```

### Document Management

1. **Bulk upload**
	- Go to **Evidence Repository**.
	- Click **Bulk Upload** and select 2+ files.
	- Confirm all files appear in the table.

2. **Tagging + filtering**
	- Open a document via **View Details**.
	- Add tags (example: `policy, ndis`).
	- Return to **Evidence Repository** and filter by tag.
	- Confirm matching documents appear.

3. **Search + advanced filters**
	- Search by filename/tag text.
	- Apply `Type`, `Date from/to`, and `Min/Max bytes` filters.
	- Confirm result list updates correctly.

4. **Preview (secure)**
	- Click **Preview** for a PDF/image/text file.
	- Confirm file opens inline.
	- Confirm unauthorized user cannot access another org’s preview/download URL.

5. **Bulk download ZIP**
	- Select multiple docs with checkboxes.
	- Click **Download Selected (ZIP)**.
	- Extract ZIP and verify expected filenames/content.

### Notifications

1. **In-app upload notification**
	- Upload a document as an org member/admin.
	- Open **Notifications** (admin view).
	- Confirm a **Document uploaded** item appears.

2. **Mark read / mark all read**
	- Mark one notification as read.
	- Use **Mark all read** and verify unread count updates.

3. **Monthly report settings**
	- Go to **Organization Settings** as admin.
	- Enable monthly report delivery and set recipient email.
	- Save and confirm setup confirmation email is sent.

4. **Monthly digest CLI test**
	- Run:

```bat
python -m flask send-monthly-notification-digest --org-id <ORG_ID> --year 2026 --month 2
```

	- Confirm digest email received by configured recipient.

### Optional focused regression tests

```bat
python -m pytest -q tests/test_document_management.py tests/test_upload_flow.py tests/test_admin_notifications.py
```
