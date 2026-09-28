"""Data Redaction Subsystem for Kavach.

Implements SEC-O-01, SEC-O-02, and FR-16:
- Role-based withholding of financial, operational, and PII figures
- Replaces restricted figures with standard audit tags
"""

import re
from typing import Tuple, List, Union
from .rbac import Role


# Regular expressions for sensitive industrial and financial patterns
PATTERNS = {
    "financial_currency": re.compile(r"(?:₹|\bINR\b|\$)\s*[\d,]+(?:\.\d+)?\s*(?:crore|lakh|million|billion|k)?", re.IGNORECASE),
    "root_password": re.compile(r"\b(?:password|passwd|secret_key|api_key)\s*[:=]\s*['\"]?([A-Za-z0-9@#$%^&+=_-]{6,})['\"]?", re.IGNORECASE),
    "phone_number": re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{9}\b"),
    "catalyst_secret_code": re.compile(r"\b(?:CAT-|FORMULA-|CHEM-)[A-Z0-9]{4,}\b"),
    "high_pressure_override": re.compile(r"\b(?:SHUTDOWN_OVERRIDE_KEY|MASTER_BYPASS_PIN)\s*[:=]\s*['\"]?([A-Za-z0-9_-]{4,})['\"]?", re.IGNORECASE),
}


def redact_for_role(text: str, role: Union[Role, str]) -> Tuple[str, bool, List[str]]:
    """Redact sensitive fields from model output based on user role clearance.

    Returns:
        (sanitized_text, was_redacted, list_of_redacted_categories)
    """
    if isinstance(role, str):
        role_enum = Role.from_str(role)
    else:
        role_enum = role

    # Admin sees everything; Engineer sees operational details (except root passwords/bypass keys)
    if role_enum == Role.ADMIN:
        return text, False, []

    redacted_text = text
    redacted_categories: List[str] = []
    was_redacted = False

    # Redact root credentials & override keys for non-Admin
    for cat in ["root_password", "high_pressure_override"]:
        pattern = PATTERNS[cat]
        if pattern.search(redacted_text):
            redacted_text = pattern.sub(f"[REDACTED: {cat.upper()}]", redacted_text)
            redacted_categories.append(cat)
            was_redacted = True

    # For Guest and Analyst: redact confidential catalyst formulas and financial figures
    if role_enum in (Role.GUEST, Role.ANALYST):
        for cat in ["catalyst_secret_code", "financial_currency"]:
            pattern = PATTERNS[cat]
            if pattern.search(redacted_text):
                redacted_text = pattern.sub(f"[REDACTED: {cat.upper()}]", redacted_text)
                redacted_categories.append(cat)
                was_redacted = True

    # For Guest: redact phone numbers and contact PII
    if role_enum == Role.GUEST:
        pattern = PATTERNS["phone_number"]
        if pattern.search(redacted_text):
            redacted_text = pattern.sub("[REDACTED: PII CONTACT]", redacted_text)
            redacted_categories.append("phone_number")
            was_redacted = True

    return redacted_text, was_redacted, list(set(redacted_categories))
