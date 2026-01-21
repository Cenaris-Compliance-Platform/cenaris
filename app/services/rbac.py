from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app import db
from app.models import OrganizationMembership


@dataclass(frozen=True)
class BuiltinRoleKeys:
    ORG_ADMIN: str = 'Organisation Admin'
    COMPLIANCE_MANAGER: str = 'Compliance Manager'
    AUDITOR: str = 'Auditor'
    MEMBER: str = 'Member'


BUILTIN_ROLE_KEYS = BuiltinRoleKeys()


PERMISSIONS: dict[str, str] = {
    'documents.view': 'View documents',
    'documents.upload': 'Upload documents',
    'documents.delete': 'Delete documents',
    'audits.export': 'Export audit data',
    'org.manage': 'Manage organization profile/settings',
    'departments.manage': 'Manage departments',
    'users.invite': 'Invite users to organization',
    'users.manage': 'Manage users and memberships',
    'roles.manage': 'Manage roles and permissions',
}


DEFAULT_ROLE_GRANTS: dict[str, list[str]] = {
    BUILTIN_ROLE_KEYS.MEMBER: ['documents.view', 'documents.upload'],
    BUILTIN_ROLE_KEYS.AUDITOR: ['documents.view', 'audits.export'],
    BUILTIN_ROLE_KEYS.COMPLIANCE_MANAGER: ['documents.view', 'documents.upload', 'documents.delete', 'audits.export'],
    BUILTIN_ROLE_KEYS.ORG_ADMIN: ['org.manage', 'departments.manage', 'users.invite', 'users.manage', 'roles.manage'],
}


DEFAULT_ROLE_INHERITANCE: list[tuple[str, str]] = [
    (BUILTIN_ROLE_KEYS.ORG_ADMIN, BUILTIN_ROLE_KEYS.COMPLIANCE_MANAGER),
    (BUILTIN_ROLE_KEYS.COMPLIANCE_MANAGER, BUILTIN_ROLE_KEYS.MEMBER),
    (BUILTIN_ROLE_KEYS.AUDITOR, BUILTIN_ROLE_KEYS.MEMBER),
]


def ensure_rbac_seeded_for_org(org_id: int) -> None:
    """Idempotently ensure permissions + default roles exist for an organization."""
    from app.models import RBACPermission, RBACRole

    if not org_id:
        return

    # Fast exit: if the four system roles already exist, assume seeding is done.
    # This avoids expensive permission table scans on every request.
    try:
        wanted = [
            BUILTIN_ROLE_KEYS.ORG_ADMIN,
            BUILTIN_ROLE_KEYS.COMPLIANCE_MANAGER,
            BUILTIN_ROLE_KEYS.AUDITOR,
            BUILTIN_ROLE_KEYS.MEMBER,
        ]
        existing_count = (
            RBACRole.query
            .filter(
                RBACRole.organization_id == int(org_id),
                RBACRole.name.in_(wanted),
            )
            .count()
        )
        if existing_count >= 4:
            return
    except Exception:
        # If anything goes wrong, fall back to full seeding logic.
        pass

    # Permissions (global)
    # Only load the codes we care about (avoid scanning the full table).
    wanted_codes = list(PERMISSIONS.keys())
    existing_perm_codes = {
        (row[0] or '').strip()
        for row in (
            RBACPermission.query
            .with_entities(RBACPermission.code)
            .filter(RBACPermission.code.in_(wanted_codes))
            .all()
        )
    }
    for code, desc in PERMISSIONS.items():
        if code in existing_perm_codes:
            continue
        db.session.add(RBACPermission(code=code, description=desc))

    db.session.flush()

    # Roles (org-scoped)
    existing_roles = {
        r.name: r
        for r in RBACRole.query.filter_by(organization_id=int(org_id)).all()
    }

    def get_or_create_role(name: str, description: str) -> RBACRole:
        role = existing_roles.get(name)
        if role:
            return role
        role = RBACRole(organization_id=int(org_id), name=name, description=description, is_system=True)
        db.session.add(role)
        db.session.flush()
        existing_roles[name] = role
        return role

    org_admin = get_or_create_role(BUILTIN_ROLE_KEYS.ORG_ADMIN, 'Full administrative access for this organization.')
    manager = get_or_create_role(BUILTIN_ROLE_KEYS.COMPLIANCE_MANAGER, 'Manage compliance workflows and documents.')
    auditor = get_or_create_role(BUILTIN_ROLE_KEYS.AUDITOR, 'Read-only access for audits and evidence review.')
    member = get_or_create_role(BUILTIN_ROLE_KEYS.MEMBER, 'Standard member access.')

    perms = (
        RBACPermission.query
        .filter(RBACPermission.code.in_(wanted_codes))
        .all()
    )
    perm_by_code = {p.code: p for p in perms if getattr(p, 'code', None)}

    def grant(role: RBACRole, codes: Iterable[str]) -> None:
        for code in codes:
            perm = perm_by_code.get(code)
            if not perm:
                continue
            if perm in role.permissions:
                continue
            role.permissions.append(perm)

    grant(member, DEFAULT_ROLE_GRANTS[BUILTIN_ROLE_KEYS.MEMBER])
    grant(auditor, DEFAULT_ROLE_GRANTS[BUILTIN_ROLE_KEYS.AUDITOR])
    grant(manager, DEFAULT_ROLE_GRANTS[BUILTIN_ROLE_KEYS.COMPLIANCE_MANAGER])
    grant(org_admin, DEFAULT_ROLE_GRANTS[BUILTIN_ROLE_KEYS.ORG_ADMIN])

    # Inheritance
    by_name = {r.name: r for r in [org_admin, manager, auditor, member]}
    for role_name, inherited_name in DEFAULT_ROLE_INHERITANCE:
        r = by_name.get(role_name)
        inh = by_name.get(inherited_name)
        if not r or not inh:
            continue
        if inh in r.inherits:
            continue
        r.inherits.append(inh)

    db.session.flush()


def choose_default_role_id_for_membership(m: OrganizationMembership) -> int | None:
    """Fallback mapping for legacy memberships that don't have role_id."""
    from app.models import RBACRole

    if not m or not m.organization_id:
        return None

    ensure_rbac_seeded_for_org(int(m.organization_id))

    legacy = (m.role or '').strip().lower()
    if legacy in {'admin', 'organisation administrator', 'organization administrator'}:
        name = BUILTIN_ROLE_KEYS.ORG_ADMIN
    else:
        name = BUILTIN_ROLE_KEYS.MEMBER

    role = (
        RBACRole.query
        .filter_by(organization_id=int(m.organization_id), name=name)
        .first()
    )
    return int(role.id) if role else None
