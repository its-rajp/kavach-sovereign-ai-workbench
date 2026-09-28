"""Role-Based Access Control (RBAC) & Clearance Subsystem for Kavach.

Implements SEC-R-01, SR-06, and FR-14:
- Tiered clearance levels: Operator/Guest (Rank 1) < Analyst (Rank 2) < Commander/Admin (Rank 3/4)
- Multi-Tenant Zero-Trust Document chunk clearance filtering
- Role privilege validation
"""

from enum import IntEnum
from typing import List, Dict, Any, Union, Optional


class Clearance(IntEnum):
    """Clearance tiers for information access."""
    PUBLIC = 1
    RESTRICTED = 2
    CONFIDENTIAL = 3
    SECRET = 4


class Role(IntEnum):
    """User roles available in Kavach."""
    GUEST = 1
    OPERATOR = 1
    ANALYST = 2
    ENGINEER = 3
    COMMANDER = 3
    ADMIN = 4

    @classmethod
    def from_str(cls, role_str: str) -> "Role":
        mapping = {
            "guest": cls.GUEST,
            "operator": cls.OPERATOR,
            "analyst": cls.ANALYST,
            "engineer": cls.ENGINEER,
            "commander": cls.COMMANDER,
            "admin": cls.ADMIN,
        }
        return mapping.get(role_str.strip().lower(), cls.OPERATOR)


# Role rank mapping (1=Operator/Guest, 2=Analyst, 3=Commander/Engineer, 4=Admin)
ROLE_RANKS = {
    Role.GUEST: 1,
    Role.OPERATOR: 1,
    Role.ANALYST: 2,
    Role.ENGINEER: 3,
    Role.COMMANDER: 3,
    Role.ADMIN: 4,
}

ROLE_STR_RANKS = {
    "operator": 1,
    "guest": 1,
    "analyst": 2,
    "engineer": 3,
    "commander": 3,
    "admin": 4,
}

# Role-to-Clearance entitlement mapping
ROLE_CLEARANCE_MAP = {
    Role.GUEST: Clearance.PUBLIC,
    Role.OPERATOR: Clearance.RESTRICTED,
    Role.ANALYST: Clearance.RESTRICTED,
    Role.ENGINEER: Clearance.CONFIDENTIAL,
    Role.COMMANDER: Clearance.SECRET,
    Role.ADMIN: Clearance.SECRET,
}


def get_role_rank(role: Union[Role, str, int]) -> int:
    """Return numeric rank (1..3/4) for a given role or string."""
    if isinstance(role, int) and not isinstance(role, Role):
        return role
    if isinstance(role, Role):
        return ROLE_RANKS.get(role, 1)
    if isinstance(role, str):
        r_clean = role.strip().lower()
        if r_clean in ROLE_STR_RANKS:
            return ROLE_STR_RANKS[r_clean]
        role_enum = Role.from_str(r_clean)
        return ROLE_RANKS.get(role_enum, 1)
    return 1


def check_clearance(role: Union[Role, str], required_clearance: Union[Clearance, str, int]) -> bool:
    """Verify if a user role possesses clearance for the target information tier."""
    if isinstance(role, str):
        role_enum = Role.from_str(role)
    else:
        role_enum = role

    if isinstance(required_clearance, str):
        clearance_map = {
            "public": Clearance.PUBLIC,
            "restricted": Clearance.RESTRICTED,
            "confidential": Clearance.CONFIDENTIAL,
            "secret": Clearance.SECRET,
        }
        req_enum = clearance_map.get(required_clearance.lower(), Clearance.SECRET)
    elif isinstance(required_clearance, int):
        req_enum = Clearance(required_clearance) if required_clearance in (1, 2, 3, 4) else Clearance.SECRET
    else:
        req_enum = required_clearance

    user_clearance = ROLE_CLEARANCE_MAP.get(role_enum, Clearance.PUBLIC)
    return user_clearance >= req_enum


def check_chunk_clearance(chunk_meta: Dict[str, Any], user_role: Union[Role, str]) -> bool:
    """Check if a chunk's clearance metadata allows access to user_role."""
    user_rank = get_role_rank(user_role)

    # If chunk has clearance_rank metadata (1, 2, 3)
    if "clearance_rank" in chunk_meta:
        chk_rank = int(chunk_meta.get("clearance_rank", 1))
        return user_rank >= chk_rank

    # If chunk has uploaded_by_role
    if "uploaded_by_role" in chunk_meta:
        uploader_role = chunk_meta["uploaded_by_role"]
        uploader_rank = get_role_rank(uploader_role)
        return user_rank >= uploader_rank

    # Fallback to clearance label ("public", "restricted", "confidential", "secret")
    chunk_clearance = chunk_meta.get("clearance", "restricted")
    return check_clearance(user_role, chunk_clearance)


def filter_chunks_by_role(chunks: List[Dict[str, Any]], role: Union[Role, str]) -> List[Dict[str, Any]]:
    """Filter candidate retrieval chunks by role clearance (SEC-R-01)."""
    allowed_chunks = []
    for chunk in chunks:
        metadata = chunk.get("metadata", {})
        if check_chunk_clearance(metadata, role):
            allowed_chunks.append(chunk)
    return allowed_chunks

