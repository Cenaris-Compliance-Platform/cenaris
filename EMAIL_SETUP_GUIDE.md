# Email Configuration Guide - SMTP Setup

## Overview
Your app now uses **SMTP** (Simple Mail Transfer Protocol) to send emails. This guide will help you set up email for both **development** (your testing) and **production** (client's live system).

---

## Quick Setup (For You - Development)

### Option 1: Gmail (Easiest for Testing)

1. **Enable 2-Factor Authentication on your Gmail account**
   - Go to: https://myaccount.google.com/security
   - Click "2-Step Verification" → Turn it on

2. **Create an App Password**
   - Go to: https://myaccount.google.com/apppasswords
   - Select app: **"Mail"**
   - Select device: **"Other (Custom name)"** → Type: "Cenaris App"
   - Click "Generate"
   - You'll get a **16-character password** (like: `abcd efgh ijkl mnop`)
   - **Copy it** (remove spaces: `abcdefghijklmnop`)

3. **Update your `.env` file**
   ```env
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=true
   MAIL_USE_SSL=false
   MAIL_USERNAME=your-gmail@gmail.com
   MAIL_PASSWORD=abcdefghijklmnop
   MAIL_DEFAULT_SENDER=your-gmail@gmail.com
   ```

4. **Restart your Flask app** and test!

---

## Production Setup (For Client - adam@cenaris.com.au)

### What You Need From the Client

**Before going live, coordinate with Adam (the client) to get these details:**

| What You Need | Example | How to Get It |
|---------------|---------|---------------|
| **Business Email** | adam@cenaris.com.au | Already have this |
| **Email Provider** | Microsoft 365 / Google Workspace | Ask: "What email service do you use?" |
| **SMTP Server** | smtp.office365.com | Depends on provider (see below) |
| **App Password** | 16-character password | Client must generate (instructions below) |

---

### Step-by-Step: Getting Info from Client

**Send this message to Adam:**

> Hi Adam,
> 
> To enable email notifications (password resets, user invitations, etc.) in the Cenaris app, I need you to set up an "App Password" for your email account (adam@cenaris.com.au).
> 
> This is a secure way for the app to send emails on your behalf without storing your actual password.
> 
> **What email service do you use?**
> - [ ] Microsoft 365 / Outlook (your cenaris.com.au email)
> - [ ] Google Workspace
> - [ ] Other (please specify)
> 
> **Once you confirm, I'll send you the exact steps to generate the App Password.**

---

### Microsoft 365 / Outlook (Most likely for adam@cenaris.com.au)

**Instructions for the client:**

1. **Enable Multi-Factor Authentication (MFA)**
   - Go to: https://account.microsoft.com/security
   - Under "Advanced security options", enable **"Two-step verification"**
   - Follow the prompts (use Microsoft Authenticator app or SMS)

2. **Generate App Password**
   - Go to: https://account.microsoft.com/security
   - Under "Advanced security options", click **"Create a new app password"**
   - Name it: "Cenaris Compliance App"
   - **Copy the password** (16 characters, no spaces)
   - **DO NOT SHARE IT VIA EMAIL** - Send it securely (e.g., Signal, WhatsApp, or in person)

3. **Provide these settings to you:**
   ```
   Email: adam@cenaris.com.au
   App Password: [16-character password]
   ```

**You will configure:**
```env
MAIL_SERVER=smtp.office365.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_USERNAME=adam@cenaris.com.au
MAIL_PASSWORD=[app-password-from-client]
MAIL_DEFAULT_SENDER=adam@cenaris.com.au
```

---

### Google Workspace (If client uses Google for cenaris.com.au)

**Instructions for the client:**

1. **Enable 2-Step Verification**
   - Go to: https://myaccount.google.com/security
   - Click "2-Step Verification" → Turn it on

2. **Create App Password**
   - Go to: https://myaccount.google.com/apppasswords
   - Select app: **"Mail"**
   - Select device: **"Other (Custom name)"** → Type: "Cenaris App"
   - Click **"Generate"**
   - Copy the 16-character password

3. **Provide these settings to you:**
   ```
   Email: adam@cenaris.com.au
   App Password: [16-character password]
   ```

**You will configure:**
```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_USERNAME=adam@cenaris.com.au
MAIL_PASSWORD=[app-password-from-client]
MAIL_DEFAULT_SENDER=adam@cenaris.com.au
```

---

## Deployment Checklist

### Before Going Live:

- [ ] **Get App Password from client** (via secure channel, NOT email)
- [ ] **Update production `.env` file** or environment variables on hosting platform
- [ ] **Test email sending** on production:
  - Try "Forgot Password" feature
  - Try inviting a test user
  - Check emails actually arrive (not in spam)
- [ ] **Delete test data** after confirming emails work
- [ ] **Document credentials** in your secure password manager (NOT in git)

### Setting Environment Variables on Render/Heroku/Azure:

**Render:**
1. Go to your Render dashboard
2. Click on your web service
3. Go to "Environment" tab
4. Add these variables:
   ```
   MAIL_SERVER=smtp.office365.com
   MAIL_PORT=587
   MAIL_USE_TLS=true
   MAIL_USERNAME=adam@cenaris.com.au
   MAIL_PASSWORD=[app-password]
   MAIL_DEFAULT_SENDER=adam@cenaris.com.au
   ```
5. Click "Save Changes" → App will auto-redeploy

---

## Testing Email Locally

1. **Update `.env` with your Gmail App Password**
2. **Restart Flask app**
3. **Test forgot password:**
   - Go to http://localhost:5000/auth/forgot-password
   - Enter your email
   - Check your inbox (and spam folder)
4. **Check logs** for any errors:
   ```
   [MONITORING] Email sent via SMTP to your-email@gmail.com
   ```

---

## Troubleshooting

### "Authentication failed" error

**Problem:** Wrong username or password

**Solutions:**
- Verify App Password is correct (no spaces, 16 characters)
- Make sure 2FA/MFA is enabled on the email account
- For Gmail: Check if "Less secure app access" is OFF (it should be, use App Passwords instead)
- For Microsoft: Ensure "Modern Authentication" is enabled

### "SMTP connect() failed"

**Problem:** Can't reach SMTP server

**Solutions:**
- Check MAIL_SERVER and MAIL_PORT are correct
- Verify firewall isn't blocking port 587
- Try port 465 with `MAIL_USE_SSL=true` instead of TLS

### Emails go to spam

**Solutions:**
- Ask client to add app's domain to SPF record (DNS settings)
- Use client's actual business email (adam@cenaris.com.au) not Gmail
- Test with multiple email providers (Gmail, Outlook, etc.)

### "Email not configured" message

**Problem:** Missing environment variables

**Solutions:**
- Verify ALL these are set in `.env`:
  - MAIL_SERVER
  - MAIL_PORT
  - MAIL_USERNAME
  - MAIL_PASSWORD
  - MAIL_DEFAULT_SENDER
- Restart Flask app after changing `.env`

---

## Code Changes Summary

✅ **Removed SendGrid** - No more paid service dependency
✅ **Pure SMTP** - Uses Flask-Mail (already in requirements.txt)
✅ **Updated `.env`** - Clear configuration options
✅ **Updated code** - Simplified email sending functions

**Files modified:**
- `app/auth/routes.py` - Simplified `_send_email()` and `_send_email_html()`
- `.env` - Updated with SMTP configuration templates
- `EMAIL_SETUP_GUIDE.md` - This guide (NEW)

---

## Security Best Practices

1. **Never commit `.env` to git** (it's in `.gitignore`)
2. **Use App Passwords, not real passwords** (protects main account)
3. **Share passwords securely** (use encrypted channels, not email/SMS)
4. **Rotate App Passwords annually** (regenerate every 12 months)
5. **Revoke unused App Passwords** (if you stop using one, delete it)

---

## Quick Reference

| Provider | SMTP Server | Port | TLS/SSL |
|----------|-------------|------|---------|
| Gmail | smtp.gmail.com | 587 | TLS |
| Microsoft 365 | smtp.office365.com | 587 | TLS |
| Outlook.com | smtp-mail.outlook.com | 587 | TLS |
| Yahoo | smtp.mail.yahoo.com | 587 | TLS |
| Zoho | smtp.zoho.com | 587 | TLS |

---

## What's Next?

1. **Test locally** with your Gmail App Password
2. **Coordinate with client** to get production email setup
3. **Deploy to production** with proper environment variables
4. **Test on production** (forgot password, invitations)
5. **Document** where production credentials are stored (password manager)

---

## Need Help?

- **Gmail App Passwords**: https://support.google.com/accounts/answer/185833
- **Microsoft App Passwords**: https://support.microsoft.com/en-us/account-billing/manage-app-passwords-for-two-step-verification-d6dc8c6d-4bf7-4851-ad95-6d07799387e9
- **Flask-Mail Docs**: https://flask-mail.readthedocs.io/

---

**Good luck! 🚀**
