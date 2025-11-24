# 🏗️ MILESTONE 1: Foundation & Multi-Tenancy

**Duration:** 4 weeks  
**Cost:** $15,000 - $20,000 AUD  
**Team:** 2 Backend Developers + 1 Frontend Developer

---

## Objectives

Transform single-user MVP into multi-tenant SaaS platform where multiple healthcare organizations can use the system independently.

---

## Features to Build

### 1.1 User Registration & Onboarding (Week 1)

**Features:**
- Public signup page for new organizations
- Email verification system
- Organization creation wizard
- User profile setup
- Password reset functionality
- Welcome email automation

**Technical:**
- Email service integration (SendGrid/AWS SES)
- Token-based email verification
- Password strength validation
- CAPTCHA for bot prevention

**Deliverables:**
- `/signup` route with organization creation
- Email templates (welcome, verification, password reset)
- User onboarding flow (5 steps)

---

### 1.2 Organization Management (Week 1-2)

**Features:**
- Organization profile (name, ABN, address, contact)
- Organization settings page
- Branding (logo upload, colors)
- Multiple users per organization
- Organization admin dashboard

**Database Schema:**
```sql
organizations (
  id, name, abn, address, contact_email, 
  logo_url, created_at, subscription_tier
)

users (
  id, email, password_hash, organization_id,
  role, first_name, last_name, created_at
)
```

**Deliverables:**
- Organization CRUD operations
- Settings page UI
- Logo upload to Azure Blob
- Organization switcher (for users in multiple orgs)

---

### 1.3 Production Database Migration (Week 2)

**Features:**
- Migrate from SQLite to PostgreSQL
- Database connection pooling
- Migration scripts for existing data
- Backup strategy

**Technical:**
- Azure Database for PostgreSQL
- SQLAlchemy ORM updates
- Alembic for migrations
- Automated daily backups

**Deliverables:**
- PostgreSQL database setup
- All tables migrated
- Connection string management
- Backup automation script

---

### 1.4 Data Isolation & Multi-Tenancy (Week 3)

**Features:**
- Organization-level data isolation
- ADLS folder structure per organization
- Document storage per organization
- Compliance data segregation

**ADLS Structure:**
```
/organizations/{org_id}/
  /documents/
  /compliance-results/
  /reports/
```

**Technical:**
- Row-level security in database
- Organization context middleware
- ADLS path management per org
- Query filters for all data access

**Deliverables:**
- Multi-tenant data access layer
- Organization context in all queries
- ADLS folder creation on signup
- Data isolation testing

---

### 1.5 User Invitation System (Week 3-4)

**Features:**
- Invite team members by email
- Invitation acceptance flow
- Pending invitations management
- Resend invitation option

**Technical:**
- Invitation tokens (24-hour expiry)
- Email invitation templates
- User role assignment on acceptance

**Deliverables:**
- `/invite` endpoint
- Invitation email template
- Invitation management UI
- Accept invitation flow

---

### 1.6 Enhanced Authentication (Week 4)

**Features:**
- Remember me functionality
- Session management
- Login activity tracking
- Force logout on password change
- Account lockout after failed attempts

**Security:**
- Secure session cookies
- CSRF protection
- Rate limiting on login
- IP-based suspicious activity detection

**Deliverables:**
- Enhanced login security
- Session management dashboard
- Activity log for users
- Security settings page

---

## Testing & QA

- Unit tests for all new features
- Integration tests for multi-tenancy
- Manual testing of signup flow
- Data isolation verification
- Performance testing with 10 organizations

---

## Milestone 1 Deliverables

✅ Working signup flow for new organizations  
✅ PostgreSQL production database  
✅ Multi-tenant data isolation  
✅ User invitation system  
✅ Organization management  
✅ Enhanced security features  

---

## Success Metrics

- 5+ test organizations created
- 20+ test users across organizations
- Zero data leakage between organizations
- < 2 second page load times
- 100% test coverage for critical paths
