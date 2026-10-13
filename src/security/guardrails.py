"""Guardrails bridge module for src.security.guardrails namespace.

Re-exports core Guardrails Engine and actions from src.guardrails.
"""

from ..guardrails.engine import GuardrailsEngine, GuardrailsResponse, get_guardrails_engine
from ..guardrails.actions import GuardrailActions
from .alert_dispatcher import dispatch_security_alert

__all__ = [
    "GuardrailsEngine",
    "GuardrailsResponse",
    "GuardrailActions",
    "get_guardrails_engine",
    "dispatch_security_alert",
]
