from datetime import datetime, timezone
import threading
import time
from flask import g
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app import db


_RBAC_EFFECTIVE_PERMS_CACHE: dict[int, tuple[float, set[str]]] = {}
_RBAC_EFFECTIVE_PERMS_CACHE_LOCK = threading.Lock()


def _rbac_effective_perms_cache_ttl_seconds() -> int:
    # Keep small to reduce risk of stale permissions after edits.
    # Roles/permissions do not change frequently in typical usage.
    try:
        # Optional env override (seconds)
        import os

        v = int(os.environ.get('RBAC_PERMS_CACHE_SECONDS') or 60)
        return max(0, v)
    except Exception:
        return 60


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
        db.Index('ix_org_memberships_org_active', 'organization_id', 'is_active'),
        db.Index('ix_org_memberships_user_active', 'user_id', 'is_active'),
        db.Index('ix_org_memberships_user_org_active', 'user_id', 'organization_id', 'is_active'),
    )

    # Avoid large JOINs on every membership lookup; load related rows only when needed.
    department = db.relationship('Department', lazy='selectin')
    rbac_role = db.relationship('RBACRole', lazy='selectin')

    @property
    def display_role_name(self) -> str:
        name = None
        if self.rbac_role and (self.rbac_role.name or '').strip():
            name = (self.rbac_role.name or '').strip()
        else:
            name = (self.role or 'User').strip() or 'User'

        # UI spelling normalisation (AU English).
        # Some databases may still contain legacy US spelling for seeded roles.
        if (name or '').strip().lower() in {'organization admin', 'organization administrator'}:
            return 'Organisation Admin'

        return name


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
    acn = db.Column(db.String(20))
    organization_type = db.Column(db.String(40))
    contact_email = db.Column(db.String(120))
    contact_number = db.Column(db.String(40))
    address = db.Column(db.String(255))
    industry = db.Column(db.String(60))
    enabled_modules_list = db.Column(db.Text, nullable=True)
    billing_email = db.Column(db.String(120))
    billing_address = db.Column(db.String(255))
    billing_details = db.Column(db.Text)
    monthly_report_enabled = db.Column(db.Boolean, nullable=False, default=False)
    monthly_report_recipient_email = db.Column(db.String(120), nullable=True)
    logo_blob_name = db.Column(db.String(255))
    logo_content_type = db.Column(db.String(100))
    subscription_tier = db.Column(db.String(20), default='Starter')
    billing_plan_code = db.Column(db.String(40), nullable=True)
    billing_status = db.Column(db.String(40), nullable=True)
    stripe_customer_id = db.Column(db.String(80), nullable=True)
    stripe_subscription_id = db.Column(db.String(80), nullable=True)
    billing_current_period_start = db.Column(db.DateTime, nullable=True)
    billing_current_period_end = db.Column(db.DateTime, nullable=True)
    billing_trial_ends_at = db.Column(db.DateTime, nullable=True)
    billing_cancel_at_period_end = db.Column(db.Boolean, nullable=False, default=False)
    billing_internal_override = db.Column(db.Boolean, nullable=False, default=False)
    billing_override_reason = db.Column(db.String(255), nullable=True)
    billing_demo_override_until = db.Column(db.DateTime, nullable=True)
    billing_last_event_id = db.Column(db.String(80), nullable=True)
    billing_last_event_at = db.Column(db.DateTime, nullable=True)

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
    work_phone = db.Column(db.String(40))
    secondary_email = db.Column(db.String(120))
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
    extracted_text = db.Column(db.Text, nullable=True)
    search_text = db.Column(db.Text, nullable=True)
    ai_status = db.Column(db.String(50), nullable=True)
    ai_confidence = db.Column(db.Float, nullable=True)
    ai_focus_area = db.Column(db.String(80), nullable=True)
    ai_question = db.Column(db.Text, nullable=True)
    ai_summary = db.Column(db.Text, nullable=True)
    ai_provider = db.Column(db.String(50), nullable=True)
    ai_model = db.Column(db.String(120), nullable=True)
    ai_retrieval_mode = db.Column(db.String(20), nullable=True)
    ai_analysis_at = db.Column(db.DateTime, nullable=True)
    uploaded_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)

    uploader = db.relationship('User', foreign_keys=[uploaded_by], lazy='select')
    tags = db.relationship(
        'DocumentTag',
        secondary='document_tag_map',
        lazy='selectin',
        back_populates='documents',
    )

    __table_args__ = (
        db.Index('ix_documents_org_active_uploaded_at', 'organization_id', 'is_active', 'uploaded_at'),
    )


