# 🚀 Complete Beginner's Guide to Deploy Cenaris on Render

## What You'll Get
- A live website URL like: `https://cenaris-compliance.onrender.com`
- No custom domain needed (Render gives you a free subdomain)
- Your app running 24/7 on the cloud

---

## PART 1: Prepare Your Code (5 minutes)

### Step 1.1: Make Sure You Have a GitHub Account

1. Go to https://github.com
2. If you don't have an account, click "Sign up" (it's free)
3. If you have an account, just login

### Step 1.2: Create a New Repository on GitHub

1. Once logged in to GitHub, click the **"+"** icon (top right)
2. Click **"New repository"**
3. Fill in:
   - **Repository name:** `cenaris-compliance`
   - **Description:** `Healthcare compliance management system`
   - **Public** or **Private** (your choice)
   - **DO NOT** check "Add a README file"
4. Click **"Create repository"**
5. **KEEP THIS PAGE OPEN** - you'll need it in the next step

### Step 1.3: Push Your Code to GitHub

Open your terminal in the cenaris folder and run these commands ONE BY ONE:

```bash
# 1. Initialize git (if not already done)
git init

# 2. Add all your files
git add .

# 3. Commit your files
git commit -m "Initial commit for Render deployment"

# 4. Add your GitHub repository (REPLACE with YOUR username and repo name)
git remote add origin https://github.com/YOUR_USERNAME/cenaris-compliance.git

# 5. Rename branch to main
git branch -M main

# 6. Push to GitHub
git push -u origin main
```

**Example:** If your GitHub username is "abdullah123", the command would be:
```bash
git remote add origin https://github.com/abdullah123/cenaris-compliance.git
```

**What if you get an error?**
- If it says "remote origin already exists", run: `git remote remove origin` then try again
- If it asks for username/password, use your GitHub username and a Personal Access Token (not password)

### Step 1.4: Verify Your Code is on GitHub

1. Go back to your GitHub repository page
2. Refresh the page
3. You should see all your files listed
4. ✅ If you see your files, you're ready for the next part!

---

## PART 2: Create PostgreSQL Database on Render (10 minutes)

### Step 2.1: Login to Render

1. Go to https://dashboard.render.com
2. Login with your Render account
3. You'll see the Render Dashboard (it's like a control panel)

### Step 2.2: Create a New PostgreSQL Database

1. Look for a blue button that says **"New +"** (top right corner)
2. Click it
3. A dropdown menu appears - click **"PostgreSQL"**
4. You'll see a form to fill out

### Step 2.3: Fill Out the Database Form

Fill in these fields:

**Name:**
```
cenaris-db
```
(This is just a name for you to identify it - you can use any name)

**Database:**
```
cenaris_production
```
(This is the actual database name inside PostgreSQL)

**User:**
```
cenaris_user
```
(This is the username that will access the database)

**Region:**
- Choose the one closest to you or your users
- For Australia: **Singapore** is usually best
- For USA: **Oregon** or **Ohio**
- For Europe: **Frankfurt**

**PostgreSQL Version:**
- Leave as default (usually 16 or latest)

