# ENV_SETUP.md (Simple) — What to set + where to get tokens

This file is ONLY for environment variables (credentials/tokens). For how to run the repo, see `README.md`.

If you want production working fast, do the steps in this order:

1) `SECRET_KEY`
2) Azure PostgreSQL → `DATABASE_URL`
3) Azure Storage → `AZURE_STORAGE_CONNECTION_STRING` + `AZURE_CONTAINER_NAME`
4) SMTP email (optional but recommended)
5) Email verification + CAPTCHA (recommended)
6) OAuth (optional)

---

## 1) Minimum env vars (Production)

Set these in your hosting provider:

- `FLASK_CONFIG=production`
- `SECRET_KEY=...`
- `DATABASE_URL=postgresql://...`
- `AZURE_STORAGE_CONNECTION_STRING=...`
- `AZURE_CONTAINER_NAME=compliance-documents`

Recommended security:

- `REQUIRE_EMAIL_VERIFICATION=true`
- `TURNSTILE_SITE_KEY=...`
- `TURNSTILE_SECRET_KEY=...`

---

## 2) Generate a strong SECRET_KEY

This app uses `SECRET_KEY` for sessions + CSRF + signed links.

On Windows PowerShell:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Copy the output into `SECRET_KEY`.

---

## 3) Azure PostgreSQL (DATABASE_URL) — where to get the “DB token”

### 3.1 Create the server

Azure Portal → Create a resource → **Azure Database for PostgreSQL flexible server**

### 3.2 Allow network access

Azure Portal → your Postgres server → Networking

- If hosting on Render/other public host: allow public access and add firewall rules.
- If hosting on Azure: configure VNet/private access (more secure, more work).

### 3.3 Get the connection string

Azure Portal → your Postgres server → **Connection strings**

Build `DATABASE_URL` like:

```text
postgresql://USERNAME:PASSWORD@HOSTNAME:5432/DBNAME?sslmode=require
```

Important:

- Azure Postgres usually requires SSL → keep `sslmode=require`.

### 3.4 Run migrations

After `DATABASE_URL` is set:

```bat
flask db upgrade
```

---

## 4) Azure Storage (Uploads + Logos) — where to get the “Storage token”

### 4.1 Create a Storage Account

Azure Portal → Storage accounts → Create

(If you need ADLS Gen2 features, enable **Hierarchical namespace**.)

### 4.2 Create a container

Azure Portal → Storage account → Data storage → Containers → Create

Use a single container name everywhere, for example:

```text
AZURE_CONTAINER_NAME=compliance-documents
```

### 4.3 Get the connection string

Azure Portal → Storage account → Security + networking → **Access keys**

Copy the **Connection string** into:

```text
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=...;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net
```

Security note: this is a secret (treat like a password).

---

## 5) SMTP Email (Forgot password + verify email) — where to get “email creds”

Email is optional. If you don’t set SMTP, the app will log reset/verify links in server logs.

### 5.1 Required env vars

```text
MAIL_SERVER=smtp.sendgrid.net
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_USERNAME=apikey
MAIL_PASSWORD=YOUR_SENDGRID_API_KEY
MAIL_DEFAULT_SENDER="CCM Support <support@yourdomain.com>"
```

### 5.2 Where to get creds (SendGrid example)

SendGrid Dashboard:

1) Settings → API Keys → Create API key
2) SMTP values:
   - Username = `apikey`
   - Password = (the API key you just created)
3) Sender Authentication: verify domain or single sender

---

## 6) Email verification (recommended)

This app supports token-based email verification.

Set:

```text
REQUIRE_EMAIL_VERIFICATION=true
```

How it works:

- User signs up → gets a signed verification link.
- They can’t log in with password until verified (if enabled).

---

## 7) CAPTCHA (Cloudflare Turnstile) — where to get “Turnstile tokens”

Turnstile is optional. If configured, it protects signup + forgot password + resend verification.

### 7.1 Create keys

Cloudflare Dashboard → Turnstile → Add widget

You will receive:

- Site key → `TURNSTILE_SITE_KEY`
- Secret key → `TURNSTILE_SECRET_KEY`

### 7.2 Set env vars

```text
TURNSTILE_SITE_KEY=...
TURNSTILE_SECRET_KEY=...
```

---

## 8) OAuth (Google / Microsoft) — where to get “OAuth tokens”

OAuth is optional. If set, users can sign in with Google/Microsoft.

### 8.1 Google OAuth

Google Cloud Console → APIs & Services → Credentials → Create Credentials → OAuth client ID

Set:

```text
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

Add an authorized redirect URI:

```text
https://YOUR_DOMAIN/auth/oauth/google/callback
```

### 8.2 Microsoft OAuth

Azure Portal → Microsoft Entra ID → App registrations → New registration

Set:

```text
MICROSOFT_CLIENT_ID=...
MICROSOFT_CLIENT_SECRET=...
MICROSOFT_TENANT=common
```

Add a redirect URI:

```text
https://YOUR_DOMAIN/auth/oauth/microsoft/callback
```

---

## 9) Local dev (short)

1) Copy `.env.example` → `.env`
2) Use SQLite for dev:

```text
FLASK_CONFIG=development
DEV_DATABASE_URL=sqlite:///compliance_dev.db
```

3) Run:

```bat
flask db upgrade
python run.py
```

Reset local DB if needed:

```bat
flask reset-local-db
```

Wipe application data (so you can reuse the same email and re-test signup/onboarding):

```bat
flask wipe-test-data
```

Reset onboarding/billing state for one organization (keeps users/memberships):

```bat
flask reset-org-state --org-id 1
```

Notes:

- `wipe-test-data` deletes app data (users/orgs/memberships/documents) but keeps schema + migrations.
- It refuses to run when `DEBUG` is false unless you pass `--force` and set `ALLOW_DATA_WIPE=1`.

This app supports **email verification via a signed token link**.

### How it works

- When enabled, new users must click a verification link emailed to them before they can sign in with a password.
- If SMTP is not configured, the verification link is logged to server logs (dev convenience).

### Environment variable

- `REQUIRE_EMAIL_VERIFICATION=true` (recommended in production)

Notes:

- OAuth sign-ins (Google/Microsoft) are treated as verified automatically.

---

## CAPTCHA Protection (Cloudflare Turnstile)

This app supports CAPTCHA protection using **Cloudflare Turnstile** for:

- Signup
- Forgot password
- Resend verification link

CAPTCHA is only enforced when the secret key is set.

### 1) Create a Turnstile site

Cloudflare Dashboard → **Turnstile** → **Add site**

- Choose widget type (Managed is fine)
- Add your domain(s) (include your production domain; for local you can add `localhost`)

### 2) Get the keys

You will get:

- Site key (public)
- Secret key (private)

### 3) Set env vars

- `TURNSTILE_SITE_KEY=...`
- `TURNSTILE_SECRET_KEY=...`

### 4.3 App base URL / HTTPS

If you deploy behind a proxy (Render/NGINX), ensure the app correctly knows it is HTTPS.

If you see generated links using http instead of https, you may need proxy header handling.

---

## 5) Example `.env` (Local Dev)

Create a `.env` file in the project root:

```env
FLASK_CONFIG=development
SECRET_KEY=dev-only-change-me

# Database
DEV_DATABASE_URL=sqlite:///compliance_dev.db

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net
AZURE_CONTAINER_NAME=compliance-documents

# Email (optional)
MAIL_SERVER=
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=

# OAuth (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
MICROSOFT_CLIENT_ID=
MICROSOFT_CLIENT_SECRET=
MICROSOFT_TENANT=common
```

---

## 6) Post-deploy sanity checks

- Database: open the app and confirm login/signup works.
- Migrations: confirm tables exist and no `flask db upgrade` errors.
- Storage: upload a document and confirm it appears in Evidence Repository.
- Email: request forgot-password and confirm email arrives (or check logs if not configured).
- Theme toggle: use the navbar toggle and confirm it persists after refresh.