class DocumentTag(db.Model):
    __tablename__ = 'document_tags'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    normalized_name = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)

    documents = db.relationship(
        'Document',
        secondary='document_tag_map',
        lazy='selectin',
        back_populates='tags',
    )

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'normalized_name', name='uq_document_tags_org_normalized_name'),
        db.Index('ix_document_tags_org_name', 'organization_id', 'name'),
    )


class DocumentTagMap(db.Model):
    __tablename__ = 'document_tag_map'

    document_id = db.Column(db.Integer, db.ForeignKey('documents.id', ondelete='CASCADE'), primary_key=True)
    tag_id = db.Column(db.Integer, db.ForeignKey('document_tags.id', ondelete='CASCADE'), primary_key=True)
    linked_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        db.Index('ix_document_tag_map_tag_id', 'tag_id'),
    )


class ComplianceFrameworkVersion(db.Model):
    __tablename__ = 'compliance_framework_versions'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    jurisdiction = db.Column(db.String(20), nullable=False, default='AU')
    scheme = db.Column(db.String(50), nullable=False, default='NDIS')
    source_authority = db.Column(db.String(255), nullable=True)
    source_document = db.Column(db.String(255), nullable=True)
    source_url = db.Column(db.String(500), nullable=True)
    version_label = db.Column(db.String(50), nullable=False, default='v1.0')
    imported_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)
    imported_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    checksum = db.Column(db.String(64), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    imported_by = db.relationship('User', foreign_keys=[imported_by_user_id], lazy='select')
    requirements = db.relationship(
        'ComplianceRequirement',
        backref='framework_version',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    __table_args__ = (
        db.UniqueConstraint(
            'organization_id',
            'scheme',
            'version_label',
            name='uq_compliance_framework_org_scheme_version',
        ),
        db.Index('ix_compliance_framework_versions_org_active', 'organization_id', 'is_active'),
    )


class ComplianceRequirement(db.Model):
    __tablename__ = 'compliance_requirements'

    id = db.Column(db.Integer, primary_key=True)
    framework_version_id = db.Column(db.Integer, db.ForeignKey('compliance_framework_versions.id'), nullable=False)

    requirement_id = db.Column(db.String(120), nullable=False)
    module_type = db.Column(db.String(40), nullable=True)
    module_name = db.Column(db.String(255), nullable=True)
    standard_name = db.Column(db.String(255), nullable=True)
    outcome_code = db.Column(db.String(120), nullable=True)
    outcome_text = db.Column(db.Text, nullable=True)
    quality_indicator_code = db.Column(db.String(120), nullable=True)
    quality_indicator_text = db.Column(db.Text, nullable=True)

    applies_to_all_providers = db.Column(db.Boolean, default=False, nullable=False)
    registration_group_numbers = db.Column(db.String(255), nullable=True)
    registration_group_names = db.Column(db.Text, nullable=True)
    registration_group_source_url = db.Column(db.String(500), nullable=True)

    audit_type = db.Column(db.String(50), nullable=True)
    high_risk_flag = db.Column(db.Boolean, default=False, nullable=False)
    stage_1_applies = db.Column(db.Boolean, default=False, nullable=False)
    stage_2_applies = db.Column(db.Boolean, default=False, nullable=False)
    audit_test_methods = db.Column(db.Text, nullable=True)
    sampling_required = db.Column(db.Boolean, default=False, nullable=False)
    sampling_subject = db.Column(db.String(255), nullable=True)

    system_evidence_required = db.Column(db.Text, nullable=True)
    implementation_evidence_required = db.Column(db.Text, nullable=True)
    workforce_evidence_required = db.Column(db.Text, nullable=True)
    participant_evidence_required = db.Column(db.Text, nullable=True)

    requires_workforce_evidence = db.Column(db.Boolean, default=False, nullable=False)
    requires_participant_evidence = db.Column(db.Boolean, default=False, nullable=False)
    minimum_evidence_score_2 = db.Column(db.Text, nullable=True)
    best_practice_evidence_score_3 = db.Column(db.Text, nullable=True)
    common_nonconformity_patterns = db.Column(db.Text, nullable=True)
    gap_rule_1 = db.Column(db.Text, nullable=True)
    gap_rule_2 = db.Column(db.Text, nullable=True)
    gap_rule_3 = db.Column(db.Text, nullable=True)
    nc_severity_default = db.Column(db.String(50), nullable=True)
    evidence_owner_role = db.Column(db.String(120), nullable=True)
    review_frequency = db.Column(db.String(120), nullable=True)
    system_of_record = db.Column(db.String(255), nullable=True)
    audit_export_label = db.Column(db.String(255), nullable=True)
    source_version = db.Column(db.String(50), nullable=True)
    source_last_reviewed_date = db.Column(db.Date, nullable=True)
    change_trigger = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)

    org_assessments = db.relationship(
        'OrganizationRequirementAssessment',
        backref='requirement',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )
    evidence_links = db.relationship(
        'RequirementEvidenceLink',
        backref='requirement',
        lazy='dynamic',
        cascade='all, delete-orphan',
    )

    __table_args__ = (
        db.UniqueConstraint('framework_version_id', 'requirement_id', name='uq_compliance_requirement_per_framework'),
        db.Index('ix_compliance_requirements_requirement_id', 'requirement_id'),
        db.Index('ix_compliance_requirements_quality_indicator_code', 'quality_indicator_code'),
    )


class OrganizationRequirementAssessment(db.Model):
    __tablename__ = 'organization_requirement_assessments'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    requirement_id = db.Column(db.Integer, db.ForeignKey('compliance_requirements.id'), nullable=False)

    evidence_status_system = db.Column(db.String(20), nullable=False, default='Not assessed')
    evidence_status_implementation = db.Column(db.String(20), nullable=False, default='Not assessed')
    evidence_status_workforce = db.Column(db.String(20), nullable=False, default='Not assessed')
    evidence_status_participant = db.Column(db.String(20), nullable=False, default='Not assessed')
    best_practice_evidence_present = db.Column(db.Boolean, default=False, nullable=False)

    computed_score = db.Column(db.Integer, nullable=True)
    computed_flag = db.Column(db.String(30), nullable=True)

    last_assessed_at = db.Column(db.DateTime, nullable=True)
    last_assessed_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.now(timezone.utc),
        nullable=False,
        onupdate=datetime.now(timezone.utc),
    )

    last_assessed_by = db.relationship('User', foreign_keys=[last_assessed_by_user_id], lazy='select')

    __table_args__ = (
        db.UniqueConstraint('organization_id', 'requirement_id', name='uq_org_requirement_assessment'),
        db.Index('ix_org_requirement_assessments_org', 'organization_id'),
        db.Index('ix_org_requirement_assessments_flag', 'computed_flag'),
    )


