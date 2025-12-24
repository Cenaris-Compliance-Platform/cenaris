from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


class OrganizationMembership(db.Model):
    __tablename__ = 'organization_memberships'
    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), default='User', nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'user_id', name='uq_org_membership_org_user'),
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
    avatar_blob_name = db.Column(db.String(255))
    avatar_content_type = db.Column(db.String(100))
    role = db.Column(db.String(20), default='User')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)

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

        # Legacy fallback: some flows still set `role` directly.
        if (self.role or '').strip().lower() == 'admin':
            return True

        membership = self.memberships.filter_by(organization_id=org_id, is_active=True).first()
        return bool(membership and (membership.role or '').strip().lower() in {'admin', 'organisation administrator', 'organization administrator'})

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

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