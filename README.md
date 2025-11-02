# Cenaris Compliance Management System

🌐 **Live Site:** http://cenaris-app-1762093207.westus2.azurecontainer.io:8000

## 🚀 Auto-Deployment
Push to main branch → Automatically deploys to Azure via GitHub Actions

## 🔧 Setup GitHub Actions
1. Add these secrets to your GitHub repo:
   - `AZURE_CLIENT_ID`
   - `AZURE_TENANT_ID`: `5fd15f41-337a-4de2-85eb-2d56c2e7d2f3`
   - `AZURE_SUBSCRIPTION_ID`: `ea805a46-0575-42aa-b92c-4296d6ce5d3a`

2. Push code changes:
```bash
git add .
git commit -m "Your changes"
git push origin main
```

## 📁 Project Structure
- `app/` - Flask application
- `Dockerfile` - Container configuration
- `.github/workflows/` - Auto-deployment
- `requirements.txt` - Python dependencies
