"""
BorderShield Sovereign Role-Based Access Control (RBAC) & Authentication Module
Implements sovereign border checkpoint roles, permission checks, and session contexts.
Compliant with Section 20 & 21 of Security.md.
"""

import os
import uuid
import logging
from enum import Enum
from typing import List, Optional, Set
from dataclasses import dataclass
from fastapi import Header, HTTPException, Depends

from core.config import get_settings

logger = logging.getLogger("bordershield.auth")


class SovereignRole(str, Enum):
    """
    Sovereign border control operational roles:
    - SCREENING_OFFICER: Primary lane officer executing front-line document & biometric screening.
    - SUPERVISOR: Senior checkpoint officer authorized to review flagged cases and execute overrides.
    - INVESTIGATOR: Intelligence / forensics officer authorized to inspect raw evidence and unmask PII.
    - AUDITOR: Oversight authority verifying cryptographic audit chains and immutable ledgers.
    - SYSTEM_ADMIN: Infrastructure and model deployment maintainer (cannot alter screening decisions).
    """
    SCREENING_OFFICER = "SCREENING_OFFICER"
    SUPERVISOR = "SUPERVISOR"
    INVESTIGATOR = "INVESTIGATOR"
    AUDITOR = "AUDITOR"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


# Role-permission mapping
ROLE_PERMISSIONS: dict[SovereignRole, Set[str]] = {
    SovereignRole.SCREENING_OFFICER: {
        "screening:execute",
        "screening:view_basic",
        "biometrics:capture",
        "ledger:view"
    },
    SovereignRole.SUPERVISOR: {
        "screening:execute",
        "screening:view_basic",
        "screening:view_detailed",
        "decision:override",
        "biometrics:capture",
        "pii:unmask",
        "ledger:view",
        "ledger:verify"
    },
    SovereignRole.INVESTIGATOR: {
        "screening:execute",
        "screening:view_basic",
        "screening:view_detailed",
        "decision:override",
        "forensics:deep_inspect",
        "pii:unmask",
        "ledger:view",
        "ledger:verify"
    },
    SovereignRole.AUDITOR: {
        "ledger:view",
        "ledger:verify",
        "screening:audit",
        "compliance:report"
    },
    SovereignRole.SYSTEM_ADMIN: {
        "system:configure",
        "models:manage",
        "ledger:view",
        "infrastructure:status"
    }
}


@dataclass
class OfficerSession:
    """Active officer session context at border screening checkpoint."""
    officer_id: str
    role: SovereignRole
    station_id: str
    session_id: str
    permissions: Set[str]

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def can_override_decision(self) -> bool:
        return "decision:override" in self.permissions

    def can_unmask_pii(self) -> bool:
        return "pii:unmask" in self.permissions

    def can_verify_ledger(self) -> bool:
        return "ledger:verify" in self.permissions

    def to_dict(self) -> dict:
        return {
            "officer_id": self.officer_id,
            "role": self.role.value,
            "station_id": self.station_id,
            "session_id": self.session_id,
            "permissions": list(self.permissions)
        }


def get_current_officer(
    x_officer_id: Optional[str] = Header(None, alias="X-Officer-Id"),
    x_officer_role: Optional[str] = Header(None, alias="X-Officer-Role"),
    x_station_id: Optional[str] = Header(None, alias="X-Station-Id")
) -> OfficerSession:
    """
    FastAPI dependency resolving active checkpoint officer identity.
    Provides safe sovereign defaults for local demo mode without breaking existing clients.
    """
    settings = get_settings()

    # Handle direct function calls outside FastAPI dependency injection
    from fastapi.params import Header as HeaderParam
    if isinstance(x_officer_role, HeaderParam) or x_officer_role is None:
        raw_role = settings.DEFAULT_OFFICER_ROLE
    else:
        raw_role = str(x_officer_role).strip().upper()

    try:
        role = SovereignRole(raw_role)
    except ValueError:
        logger.warning(f"Unrecognized role '{raw_role}', falling back to SCREENING_OFFICER")
        role = SovereignRole.SCREENING_OFFICER

    # Resolve officer ID
    if isinstance(x_officer_id, HeaderParam) or x_officer_id is None:
        officer_id = settings.DEFAULT_OFFICER_ID
    else:
        officer_id = str(x_officer_id).strip()

    # Resolve station ID
    if isinstance(x_station_id, HeaderParam) or x_station_id is None:
        station_id = "ICP-RAXAUL-01"
    else:
        station_id = str(x_station_id).strip()

    session_id = f"SESS-{uuid.uuid4().hex[:8].upper()}"
    permissions = ROLE_PERMISSIONS.get(role, set())

    return OfficerSession(
        officer_id=officer_id,
        role=role,
        station_id=station_id,
        session_id=session_id,
        permissions=permissions
    )


def require_permission(permission: str):
    """Dependency factory enforcing specific sovereign operational permission."""
    def _dependency(officer: OfficerSession = Depends(get_current_officer)):
        if not officer.has_permission(permission):
            logger.warning(
                f"ACCESS DENIED: Officer '{officer.officer_id}' ({officer.role.value}) "
                f"attempted action requiring '{permission}'"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: Role '{officer.role.value}' lacks sovereign permission '{permission}'."
            )
        return officer
    return _dependency


def require_role(allowed_roles: List[SovereignRole]):
    """Dependency factory restricting endpoint access to specific roles."""
    def _dependency(officer: OfficerSession = Depends(get_current_officer)):
        if officer.role not in allowed_roles:
            role_names = [r.value for r in allowed_roles]
            logger.warning(
                f"ACCESS DENIED: Officer '{officer.officer_id}' ({officer.role.value}) "
                f"attempted action restricted to {role_names}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: Access restricted to authorized roles: {', '.join(role_names)}."
            )
        return officer
    return _dependency
