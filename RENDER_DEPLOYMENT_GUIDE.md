# 🚀 Deploy Cenaris to Render - Step by Step Guide

## Prerequisites
✅ Render account (you have this)
✅ GitHub account
✅ Your code pushed to GitHub

---

## Step 1: Push Your Code to GitHub

If you haven't already, push your code to GitHub:

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Ready for Render deployment"

# Create a new repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/cenaris.git
git branch -M main
git push -u origin main
```

---

## Step 2: Create PostgreSQL Database on Render

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"PostgreSQL"**
3. Fill in:
   - **Name:** `cenaris-db`
   - **Database:** `cenaris_production`
   - **User:** `cenaris_user`
   - **Region:** Choose closest to you
   - **Plan:** Free (or Starter $7/month for better performance)
4. Click **"Create Database"**
5. **IMPORTANT:** Copy the **Internal Database URL** (you'll need this)

---

## Step 3: Create Web Service on Render

1. Click **"New +"** → **"Web Service"**
2. Connect your GitHub repository
3. Fill in the details:

### Basic Settings:
- **Name:** `cenaris-compliance`
- **Region:** Same as database
- **Branch:** `main`
- **Root Directory:** (leave empty)
- **Runtime:** `Python 3`
- **Build Command:** 
  ```
  pip install -r requirements.txt
  ```
- **Start Command:**
  ```
  gunicorn -w 4 -b 0.0.0.0:$PORT run:app
  ```

### Instance Type:
- **Free** (for testing) or **Starter $7/month** (recommended)

---

## Step 4: Add Environment Variables

In the **Environment** section, add these variables:

### Required Variables:

1. **FLASK_CONFIG**
   - Value: `production`

2. **SECRET_KEY**
   - Value: Click "Generate" or use: `your-super-secret-key-here-change-this`

3. **DATABASE_URL**
   - Value: Paste the Internal Database URL from Step 2

4. **AZURE_STORAGE_CONNECTION_STRING**
   - Value: Your Azure connection string
   - `DefaultEndpointsProtocol=https;AccountName=cenarisblobstorage;AccountKey=YOUR_KEY;EndpointSuffix=core.windows.net`

5. **AZURE_CONTAINER_NAME**
   - Value: `user-uploads`

6. **AZURE_ML_STORAGE_ACCOUNT**
   - Value: `cenarisblobstorage`

7. **AZURE_ML_CONTAINER**
   - Value: `results`

8. **AZURE_ML_RESULTS_PATH**
   - Value: `compliance-results`

---

## Step 5: Deploy!

1. Click **"Create Web Service"**
2. Render will automatically:
   - Clone your repo
   - Install dependencies
   - Start your app
3. Wait 3-5 minutes for deployment
4. You'll get a URL like: `https://cenaris-compliance.onrender.com`

---

## Step 6: Initialize Database

After first deployment, you need to create the database tables:

### Option A: Using Render Shell
1. Go to your web service dashboard
2. Click **"Shell"** tab
3. Run:
   ```bash
   python -c "from app import create_app; from app.database import init_database; app = create_app('production'); app.app_context().push(); init_database()"
   ```

### Option B: Add initialization to run.py (already done!)
The database will auto-initialize on first run.

---

## Step 7: Test Your Deployment

1. Visit your Render URL: `https://cenaris-compliance.onrender.com`
2. You should see the login page
3. Create a new account or login
4. Test uploading a document
5. Check Gap Analysis page

---

## 🎉 You're Live!

Your app is now deployed at:
**https://cenaris-compliance.onrender.com**

(Render gives you a free subdomain - no custom domain needed!)

---

## Important Notes

### Free Tier Limitations:
- ⚠️ App sleeps after 15 minutes of inactivity
- ⚠️ First request after sleep takes 30-60 seconds
- ⚠️ 750 hours/month free (enough for one app)
- ⚠️ Database limited to 1GB

### Upgrade to Starter ($7/month) for:
- ✅ No sleeping
- ✅ Faster performance
- ✅ More resources
- ✅ Better for production

---

## Troubleshooting

### Build Failed?
- Check `requirements.txt` has all dependencies
- Check Python version in `runtime.txt`
- View build logs in Render dashboard

### App Crashes?
- Check environment variables are set correctly
- View logs in Render dashboard
- Check database connection string

### Database Connection Error?
- Make sure DATABASE_URL is set
- Use **Internal Database URL** (not External)
- Check database is running

### Azure Storage Not Working?
- Verify AZURE_STORAGE_CONNECTION_STRING is correct
- Check container names match
- Test connection locally first

---

## Updating Your App

To deploy updates:

```bash
# Make your changes
git add .
git commit -m "Update feature X"
git push origin main
```

Render will automatically detect the push and redeploy! 🚀

---

## Monitoring

- **Logs:** Render Dashboard → Your Service → Logs
- **Metrics:** Render Dashboard → Your Service → Metrics
- **Shell Access:** Render Dashboard → Your Service → Shell

---

## Cost Summary

### Free Tier (Good for Testing):
- Web Service: Free
- PostgreSQL: Free (1GB)
- **Total: $0/month**

### Starter Tier (Recommended for Production):
- Web Service: $7/month
- PostgreSQL: $7/month
- **Total: $14/month**

---

## Next Steps After Deployment

1. ✅ Test all features
2. ✅ Create your first organization
3. ✅ Upload test documents
4. ✅ Generate reports
5. ✅ Share URL with Adam!

---

## Need Help?

- Render Docs: https://render.com/docs
- Render Community: https://community.render.com
- Check logs in Render dashboard

---

**Your Render URL will be:**
`https://cenaris-compliance.onrender.com`

(You can change "cenaris-compliance" to any available name during setup)

Good luck with your deployment! 🎉