class RequirementEvidenceLink(db.Model):
    __tablename__ = 'requirement_evidence_links'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    requirement_id = db.Column(db.Integer, db.ForeignKey('compliance_requirements.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('documents.id'), nullable=False)

    evidence_bucket = db.Column(db.String(30), nullable=False)
    rationale_note = db.Column(db.Text, nullable=True)
    linked_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    linked_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)

    linked_by = db.relationship('User', foreign_keys=[linked_by_user_id], lazy='select')
    document = db.relationship('Document', foreign_keys=[document_id], lazy='select')

    __table_args__ = (
        db.UniqueConstraint(
            'organization_id',
            'requirement_id',
            'document_id',
            'evidence_bucket',
            name='uq_requirement_evidence_link',
        ),
        db.Index('ix_requirement_evidence_links_org_requirement', 'organization_id', 'requirement_id'),
        db.Index('ix_requirement_evidence_links_document', 'document_id'),
    )


class DemoAnalysisResult(db.Model):
    """
    Persisted record of every AI demo analysis run.
    Uploaded file content is NOT stored — only metadata and the AI output.
    """
    __tablename__ = 'demo_analysis_results'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Input metadata (no file content stored)
    filename = db.Column(db.String(255), nullable=True)
    question = db.Column(db.Text, nullable=True)

    # AI outputs
    status = db.Column(db.String(50), nullable=True)      # Mature / OK / High risk gap / Critical gap
    confidence = db.Column(db.Float, nullable=True)       # 0.0–1.0
    analysis_mode = db.Column(db.String(20), default='balanced', nullable=False)
    summary = db.Column(db.Text, nullable=True)
    snippet_count = db.Column(db.Integer, default=0, nullable=False)
    citation_count = db.Column(db.Integer, default=0, nullable=False)

    # Engine metadata
    provider = db.Column(db.String(50), nullable=True)    # openrouter / deterministic
    model_used = db.Column(db.String(120), nullable=True)
    retrieval_mode = db.Column(db.String(20), nullable=True)  # hybrid / lexical

    organization = db.relationship('Organization', lazy='select')
    user = db.relationship('User', lazy='select')

    __table_args__ = (
        db.Index('ix_demo_analysis_org_created', 'organization_id', 'created_at'),
        db.Index('ix_demo_analysis_user_created', 'user_id', 'created_at'),
    )


class AIUsageEvent(db.Model):
    __tablename__ = 'ai_usage_events'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    event = db.Column(db.String(40), nullable=False)
    mode = db.Column(db.String(20), nullable=False)
    provider = db.Column(db.String(40), nullable=False)
    model = db.Column(db.String(120), nullable=False)
    prompt_tokens = db.Column(db.Integer, nullable=False, default=0)
    completion_tokens = db.Column(db.Integer, nullable=False, default=0)
    total_tokens = db.Column(db.Integer, nullable=False, default=0)
    latency_ms = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)

    organization = db.relationship('Organization', lazy='select')
    user = db.relationship('User', lazy='select')

    __table_args__ = (
        db.Index('ix_ai_usage_events_org_created_at', 'organization_id', 'created_at'),
        db.Index('ix_ai_usage_events_event_created_at', 'event', 'created_at'),
    )


