# Cenaris Compliance Management System

A professional, secure, and modern compliance document management system built with Flask and Azure Data Lake Storage. This enterprise-grade solution provides secure document storage, user authentication, and an intuitive web interface designed specifically for compliance professionals.

![Python](https://img.shields.io/badge/python-v3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-v2.3.3-green.svg)
![Azure](https://img.shields.io/badge/azure-ADLS%20Gen2-blue.svg)

## 🌟 Features

- **🔐 Secure Authentication** - User registration, login, and session management
- **📁 Document Management** - Upload and manage PDF/DOCX files (up to 16MB)
- **☁️ Azure Storage** - Secure storage in Azure Data Lake Storage Gen2
- **🤖 AI Evidence** - AI-powered compliance evidence analysis
- **📊 Gap Analysis** - Identify compliance gaps and requirements
- **📈 ML Results** - Machine learning compliance scoring
- **🎨 Modern UI** - Clean, responsive Bootstrap 5 interface
- **👥 User Roles** - Role-based access control
- **📤 Audit Export** - Generate compliance reports

---

## 🚀 Quick Start (5 Minutes)

### Prerequisites

- **Python 3.8+** installed
- **Azure Storage Account** with connection string
- **Git** installed

### Step 1: Clone the Repository

```bash
git clone <your-repo-url>
cd cenaris
```

### Step 2: Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Azure Storage

Create a `.env` file in the root directory:

```bash
# Create .env file
touch .env
```

Add your Azure credentials to `.env`:

```env
# Flask Configuration
FLASK_CONFIG=development
SECRET_KEY=your-super-secret-key-change-this

# Azure Storage Configuration
AZURE_STORAGE_CONNECTION_STRING=DefaultEndpointsProtocol=https;AccountName=YOUR_ACCOUNT;AccountKey=YOUR_KEY;EndpointSuffix=core.windows.net
AZURE_CONTAINER_NAME=user-uploads
```

**How to get Azure Storage Connection String:**
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your Storage Account
3. Click "Access keys" in the left menu
4. Copy "Connection string" from key1 or key2

### Step 5: Initialize Database

```bash
python3 init_db.py
```

When prompted, type `Y` to create sample users for testing.

### Step 6: Run the Application

```bash
python3 run.py
```

The app will be available at: **http://127.0.0.1:8081**

---

## 👥 Default Test Users

After running `init_db.py`, you can login with:

| Email | Password | Role |
|-------|----------|------|
| admin@compliance.com | admin123 | Administrator |
| user@compliance.com | user123 | Regular User |

**⚠️ Change these passwords in production!**

---

## 📁 Project Structure

```
cenaris/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── models.py                # Database models
│   ├── database.py              # Database utilities
│   ├── auth/                    # Authentication routes
│   │   ├── routes.py
│   │   └── forms.py
│   ├── main/                    # Main application routes
│   │   └── routes.py
│   ├── upload/                  # File upload handling
│   │   └── routes.py
│   ├── services/                # Business logic
│   │   ├── azure_storage.py
│   │   ├── azure_data_service.py
│   │   └── file_validation.py
│   └── templates/               # HTML templates
│       ├── base.html
│       ├── auth/
│       └── main/
├── config.py                    # Configuration
├── requirements.txt             # Python dependencies
├── run.py                       # Application runner
├── init_db.py                   # Database initialization
├── .env                         # Environment variables (create this)
└── README.md                    # This file
```

---

## 🔧 Configuration

### Environment Variables

Create a `.env` file with these variables:

```env
# Flask Settings
FLASK_CONFIG=development          # or 'production'
SECRET_KEY=your-secret-key-here   # Generate with: openssl rand -hex 32

# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=your-connection-string
AZURE_CONTAINER_NAME=user-uploads

# Database (optional)
DATABASE_URL=sqlite:///compliance.db
```

### Azure Storage Setup

1. **Create Storage Account:**
   - Go to Azure Portal
   - Create a new Storage Account
   - Enable "Data Lake Storage Gen2" (optional)

2. **Create Container:**
   - In your storage account, create a container named `user-uploads`
   - Set access level to "Private"

3. **Get Connection String:**
   - Go to "Access keys" in your storage account
   - Copy the connection string

---

## 🛠️ Development

### Running in Development Mode

```bash
# Set environment
export FLASK_ENV=development
export FLASK_DEBUG=1

# Run app
python3 run.py
```

### Database Operations

```bash
# Reset database
python3 init_db.py

# Create new migration (if using Flask-Migrate)
flask db migrate -m "Description"
flask db upgrade
```

### Testing Azure Connection

```bash
python3 setup_azure.py test
```

---

## 📊 Features Guide

### 1. Dashboard
- View recent documents
- See ML compliance scores
- Quick access to all features

### 2. Evidence Repository
- Upload compliance documents
- View all uploaded files
- Organized by date and user

### 3. AI Evidence
- AI-powered evidence analysis
- Confidence scoring
- Framework mapping (ISO 27001, SOC 2, etc.)

### 4. Gap Analysis
- Identify compliance gaps
- Track requirements status
- Visual compliance metrics

### 5. ML Results
- Machine learning compliance analysis
- Detailed requirement breakdown
- Compliance scoring

### 6. Audit Export
- Generate compliance reports
- Export documentation
- Audit trail

---

## 🚀 Deployment

### Local Production Mode

```bash
# Install production server
pip install gunicorn

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 run:app
```

### Environment Setup for Production

1. **Set production environment variables:**
```bash
export FLASK_CONFIG=production
export SECRET_KEY=$(openssl rand -hex 32)
```

2. **Use production database** (PostgreSQL recommended)

3. **Configure reverse proxy** (Nginx/Apache)

4. **Enable HTTPS** with SSL certificates

---

## 🔒 Security

- **Password Hashing:** Werkzeug security
- **Session Management:** Flask-Login with strong protection
- **CSRF Protection:** Enabled on all forms
- **File Validation:** Type and size checking
- **SQL Injection Prevention:** Parameterized queries
- **Security Headers:** X-Content-Type-Options, X-Frame-Options, etc.

---

## 🐛 Troubleshooting

### Issue: "Azure Connection Failed"

**Solution:**
```bash
# Test your connection string
python3 setup_azure.py test

# Verify .env file exists and has correct values
cat .env
```

### Issue: "Database not found"

**Solution:**
```bash
# Reinitialize database
python3 init_db.py
```

### Issue: "Module not found"

**Solution:**
```bash
# Ensure virtual environment is activated
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: "Port already in use"

**Solution:**
```bash
# Kill process on port 8081
lsof -ti:8081 | xargs kill -9

# Or change port in run.py
```

---

## 📝 Common Tasks

### Add a New User

```python
from app import create_app
from app.models import User
from app.database import get_db

app = create_app()
with app.app_context():
    db = get_db()
    User.create(
        email='newuser@example.com',
        password='password123',
        full_name='New User'
    )
```

### Upload Files via Code

```python
from app.services.azure_storage import AzureStorageService

storage = AzureStorageService()
blob_url = storage.upload_file(
    file_data=file_content,
    filename='document.pdf',
    user_id=1
)
```

---

## 🔄 Updating the Application

```bash
# Pull latest changes
git pull origin main

# Update dependencies
pip install -r requirements.txt

# Run database migrations (if any)
python3 init_db.py

# Restart application
python3 run.py
```

---

## 📦 Dependencies

Main packages:
- **Flask 2.3.3** - Web framework
- **Flask-Login 0.6.3** - User authentication
- **azure-storage-blob 12.19.0** - Azure Blob Storage
- **azure-storage-file-datalake 12.14.0** - Azure Data Lake
- **WTForms 3.0.1** - Form handling
- **pandas 2.1.1** - Data processing
- **gunicorn 21.2.0** - Production server

See `requirements.txt` for complete list.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -m 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit a pull request

---

## 📄 License

This project is licensed under the MIT License.

---

## 📞 Support

For issues or questions:
- Create an issue in the repository
- Check the troubleshooting section above
- Review Azure Storage documentation

---

## 🎯 Quick Reference

```bash
# Setup
git clone <repo> && cd cenaris
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your Azure credentials
python3 init_db.py
python3 run.py

# Access
http://127.0.0.1:8081

# Test Login
admin@compliance.com / admin123
```

---

**Built with ❤️ for enterprise compliance needs.**
