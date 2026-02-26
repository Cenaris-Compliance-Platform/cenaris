# Microsoft Entra ID (Azure AD) - OAuth Setup Guide

## Overview
This guide shows you how to configure Microsoft OAuth (Sign in with Microsoft) for your Cenaris app, including adding redirect URIs for both local development and production.

---

## What is Microsoft Entra ID?

**Microsoft Entra ID** (formerly Azure Active Directory) is Microsoft's identity and access management service. It allows users to sign in with their Microsoft accounts.

---

## Step 1: Access Microsoft Entra ID

1. Go to: https://portal.azure.com
2. Search for **"Microsoft Entra ID"** (or "Azure Active Directory") in the top search bar
3. Click on it to open

---

## Step 2: Find Your App Registration

1. In the left sidebar, click **"App registrations"**
2. You should see your existing app (likely named something like "Cenaris" or "Cenaris Compliance")
3. **Click on your app** to open its settings

**If you don't see an app yet:**
- You need to create one first (see "Creating New App Registration" section below)

---

## Step 3: Add Redirect URIs (Callback URLs)

Redirect URIs are where Microsoft sends users after they successfully log in.

### Current Setup
You probably already have one redirect URI. You need to add more for different environments.

### How to Add More Redirect URIs:

1. **In your app registration**, click **"Authentication"** in the left sidebar
2. Under **"Platform configurations"**, find **"Web"** section
3. Click **"Add URI"** button
4. Add each of these URLs:

```
http://localhost:5000/auth/oauth/microsoft/callback
http://127.0.0.1:5000/auth/oauth/microsoft/callback
https://your-production-domain.com/auth/oauth/microsoft/callback
https://cenaris.onrender.com/auth/oauth/microsoft/callback
```

**Replace:**
- `your-production-domain.com` with your actual production domain
- `cenaris.onrender.com` with your actual Render URL (if using Render)

5. **Scroll down** and click **"Save"**

### Example Configuration:

| Environment | Redirect URI |
|-------------|--------------|
| Local Development | `http://localhost:5000/auth/oauth/microsoft/callback` |
| Local (alternate) | `http://127.0.0.1:5000/auth/oauth/microsoft/callback` |
| Production | `https://cenaris.com.au/auth/oauth/microsoft/callback` |
| Staging/Testing | `https://cenaris-staging.onrender.com/auth/oauth/microsoft/callback` |

---

## Step 4: Configure Token Settings (Important!)

1. Still in **"Authentication"** section, scroll down to **"Implicit grant and hybrid flows"**
2. **Check these boxes:**
   - ☑️ **ID tokens** (used for user authentication)
3. **Uncheck:**
   - ☐ Access tokens (not needed for basic OAuth)
4. Click **"Save"**

---

## Step 5: Configure Account Types (Who Can Sign In)

1. In the left sidebar, click **"Overview"**
2. Look for **"Supported account types"**

**Options:**
- **"Accounts in any organizational directory (Any Azure AD directory - Multitenant)"** - Allows anyone with a Microsoft work/school account
- **"Accounts in any organizational directory and personal Microsoft accounts"** - Allows both work and personal Microsoft accounts (Hotmail, Outlook.com, etc.)
- **"Accounts in this organizational directory only"** - Only your organization

**Recommended for Cenaris:**
- Choose **"Personal Microsoft accounts only"** or **"Any Azure AD directory + personal accounts"**

To change this:
1. Click **"Manifest"** in the left sidebar
2. Find `"signInAudience": "..."`
3. Change to one of:
   - `"AzureADandPersonalMicrosoftAccount"` (most flexible)
   - `"PersonalMicrosoftAccount"` (only personal accounts)
   - `"AzureADMultipleOrgs"` (work/school accounts only)
4. Click **"Save"**

---

## Step 6: Get Client ID and Secret

### Client ID (Application ID):
1. Go to **"Overview"** section
2. Copy **"Application (client) ID"** → This goes in `MICROSOFT_CLIENT_ID` in your `.env`

### Client Secret:
1. Click **"Certificates & secrets"** in the left sidebar
2. Under **"Client secrets"** tab, click **"New client secret"**
3. Add description: "Cenaris Production"
4. Choose expiration: **24 months** (set a reminder to renew before it expires!)
5. Click **"Add"**
6. **IMMEDIATELY COPY THE SECRET VALUE** → This goes in `MICROSOFT_CLIENT_SECRET` in your `.env`
   - ⚠️ **You can only see it once!** If you lose it, you'll need to create a new one

---

## Step 7: Update Your `.env` File

```env
# Microsoft OAuth
MICROSOFT_CLIENT_ID=f92f4f68-d2e1-4878-911a-35888dfff3f8
MICROSOFT_CLIENT_SECRET=your-secret-value-here
MICROSOFT_TENANT=common
```

**Tenant Options:**
- `common` - Allows both personal and organizational accounts (recommended)
- `organizations` - Only organizational (work/school) accounts
- `consumers` - Only personal Microsoft accounts
- `[tenant-id]` - Specific organization only

---

## Creating New App Registration (If You Don't Have One)