class APIKey(db.Model):
    __tablename__ = 'api_keys'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    key_prefix = db.Column(db.String(20), nullable=False)
    key_hash = db.Column(db.String(64), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_used_at = db.Column(db.DateTime, nullable=True)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)

    organization = db.relationship('Organization', lazy='select')
    created_by = db.relationship('User', foreign_keys=[created_by_user_id], lazy='select')

    __table_args__ = (
        db.UniqueConstraint('key_hash', name='uq_api_keys_hash'),
        db.Index('ix_api_keys_org_active', 'organization_id', 'is_active'),
        db.Index('ix_api_keys_prefix', 'key_prefix'),
    )


class WebhookEndpoint(db.Model):
    __tablename__ = 'webhook_endpoints'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    name = db.Column(db.String(120), nullable=False)
    target_url = db.Column(db.String(500), nullable=False)
    events_csv = db.Column(db.Text, nullable=False, default='*')
    secret = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)

    organization = db.relationship('Organization', lazy='select')
    created_by = db.relationship('User', foreign_keys=[created_by_user_id], lazy='select')

    __table_args__ = (
        db.Index('ix_webhook_endpoints_org_active', 'organization_id', 'is_active'),
    )


class WebhookDelivery(db.Model):
    __tablename__ = 'webhook_deliveries'

    id = db.Column(db.Integer, primary_key=True)
    webhook_endpoint_id = db.Column(db.Integer, db.ForeignKey('webhook_endpoints.id'), nullable=False)
    event_type = db.Column(db.String(80), nullable=False)
    payload_json = db.Column(db.Text, nullable=False)
    success = db.Column(db.Boolean, default=False, nullable=False)
    status_code = db.Column(db.Integer, nullable=True)
    response_excerpt = db.Column(db.String(500), nullable=True)
    attempted_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)

    endpoint = db.relationship('WebhookEndpoint', lazy='select')

    __table_args__ = (
        db.Index('ix_webhook_deliveries_endpoint_attempted_at', 'webhook_endpoint_id', 'attempted_at'),
        db.Index('ix_webhook_deliveries_event_attempted_at', 'event_type', 'attempted_at'),
    )