**Datadog API Key:**
- Leave empty (you don't need this)

**Instance Type:**
- **Free** - Good for testing (1GB storage, database may be deleted after 90 days)
- **Starter ($7/month)** - Better for production (10GB storage, persistent)

**For now, choose FREE to test**

### Step 2.4: Create the Database

1. Click the blue **"Create Database"** button at the bottom
2. Wait 1-2 minutes while Render creates your database
3. You'll see a progress indicator

### Step 2.5: Copy Your Database Connection String

Once the database is created, you'll see a page with database details.

**VERY IMPORTANT:** You need to copy the **Internal Database URL**

1. Scroll down to find **"Connections"** section
2. You'll see two URLs:
   - **External Database URL** (starts with `postgres://`)
   - **Internal Database URL** (starts with `postgres://`)
3. Find the **Internal Database URL**
4. Click the **copy icon** next to it (looks like two overlapping squares)
5. **PASTE IT SOMEWHERE SAFE** (like a text file) - you'll need this in Part 3!

**It looks like this:**
```
postgres://cenaris_user:SOME_LONG_PASSWORD@dpg-xxxxx-a/cenaris_production
```

✅ **Database is ready!** Keep that URL safe!

---

## PART 3: Create Web Service on Render (15 minutes)

### Step 3.1: Start Creating a New Web Service

1. Go back to Render Dashboard: https://dashboard.render.com
2. Click **"New +"** button again (top right)
3. This time, click **"Web Service"**

### Step 3.2: Connect Your GitHub Repository

You'll see a page asking to connect your repository.

**If this is your first time:**
1. Click **"Connect GitHub"** or **"Configure GitHub"**
2. A popup will ask you to authorize Render
3. Click **"Authorize Render"**
4. You might need to enter your GitHub password

**Select Your Repository:**
1. You'll see a list of your GitHub repositories
2. Find **"cenaris-compliance"** (or whatever you named it)
3. Click **"Connect"** next to it

**If you don't see your repository:**
1. Click **"Configure GitHub App"**
2. Select which repositories Render can access
3. Choose "All repositories" or select "cenaris-compliance"
4. Click "Save"
5. Go back to Render and refresh

### Step 3.3: Configure Your Web Service

Now you'll see a form with many fields. Fill them out carefully:

#### Basic Information:

**Name:**
```
cenaris-compliance
```
(This will be part of your URL: cenaris-compliance.onrender.com)

**Region:**
```
Same as your database (e.g., Singapore)
```

**Branch:**
```
main
```
(This is your GitHub branch name)

**Root Directory:**
```
(leave this EMPTY)
```

**Runtime:**
```
Python 3
```
(Select from dropdown)

#### Build & Deploy:

**Build Command:**
```
pip install -r requirements.txt
```
(Copy this EXACTLY)

**Start Command:**
```
gunicorn -w 4 -b 0.0.0.0:$PORT run:app
```
(Copy this EXACTLY)

#### Instance Type:

**Plan:**
- **Free** - Good for testing (app sleeps after 15 min of no activity)
- **Starter ($7/month)** - Recommended for production (always on)

**For now, choose FREE to test**

### Step 3.4: Add Environment Variables (IMPORTANT!)

Scroll down to the **"Environment Variables"** section.

You need to add 8 variables. Click **"Add Environment Variable"** for each one:

#### Variable 1: FLASK_CONFIG
- **Key:** `FLASK_CONFIG`
- **Value:** `production`

#### Variable 2: SECRET_KEY
- **Key:** `SECRET_KEY`
- **Value:** Click the **"Generate"** button (Render will create a random secure key)
- OR paste: `your-super-secret-random-key-change-this-to-something-long-and-random`

#### Variable 3: DATABASE_URL
- **Key:** `DATABASE_URL`
- **Value:** Paste the **Internal Database URL** you copied in Part 2, Step 2.5
- It should look like: `postgres://cenaris_user:PASSWORD@dpg-xxxxx-a/cenaris_production`

#### Variable 4: AZURE_STORAGE_CONNECTION_STRING
- **Key:** `AZURE_STORAGE_CONNECTION_STRING`
- **Value:** Your Azure connection string from your `.env` file
- It looks like: `DefaultEndpointsProtocol=https;AccountName=cenarisblobstorage;AccountKey=YOUR_KEY;EndpointSuffix=core.windows.net`

**How to find it:**
1. Open your `.env` file in your project
2. Copy the value after `AZURE_STORAGE_CONNECTION_STRING=`
3. Paste it here

#### Variable 5: AZURE_CONTAINER_NAME
- **Key:** `AZURE_CONTAINER_NAME`
- **Value:** `user-uploads`

#### Variable 6: AZURE_ML_STORAGE_ACCOUNT
- **Key:** `AZURE_ML_STORAGE_ACCOUNT`
- **Value:** `cenarisblobstorage`

#### Variable 7: AZURE_ML_CONTAINER
- **Key:** `AZURE_ML_CONTAINER`
- **Value:** `results`

#### Variable 8: AZURE_ML_RESULTS_PATH
- **Key:** `AZURE_ML_RESULTS_PATH`
- **Value:** `compliance-results`

**Double-check all 8 variables are added!**

### Step 3.5: Create the Web Service

1. Scroll to the bottom
2. Click the big blue **"Create Web Service"** button
3. Render will start deploying your app!

---

## PART 4: Wait for Deployment (5-10 minutes)

### Step 4.1: Watch the Build Process

You'll see a page with logs scrolling by. This is Render:
1. Downloading your code from GitHub
2. Installing Python packages
3. Starting your app

**What you'll see:**
```
==> Cloning from https://github.com/...
==> Downloading Python...
==> Installing dependencies...
==> Starting server...
==> Your service is live 🎉
```

**This takes 5-10 minutes the first time.**

### Step 4.2: Check for Success

Look for these messages:
- ✅ **"Build successful"** - Good!
- ✅ **"Deploy live"** - Perfect!
- ✅ **"Your service is live"** - You're done!

**If you see errors:**
- Red text means something went wrong
- Common issues:
  - Missing package in requirements.txt
  - Wrong Python version
  - Typo in environment variables

### Step 4.3: Get Your Live URL

1. At the top of the page, you'll see your URL
2. It looks like: `https://cenaris-compliance.onrender.com`
3. Click on it to open your live app!

---

## PART 5: Test Your Deployed App (5 minutes)

### Step 5.1: Open Your App

1. Click your Render URL: `https://cenaris-compliance.onrender.com`
2. **First time might take 30-60 seconds** (database is initializing)
3. You should see the Cenaris login page!

### Step 5.2: Create an Account

1. Click "Sign Up" or "Register"
2. Create a new account with:
   - Email: your email
   - Password: your password
3. Login

### Step 5.3: Test Features

Try these to make sure everything works:
1. ✅ Upload a document
2. ✅ Go to Gap Analysis page
3. ✅ Generate a report
4. ✅ Check Evidence Repository

**If everything works - CONGRATULATIONS! 🎉**

---

## PART 6: Important Things to Know

### Your Free Render URL

Your app is now live at:
```
https://cenaris-compliance.onrender.com
```
(or whatever name you chose)

**You can share this URL with anyone!**

### Free Tier Limitations

⚠️ **App Sleeps After 15 Minutes**
- If no one visits for 15 minutes, the app goes to sleep
- First visit after sleep takes 30-60 seconds to wake up
- This is normal for free tier

⚠️ **Database Limited to 1GB**
- Good for testing
- For production, upgrade to Starter ($7/month)

### How to Upgrade (Optional)

If you want your app to be always on:

1. Go to Render Dashboard
2. Click on your web service "cenaris-compliance"
3. Click "Settings" tab
4. Scroll to "Instance Type"
5. Change from "Free" to "Starter"
6. Click "Save Changes"
7. Cost: $7/month for web service + $7/month for database = $14/month total

---

## PART 7: Updating Your App

When you make changes to your code:

```bash
# 1. Make your changes in your code
# 2. Commit the changes
git add .
git commit -m "Updated feature X"

# 3. Push to GitHub
git push origin main
```

**Render will automatically detect the push and redeploy!**
- Takes 3-5 minutes
- Your URL stays the same
- Zero downtime

---

## PART 8: Viewing Logs and Troubleshooting

### How to See Logs

1. Go to Render Dashboard
2. Click on your web service "cenaris-compliance"
3. Click "Logs" tab
4. You'll see real-time logs of your app

**Useful for:**
- Seeing errors
- Debugging issues
- Monitoring activity

### Common Issues and Fixes

#### Issue 1: "Application Error" when visiting URL

**Fix:**
1. Check logs in Render dashboard
2. Look for red error messages
3. Usually means:
   - Database connection failed (check DATABASE_URL)
   - Missing environment variable
   - Python package error

#### Issue 2: "Build Failed"

**Fix:**
1. Check build logs
2. Usually means:
   - Missing package in requirements.txt
   - Wrong Python version
   - Syntax error in code

#### Issue 3: App is Very Slow

**Fix:**
- This is normal for free tier
- App is waking up from sleep
- Upgrade to Starter ($7/month) for always-on

#### Issue 4: Database Connection Error

**Fix:**
1. Go to Environment Variables
2. Check DATABASE_URL is correct
3. Make sure you used **Internal Database URL** (not External)
4. Restart the service

---

## PART 9: Accessing Render Dashboard Features

### Shell Access (Run Commands)

1. Go to your web service in Render
2. Click "Shell" tab
3. You can run Python commands directly!

**Example - Initialize database manually:**
```bash
python -c "from app import create_app; from app.database import init_database; app = create_app('production'); app.app_context().push(); init_database()"
```

### Metrics (See Performance)

1. Click "Metrics" tab
2. See:
   - CPU usage
   - Memory usage
   - Request count
   - Response times

### Settings (Change Configuration)

1. Click "Settings" tab
2. You can:
   - Change instance type
   - Update environment variables
   - Change build/start commands
   - Delete service

---

## PART 10: Costs Summary

### Free Tier (What You Have Now):
- ✅ Web Service: $0/month
- ✅ PostgreSQL: $0/month
- ⚠️ App sleeps after 15 min
- ⚠️ Database may be deleted after 90 days of inactivity
- **Total: $0/month**

### Starter Tier (Recommended for Production):
- ✅ Web Service: $7/month (always on, no sleeping)
- ✅ PostgreSQL: $7/month (10GB, persistent)
- ✅ Better performance
- ✅ More reliable
- **Total: $14/month**

### When to Upgrade?
- When you're ready to show clients
- When you need it always available
- When you have real users
- When you need more storage

---

## 🎉 YOU'RE DONE!

Your app is now live at:
**https://cenaris-compliance.onrender.com**

### What You Accomplished:
✅ Pushed code to GitHub
✅ Created PostgreSQL database on Render
✅ Deployed Flask app to Render
✅ Configured environment variables
✅ Got a live URL (no custom domain needed!)

### Share With Adam:
Send him the URL and he can access it from anywhere!

---

## Need Help?

**Render Documentation:**
- https://render.com/docs

**Render Community Forum:**
- https://community.render.com

**Check Your Logs:**
- Render Dashboard → Your Service → Logs

**Common Commands:**
```bash
# Update your app
git add .
git commit -m "Update"
git push origin main

# Check if git is initialized
git status

# See your remote URL
git remote -v
```

---

## Quick Reference Card

**Your URLs:**
- Render Dashboard: https://dashboard.render.com
- Your App: https://cenaris-compliance.onrender.com
- GitHub Repo: https://github.com/YOUR_USERNAME/cenaris-compliance

**Your Database:**
- Name: cenaris-db
- Database: cenaris_production
- User: cenaris_user

**To Update App:**
```bash
git add .
git commit -m "Update"
git push origin main
```

**To View Logs:**
Render Dashboard → cenaris-compliance → Logs

---

Good luck! You've got this! 🚀