1. Go to **"App registrations"** → Click **"New registration"**
2. **Name:** "Cenaris Compliance App"
3. **Supported account types:** "Accounts in any organizational directory and personal Microsoft accounts"
4. **Redirect URI:** 
   - Platform: **Web**
   - URI: `http://localhost:5000/auth/oauth/microsoft/callback`
5. Click **"Register"**
6. Follow steps 3-7 above

---

## Adding Multiple Environments (Local + Staging + Production)

### Scenario: You have 3 environments

1. **Local Development:** `http://localhost:5000`
2. **Staging:** `https://cenaris-staging.onrender.com`
3. **Production:** `https://cenaris.com.au`

### Add All Redirect URIs:

Go to **Authentication** → **Add URI** for each:

```
http://localhost:5000/auth/oauth/microsoft/callback
http://127.0.0.1:5000/auth/oauth/microsoft/callback
https://cenaris-staging.onrender.com/auth/oauth/microsoft/callback
https://cenaris.com.au/auth/oauth/microsoft/callback
```

**All environments use the SAME Client ID and Secret!** No need to create separate app registrations.

---

## Common Tasks

### Adding a New Redirect URI (Detailed Steps)

1. Azure Portal → Microsoft Entra ID
2. App registrations → [Your App]
3. Authentication (left sidebar)
4. Under "Web" platform, click **"Add URI"**
5. Paste the new URL: `https://new-domain.com/auth/oauth/microsoft/callback`
6. Click **"Save"** at the bottom

### Regenerating a Secret (If Lost or Expired)

1. Certificates & secrets → Client secrets tab
2. Click **"New client secret"**
3. Description: "Renewed [Date]"
4. Expiration: 24 months
5. Click **"Add"**
6. **COPY THE NEW SECRET IMMEDIATELY**
7. Update `.env` or production environment variables
8. **(Optional)** Delete the old secret after confirming new one works

### Changing Who Can Sign In

1. Manifest (left sidebar)
2. Find `"signInAudience"`
3. Change value:
   ```json
   "signInAudience": "AzureADandPersonalMicrosoftAccount"
   ```
4. Save

---

## Testing OAuth Locally

1. **Ensure redirect URI includes localhost:**
   - `http://localhost:5000/auth/oauth/microsoft/callback`

2. **Update `.env`:**
   ```env
   MICROSOFT_CLIENT_ID=your-client-id
   MICROSOFT_CLIENT_SECRET=your-secret
   MICROSOFT_TENANT=common
   ```

3. **Restart Flask app**

4. **Test login:**
   - Go to http://localhost:5000/auth/login
   - Click "Sign in with Microsoft"
   - Should redirect to Microsoft login
   - After login, should redirect back to your app

5. **Check for errors** in Flask logs

---

## Troubleshooting

### Error: "Redirect URI mismatch"

**Problem:** The callback URL doesn't match any registered redirect URIs

**Solution:**
1. Check the URL in browser when error occurs
2. Go to Azure Portal → Your App → Authentication
3. Add the EXACT URL shown in the error (including `/auth/oauth/microsoft/callback`)
4. Save and try again

### Error: "Invalid client secret"

**Problem:** Secret is wrong, expired, or not copied correctly

**Solution:**
1. Generate a new client secret
2. Update `.env` or production environment variables
3. Restart app

### Error: "AADSTS50011: The reply URL specified in the request does not match"

**Problem:** Your code is using a different callback URL than what's registered

**Solution:**
1. Check your Flask route in `app/auth/routes.py`
2. The route should be: `@bp.route('/oauth/microsoft/callback')`
3. Full URL must match Azure: `https://yourdomain.com/auth/oauth/microsoft/callback`

### Users Can't Sign In (Personal Accounts)

**Problem:** App is configured for organizational accounts only

**Solution:**
1. Go to Manifest
2. Change `"signInAudience"` to `"AzureADandPersonalMicrosoftAccount"`
3. Save

---

## Security Best Practices

1. **Rotate secrets every 12-24 months** (set calendar reminder)
2. **Use HTTPS in production** (HTTP only for localhost)
3. **Don't commit secrets to git** (`.env` is in `.gitignore`)
4. **Limit redirect URIs** to only the domains you actually use
5. **Monitor sign-ins** in Azure Portal → Sign-in logs

---

## Quick Reference

| Setting | Location | Example Value |
|---------|----------|---------------|
| Client ID | Overview | `f92f4f68-d2e1-4878-911a-35888dfff3f8` |
| Client Secret | Certificates & secrets | Generate new (24 months expiry) |
| Redirect URIs | Authentication → Web | `https://domain.com/auth/oauth/microsoft/callback` |
| Tenant | Manifest → signInAudience | `common` or `AzureADandPersonalMicrosoftAccount` |

---

## Need Help?

- **Microsoft Entra ID Docs:** https://learn.microsoft.com/en-us/entra/identity/
- **App Registration Guide:** https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app
- **Redirect URI Troubleshooting:** https://learn.microsoft.com/en-us/entra/identity-platform/reply-url

---

**All set! 🎉**
