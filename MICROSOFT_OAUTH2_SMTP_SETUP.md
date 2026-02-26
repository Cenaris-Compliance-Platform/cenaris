# Microsoft 365 OAuth2 SMTP Setup Guide

When Microsoft 365 has "Modern Authentication" enabled, it blocks basic authentication (app passwords) and requires OAuth2 for SMTP.

**You still use `adam@cenaris.com.au`** - same email address, same domain, just different authentication.

---

## Step 1: Register Azure AD Application (Adam needs to do this)

### 1.1 Create the App Registration

1. Go to **Azure Portal**: https://portal.azure.com
2. Navigate to **Azure Active Directory** → **App registrations**
3. Click **"+ New registration"**
4. Fill in:
   - **Name**: `Cenaris SMTP OAuth2`
   - **Supported account types**: "Accounts in this organizational directory only (Single tenant)"
   - **Redirect URI**: Leave blank (not needed for SMTP)
5. Click **Register**

### 1.2 Get Application (Client) ID

After registration:
1. Copy the **Application (client) ID** (looks like: `12345678-1234-1234-1234-123456789abc`)
2. Copy the **Directory (tenant) ID** (looks like: `87654321-4321-4321-4321-cba987654321`)

Save these for `.env` file.

### 1.3 Create Client Secret

1. In the app registration, go to **Certificates & secrets**
2. Click **"+ New client secret"**
3. Description: `SMTP OAuth2 Secret`
4. Expires: Choose **24 months** (or longer)
5. Click **Add**
6. **IMMEDIATELY COPY THE VALUE** - you can't see it again!

Save this secret for `.env` file.

### 1.4 Assign API Permissions

1. Go to **API permissions**
2. Click **"+ Add a permission"**
3. Select **Microsoft Graph**
4. Choose **Application permissions** (not Delegated)
5. Search and add these permissions:
   - `Mail.Send` - Send mail as any user
   - `User.Read.All` - Read all users' basic profiles (optional)
6. Click **Add permissions**
7. **IMPORTANT**: Click **"Grant admin consent for [Your Organization]"** (blue button at top)
8. Confirm by clicking **Yes**

You should see green checkmarks ✓ next to each permission.

---

## Step 2: Configure Exchange Online (Adam needs to do this)

### 2.1 Allow the App to Send Email

Adam must run this PowerShell command to allow the Azure AD app to send emails:

#### Install Exchange Online PowerShell (one-time)
```powershell
Install-Module -Name ExchangeOnlineManagement -Force -AllowClobber
```

#### Connect to Exchange Online
```powershell
Connect-ExchangeOnline -UserPrincipalName adam@cenaris.com.au
```

It will prompt for login - use Adam's Microsoft 365 credentials.

#### Create Service Principal in Exchange
```powershell
New-ServicePrincipal -AppId "<YOUR_CLIENT_ID>" -ServiceId "<YOUR_CLIENT_ID>" -DisplayName "Cenaris SMTP OAuth2"
```

Replace `<YOUR_CLIENT_ID>` with the Application (client) ID from Step 1.2.

#### Assign Send Permissions
```powershell
Add-MailboxPermission -Identity "adam@cenaris.com.au" -User "<YOUR_CLIENT_ID>" -AccessRights FullAccess
```

This allows the app to send emails as `adam@cenaris.com.au`.

#### Verify the Setup
```powershell
Get-ServicePrincipal -Identity "<YOUR_CLIENT_ID>"
```

Should show the service principal with DisplayName "Cenaris SMTP OAuth2".

---

## Step 3: Update Environment Variables

Add these to your `.env` file (replacing the old MAIL_PASSWORD):

```bash
# Microsoft 365 OAuth2 for SMTP (replaces app password)
MICROSOFT_SMTP_CLIENT_ID=<Application_Client_ID_from_step_1.2>
MICROSOFT_SMTP_CLIENT_SECRET=<Client_Secret_from_step_1.3>
MICROSOFT_SMTP_TENANT_ID=<Directory_Tenant_ID_from_step_1.2>

# Keep these the same
MAIL_SERVER=smtp.office365.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=adam@cenaris.com.au
MAIL_DEFAULT_SENDER=adam@cenaris.com.au
# MAIL_PASSWORD is no longer needed - OAuth2 uses tokens instead
```

---

## Step 4: Deploy and Test

After the code changes are deployed:

1. Restart your Flask application
2. Test "Forgot Password" feature
3. Check logs for "OAuth2 token acquired successfully"
4. Email should send via OAuth2 authentication

---

## Troubleshooting

### Error: "Authentication unsuccessful"
- Verify admin consent was granted in Azure AD (Step 1.4)
- Check that service principal was created in Exchange Online (Step 2)
- Confirm client secret hasn't expired

### Error: "Invalid client"
- Check CLIENT_ID and TENANT_ID are correct in `.env`
- Verify CLIENT_SECRET was copied correctly (no extra spaces)

### Error: "Insufficient privileges"
- Grant admin consent for API permissions (Step 1.4)
- Verify `Mail.Send` permission is added and consented

### Error: "Access denied"
- Run the `Add-MailboxPermission` command in Exchange Online (Step 2)
- Make sure service principal is registered with Exchange

### Email sends but from wrong address
- Update `Add-MailboxPermission -Identity` to use the correct email address
- Verify MAIL_USERNAME and MAIL_DEFAULT_SENDER match

---

## Security Notes

- **Client Secret**: Store securely, never commit to git
- **Permissions**: App has `Mail.Send` - can send as ANY user if mailbox permission granted
- **Expiration**: Client secret expires after chosen period (24 months) - must regenerate
- **Least Privilege**: Only grant mailbox permission for `adam@cenaris.com.au`, not all users

---

## Comparison: App Password vs OAuth2

| Feature | App Password | OAuth2 |
|---------|-------------|---------|
| **Security** | Less secure (password-based) | More secure (token-based) |
| **Microsoft Recommendation** | Deprecated, being phased out | Recommended modern approach |
| **Setup Complexity** | Simple (just generate password) | Complex (Azure AD app + Exchange config) |
| **Expiration** | Never expires | Refresh tokens automatically |
| **Works with Modern Auth ON** | ❌ Blocked | ✅ Required |
| **Your Situation** | Not working (535 error) | Will work |

---

## Quick Reference: What Adam Needs to Do

1. ✅ Azure Portal: Create app registration → Copy Client ID, Tenant ID, Client Secret
2. ✅ Azure Portal: Add `Mail.Send` API permission → Grant admin consent
3. ✅ PowerShell: Connect to Exchange Online → Create service principal → Grant mailbox permission
4. ✅ Send you the 3 IDs/secrets to add to `.env`

Once Adam completes these steps, the Flask code will handle the rest (acquiring tokens, sending emails with OAuth2).
