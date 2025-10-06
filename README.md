# Cenaris Compliance Management System

A professional, secure, and modern compliance document management system built with Flask and Azure Data Lake Storage. This enterprise-grade solution provides secure document storage, user authentication, and an intuitive web interface designed specifically for compliance professionals.

![Python](https://img.shields.io/badge/python-v3.8+-blue.svg)
![Flask](https://img.shields.io/badge/flask-v2.3.3-green.svg)
![Azure](https://img.shields.io/badge/azure-ADLS%20Gen2-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## 🌟 Features

### 🔐 **Security & Authentication**
- Secure user registration and login system
- Password hashing with Werkzeug security
- Session management with Flask-Login
- CSRF protection on all forms
- Enterprise-grade security headers
- Strong session protection

### 📁 **Document Management**
- Upload PDF and DOCX files (up to 16MB)
- Secure storage in Azure Data Lake Storage Gen2
- Organized file structure: `compliance-docs/YYYY/MM/user_ID/filename`
- Document metadata tracking
- File validation and type checking
- Automatic file naming with timestamps and unique IDs

### 🎨 **Professional UI/UX**
- Clean, modern, responsive design
- Bootstrap 5 styling with custom compliance theme
- Mobile-friendly interface
- Professional white/light color scheme
- Intuitive navigation and user flow
- Real-time feedback and notifications

### ☁️ **Azure Integration**
- Azure Data Lake Storage Gen2 support
- Automatic fallback to Blob Storage
- Secure credential management
- Connection testing and validation
- Organized folder structure for compliance

### 📊 **Dashboard & Repository**
- Professional dashboard with upload functionality
- Evidence repository with table and grid views
- Document statistics and summaries
- Recent documents display
- User-specific document management

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Azure Storage Account with ADLS Gen2 enabled
- Virtual environment (recommended)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd cenaris-compliance-management
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Azure credentials**
   ```bash
   python3 setup_azure.py
   
🔑 Azure Storage Connection String: DefaultEndpointsProtocol=https;AccountName=<acc_name>;AccountKey=<acc_key>

📦 Container/File System Name (default: compliance-documents): user-uploads

After this please enter the secret key in the .env file 
   ```
   
   You'll be prompted to enter:
   - Azure Storage Connection String
   - Container/File System Name (default: user-uploads)

5. **Initialize the database**
   ```bash
   python3 init_db.py
   ```
   
   Choose 'Y' to create sample users for testing.

6. **Run the application**
   ```bash
   python3 run.py
   ```

7. **Access the application**
   
   Open your browser to: `http://127.0.0.1:5000`

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the root directory:

```env
# Flask Configuration
FLASK_CONFIG=development
SECRET_KEY=your-super-secret-key-here

# Azure Data Lake Storage Configuration
AZURE_STORAGE_CONNECTION_STRING=your_azure_connection_string
AZURE_CONTAINER_NAME=user-uploads

# Database Configuration
DATABASE_URL=sqlite:///compliance.db
```

### Azure Setup

1. **Create Azure Storage Account**
   - Enable Data Lake Storage Gen2
   - Create a container (e.g., "user-uploads")
   - Get the connection string from Access Keys

2. **Configure Permissions**
   - Ensure proper access permissions for the storage account
   - Configure network access rules if needed

## 👥 Default Users

After running `init_db.py`, you can use these test accounts:

| Email | Password | Role |
|-------|----------|------|
| admin@compliance.com | admin123 | Administrator |
| user@compliance.com | user123 | Regular User |

## 📁 Project Structure

```
cenaris-compliance-management/
├── app/
│   ├── __init__.py              # Flask application factory
│   ├── models.py                # Database models (User, Document)
│   ├── decorators.py            # Custom decorators
│   ├── database.py              # Database utilities
│   ├── auth/                    # Authentication blueprint
│   │   ├── __init__.py
│   │   ├── routes.py            # Login/signup routes
│   │   └── forms.py             # WTForms for authentication
│   ├── main/                    # Main application blueprint
│   │   ├── __init__.py
│   │   └── routes.py            # Dashboard and repository routes
│   ├── upload/                  # File upload blueprint
│   │   ├── __init__.py
│   │   └── routes.py            # Upload handling routes
│   ├── services/                # Business logic services
│   │   ├── __init__.py
│   │   ├── azure_storage.py     # Azure ADLS integration
│   │   └── file_validation.py   # File validation service
│   └── templates/               # Jinja2 templates
│       ├── base.html            # Base template
│       ├── auth/                # Authentication templates
│       └── main/                # Main application templates
├── config.py                    # Configuration classes
├── requirements.txt             # Python dependencies
├── run.py                      # Application runner
├── app.py                      # Alternative runner
├── init_db.py                  # Database initialization
├── setup_azure.py              # Azure setup utility
├── .env.example                # Environment variables example
├── .gitignore                  # Git ignore rules
└── README.md                   # This file
```

## 🔒 Security Features

- **Password Security**: Werkzeug password hashing
- **Session Security**: Secure session cookies, strong protection
- **CSRF Protection**: All forms protected against CSRF attacks
- **Security Headers**: X-Content-Type-Options, X-Frame-Options, etc.
- **Input Validation**: Comprehensive file and form validation
- **SQL Injection Prevention**: Parameterized queries
- **File Upload Security**: Type validation, size limits, secure naming

## 📊 File Organization

Documents are automatically organized in Azure ADLS with the following structure:

```
compliance-docs/
├── 2025/                        # Year
│   ├── 01/                      # Month (January)
│   │   ├── user_1/              # User ID
│   │   │   ├── 20250115_143022_abc123.pdf
│   │   │   └── 20250115_143045_def456.docx
│   │   └── user_2/
│   │       └── 20250115_144000_ghi789.pdf
│   └── 02/                      # Month (February)
│       └── user_1/
│           └── 20250201_090000_jkl012.pdf
```

## 🛠️ Development

### Running in Development Mode

```bash
export FLASK_ENV=development
export FLASK_DEBUG=1
python3 run.py
```

### Testing Azure Connection

```bash
python3 setup_azure.py test
```

### Database Operations

```bash
# Reset database
python3 init_db.py

# Create sample data
python3 -c "
from app import create_app
from app.database import create_sample_data
app = create_app()
with app.app_context():
    create_sample_data()
"
```

## 🚀 Deployment

### Production Configuration

1. **Set environment variables**
   ```bash
   export FLASK_CONFIG=production
   export SECRET_KEY=your-production-secret-key
   export AZURE_STORAGE_CONNECTION_STRING=your-production-connection-string
   ```

2. **Use production WSGI server**
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:8000 app:app
   ```

3. **Configure reverse proxy** (Nginx recommended)

4. **Set up SSL/TLS certificates**

5. **Configure Azure SQL Database** (optional, for production scale)

## 📋 API Endpoints

### Authentication
- `GET/POST /auth/login` - User login
- `GET/POST /auth/signup` - User registration
- `POST /auth/logout` - User logout

### Main Application
- `GET /` - Home page
- `GET /dashboard` - User dashboard
- `GET /evidence-repository` - Document repository

### File Upload
- `POST /upload` - Upload document
- `POST /upload/validate` - Validate file (AJAX)
- `GET /upload/info` - Upload configuration info

## 🔧 Troubleshooting

### Common Issues

1. **Azure Connection Failed**
   ```bash
   # Test connection
   python3 setup_azure.py test
   
   # Check credentials in .env file
   cat .env
   ```

2. **Database Errors**
   ```bash
   # Reinitialize database
   python3 init_db.py
   ```

3. **File Upload Issues**
   - Check file size (max 16MB)
   - Verify file type (PDF, DOCX only)
   - Ensure Azure credentials are correct

4. **Template Errors**
   ```bash
   # Check for datetime formatting issues
   # Ensure all datetime objects are properly handled
   ```

## 📝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Flask** - Web framework
- **Azure** - Cloud storage and services
- **Bootstrap** - UI framework
- **Font Awesome** - Icons
- **SQLite** - Database

## 📞 Support

For support and questions:

- Create an issue in the repository
- Check the troubleshooting section
- Review the configuration documentation

---

**Cenaris Compliance Management System** - Professional document management for compliance professionals.

Built with ❤️ for enterprise compliance needs.
