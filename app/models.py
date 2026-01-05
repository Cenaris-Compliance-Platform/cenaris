from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class OrganizationMembership(db.Model):
    __tablename__ = 'organization_memberships'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    role = db.Column(db.String(20), default='User', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    # Invite tracking (org membership invites)
    invited_at = db.Column(db.DateTime, nullable=True)
    invited_by_user_id = db.Column(db.Integer, nullable=True)
    invite_last_sent_at = db.Column(db.DateTime, nullable=True)
    invite_send_count = db.Column(db.Integer, default=0, nullable=False)
    invite_accepted_at = db.Column(db.DateTime, nullable=True)
    invite_revoked_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'user_id', name='uq_org_membership_org_user'),
    )

    department = db.relationship('Department', lazy='joined')


class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    # Store a Bootstrap contextual color token: primary/secondary/success/info/warning/danger/dark
    color = db.Column(db.String(20), nullable=False, default='primary')
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    # Relationship to see members in this department
    memberships = db.relationship('OrganizationMembership', foreign_keys='OrganizationMembership.department_id', lazy='dynamic', overlaps="department")

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'name', name='uq_departments_org_name'),
        db.Index('ix_departments_org_id', 'organization_id'),
    )


class Organization(db.Model):
    __tablename__ = 'organizations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    trading_name = db.Column(db.String(100))
    abn = db.Column(db.String(20))
    organization_type = db.Column(db.String(40))
    contact_email = db.Column(db.String(120))
    address = db.Column(db.String(255))
    industry = db.Column(db.String(60))
    billing_email = db.Column(db.String(120))
    billing_address = db.Column(db.String(255))
    logo_blob_name = db.Column(db.String(255))
    logo_content_type = db.Column(db.String(100))
    subscription_tier = db.Column(db.String(20), default='Starter')

    # Compliance + privacy acknowledgements
    operates_in_australia = db.Column(db.Boolean, nullable=True)
    declarations_accepted_at = db.Column(db.DateTime, nullable=True)
    declarations_accepted_by_user_id = db.Column(db.Integer, nullable=True)
    data_processing_ack_at = db.Column(db.DateTime, nullable=True)
    data_processing_ack_by_user_id = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    # Relationships
    users = db.relationship('User', backref='organization', lazy='dynamic')
    documents = db.relationship('Document', backref='organization', lazy='dynamic')
    memberships = db.relationship('OrganizationMembership', backref='organization', lazy='dynamic', cascade='all, delete-orphan')
    departments = db.relationship('Department', backref='organization', lazy='dynamic', cascade='all, delete-orphan')

    def core_details_complete(self) -> bool:
        return bool(
            (self.name or '').strip()
            and (self.abn or '').strip()
            and (self.organization_type or '').strip()
            and (self.contact_email or '').strip()
            and (self.address or '').strip()
            and (self.industry or '').strip()
        )

    def declarations_complete(self) -> bool:
        return bool(self.operates_in_australia is True and self.declarations_accepted_at)

    def data_privacy_ack_complete(self) -> bool:
        return bool(self.data_processing_ack_at)

    def billing_complete(self) -> bool:
        return bool((self.billing_email or '').strip() and (self.billing_address or '').strip())

    def onboarding_complete(self) -> bool:
        # "Onboarding complete" means the user can access the workspace.
        # Billing can be deferred; uploads/reports are gated separately.
        return bool(self.core_details_complete() and self.declarations_complete() and self.data_privacy_ack_complete())


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256))

    # Admin/account-holder details
    first_name = db.Column(db.String(60))
    last_name = db.Column(db.String(60))
    title = db.Column(db.String(80))
    mobile_number = db.Column(db.String(40))
    time_zone = db.Column(db.String(60))

    full_name = db.Column(db.String(100))
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    welcome_email_sent_at = db.Column(db.DateTime, nullable=True)
    terms_accepted_at = db.Column(db.DateTime, nullable=True)
    password_changed_at = db.Column(db.DateTime, nullable=True)
    avatar_blob_name = db.Column(db.String(255))
    avatar_content_type = db.Column(db.String(100))
    role = db.Column(db.String(20), default='User')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)

    # Security: login tracking / lockout
    last_login_at = db.Column(db.DateTime, nullable=True)
    password_changed_at = db.Column(db.DateTime, nullable=True)
    last_failed_login_at = db.Column(db.DateTime, nullable=True)
    failed_login_count = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    session_version = db.Column(db.Integer, default=1, nullable=False)  # For logout-all-devices

    memberships = db.relationship('OrganizationMembership', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def display_name(self) -> str:
        name = (self.full_name or '').strip()
        if name:
            return name
        parts = [p.strip() for p in [(self.first_name or ''), (self.last_name or '')] if (p or '').strip()]
        if parts:
            return ' '.join(parts)
        return (self.email or '').strip()

    def is_org_admin(self, org_id: int | None = None) -> bool:
        org_id = int(org_id) if org_id is not None else (int(self.organization_id) if self.organization_id else None)
        if not org_id:
            return False

        membership = self.memberships.filter_by(organization_id=org_id, is_active=True).first()
        return bool(membership and (membership.role or '').strip().lower() in {'admin', 'organisation administrator', 'organization administrator'})

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.password_changed_at = datetime.now(timezone.utc)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)


class Document(db.Model):
    __tablename__ = 'documents'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    blob_name = db.Column(db.String(255))
    file_size = db.Column(db.Integer)
    content_type = db.Column(db.String(50))
    uploaded_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)

    uploader = db.relationship('User', foreign_keys=[uploaded_by], lazy='joined')

    uploader = db.relationship('User', foreign_keys=[uploaded_by], lazy='joined')


class LoginEvent(db.Model):
    __tablename__ = 'login_events'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    provider = db.Column(db.String(20), nullable=False, default='password')
    success = db.Column(db.Boolean, nullable=False, default=False)
    reason = db.Column(db.String(80), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)

    user = db.relationship('User', lazy='joined')

    __table_args__ = (
        db.Index('ix_login_events_user_id_created_at', 'user_id', 'created_at'),
        db.Index('ix_login_events_ip_created_at', 'ip_address', 'created_at'),
    )


class SuspiciousIP(db.Model):
    __tablename__ = 'suspicious_ips'

    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45), nullable=False, unique=True)
    window_started_at = db.Column(db.DateTime, nullable=True)
    failure_count = db.Column(db.Integer, default=0, nullable=False)
    blocked_until = db.Column(db.DateTime, nullable=True)
    last_seen_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.Index('ix_suspicious_ips_blocked_until', 'blocked_until'),
    )