class AdminNotification(db.Model):
    __tablename__ = 'admin_notifications'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False)
    actor_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    read_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    event_type = db.Column(db.String(60), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), nullable=False, default='info')
    link_url = db.Column(db.String(255), nullable=True)
    payload_json = db.Column(db.Text, nullable=True)

    is_read = db.Column(db.Boolean, nullable=False, default=False)
    read_at = db.Column(db.DateTime, nullable=True)
    email_sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)

    organization = db.relationship('Organization', lazy='select')
    actor = db.relationship('User', foreign_keys=[actor_user_id], lazy='select')
    read_by = db.relationship('User', foreign_keys=[read_by_user_id], lazy='select')

    __table_args__ = (
        db.Index('ix_admin_notifications_org_created_at', 'organization_id', 'created_at'),
        db.Index('ix_admin_notifications_org_read_created_at', 'organization_id', 'is_read', 'created_at'),
        db.Index('ix_admin_notifications_event_type', 'event_type'),
    )


class StripeBillingWebhookEvent(db.Model):
    __tablename__ = 'stripe_billing_webhook_events'

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(80), nullable=False)
    event_type = db.Column(db.String(80), nullable=False)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=True)
    processed_at = db.Column(db.DateTime, default=datetime.now(timezone.utc), nullable=False)

    organization = db.relationship('Organization', lazy='select')

    __table_args__ = (
        db.UniqueConstraint('event_id', name='uq_stripe_billing_webhook_event_id'),
        db.Index('ix_stripe_billing_webhook_events_org_processed', 'organization_id', 'processed_at'),
    )


class OrganizationAISettings(db.Model):
    __tablename__ = 'organization_ai_settings'

    id = db.Column(db.Integer, primary_key=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('organizations.id'), nullable=False, unique=True)
    policy_draft_use_llm = db.Column(db.Boolean, nullable=False, default=False)
    max_query_chars = db.Column(db.Integer, nullable=False, default=1200)
    max_top_k = db.Column(db.Integer, nullable=False, default=5)
    max_citation_text_chars = db.Column(db.Integer, nullable=False, default=600)
    max_answer_chars = db.Column(db.Integer, nullable=False, default=2000)
    max_policy_draft_chars = db.Column(db.Integer, nullable=False, default=6000)
    rag_rate_limit = db.Column(db.String(40), nullable=False, default='20 per minute')
    policy_rate_limit = db.Column(db.String(40), nullable=False, default='10 per minute')
    updated_at = db.Column(
        db.DateTime,
        default=datetime.now(timezone.utc),
        nullable=False,
        onupdate=datetime.now(timezone.utc),
    )
    updated_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    organization = db.relationship('Organization', lazy='select')
    updated_by = db.relationship('User', lazy='select')

    __table_args__ = (
        db.Index('ix_org_ai_settings_org_id', 'organization_id'),
    )


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
        try:
            rid = int(getattr(self, 'id', 0) or 0)
        except Exception:
            rid = 0

        ttl = _rbac_effective_perms_cache_ttl_seconds()
        if rid and ttl > 0:
            now = time.monotonic()
            with _RBAC_EFFECTIVE_PERMS_CACHE_LOCK:
                cached = _RBAC_EFFECTIVE_PERMS_CACHE.get(rid)
            if cached:
                expires_at, codes = cached
                if now < expires_at:
                    # Return a copy to avoid accidental mutation of cached set.
                    return set(codes)

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

        if rid and ttl > 0:
            try:
                expires_at = time.monotonic() + max(1, ttl)
                with _RBAC_EFFECTIVE_PERMS_CACHE_LOCK:
                    _RBAC_EFFECTIVE_PERMS_CACHE[rid] = (expires_at, set(codes))
            except Exception:
                pass
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