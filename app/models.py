from datetime import datetime, timezone
from flask import g
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
    # Org-scoped RBAC role reference (preferred)
    role_id = db.Column(db.Integer, db.ForeignKey('rbac_roles.id'), nullable=True)
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

    # Avoid large JOINs on every membership lookup; load related rows only when needed.
    department = db.relationship('Department', lazy='selectin')
    rbac_role = db.relationship('RBACRole', lazy='selectin')

    @property
    def display_role_name(self) -> str:
        if self.rbac_role and (self.rbac_role.name or '').strip():
            return (self.rbac_role.name or '').strip()
        return (self.role or 'User').strip() or 'User'


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
    roles = db.relationship('RBACRole', backref='organization', lazy='dynamic', cascade='all, delete-orphan')

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
        return bool(self.has_permission('users.manage', org_id=org_id))

    def active_membership(self, org_id: int | None = None) -> OrganizationMembership | None:
        org_id = int(org_id) if org_id is not None else (int(self.organization_id) if self.organization_id else None)
        if not org_id:
            return None

        # Request-scoped cache to avoid repeated DB queries when templates/routes
        # call permission checks multiple times on the same request.
        try:
            cache = getattr(g, '_active_membership_cache', None)
            if cache is None:
                cache = {}
                setattr(g, '_active_membership_cache', cache)
            key = (int(self.id), int(org_id))
            if key in cache:
                return cache[key]
        except Exception:
            cache = None
            key = None

        membership = self.memberships.filter_by(organization_id=org_id, is_active=True).first()
        try:
            if cache is not None and key is not None:
                cache[key] = membership
        except Exception:
            pass
        return membership

    def active_role_name(self, org_id: int | None = None) -> str | None:
        membership = self.active_membership(org_id=org_id)
        return membership.display_role_name if membership else None

    def has_permission(self, code: str, org_id: int | None = None) -> bool:
        code = (code or '').strip()
        if not code:
            return False

        membership = self.active_membership(org_id=org_id)
        if not membership:
            return False

        # Preferred: RBAC role with permissions.
        if membership.rbac_role:
            try:
                perm_cache = getattr(g, '_role_permission_codes_cache', None)
                if perm_cache is None:
                    perm_cache = {}
                    setattr(g, '_role_permission_codes_cache', perm_cache)
                role_id = int(getattr(membership.rbac_role, 'id', 0) or 0)
                if role_id and role_id in perm_cache:
                    codes = perm_cache[role_id]
                else:
                    codes = membership.rbac_role.effective_permission_codes()
                    if role_id:
                        perm_cache[role_id] = codes
            except Exception:
                codes = membership.rbac_role.effective_permission_codes()

            return code in codes

        # Legacy fallback (until role_id is fully backfilled everywhere)
        legacy = (membership.role or '').strip().lower()
        if legacy in {'admin', 'organisation administrator', 'organization administrator'}:
            return True

        # Conservative defaults for legacy non-admin members.
        return code in {'documents.view', 'documents.upload'}

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

    uploader = db.relationship('User', foreign_keys=[uploaded_by], lazy='select')


rbac_role_permissions = db.Table(
    'rbac_role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('rbac_roles.id', ondelete='CASCADE'), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('rbac_permissions.id', ondelete='CASCADE'), primary_key=True),
)


rbac_role_inherits = db.Table(
    'rbac_role_inherits',
    db.Column('role_id', db.Integer, db.ForeignKey('rbac_roles.id', ondelete='CASCADE'), primary_key=True),
    db.Column('inherited_role_id', db.Integer, db.ForeignKey('rbac_roles.id', ondelete='CASCADE'), primary_key=True),
)


class RBACPermission(db.Model):
    __tablename__ = 'rbac_permissions'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(255))


class RBACRole(db.Model):
    __tablename__ = 'rbac_roles'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    description = db.Column(db.String(255))
    is_system = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    # These collections can be large; selectin avoids row explosion from JOINs.
    permissions = db.relationship('RBACPermission', secondary=rbac_role_permissions, lazy='selectin')
    inherits = db.relationship(
        'RBACRole',
        secondary=rbac_role_inherits,
        primaryjoin=(rbac_role_inherits.c.role_id == id),
        secondaryjoin=(rbac_role_inherits.c.inherited_role_id == id),
        lazy='selectin',
    )

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'name', name='uq_rbac_roles_org_name'),
        db.Index('ix_rbac_roles_org_id', 'organization_id'),
    )

    def effective_permission_codes(self) -> set[str]:
        """Return direct + inherited permission codes (cycle-safe)."""
        seen_role_ids: set[int] = set()
        codes: set[str] = set()

        def walk(role: 'RBACRole') -> None:
            if not role or not role.id:
                return
            rid = int(role.id)
            if rid in seen_role_ids:
                return
            seen_role_ids.add(rid)

            for perm in (role.permissions or []):
                c = (getattr(perm, 'code', None) or '').strip()
                if c:
                    codes.add(c)

            for inherited in (role.inherits or []):
                walk(inherited)

        walk(self)
        return codes


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