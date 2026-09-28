"""Guardrails Security Engine for Kavach.

Coordinates NeMo Guardrails policy flows, custom actions, and fail-closed RAG generation.
Enforces:
- Input screening (injection, jailbreak, exfiltration, disclosure, scope)
- Fail-Closed invariant (SEC-X-01: any exception denies turn with critical audit log)
- Output screening & redaction (SEC-O-01 to SEC-O-05)
- Immutable audit logging on every security decision
"""

from typing import Optional, List, Dict, Any, Literal, Union
from pydantic import BaseModel, Field
from .actions import GuardrailActions
from ..rag.chain import RAGChain, Answer, Citation, get_rag_chain
from ..security.audit import AuditRecord, get_audit_logger
from ..security.rbac import Role
from ..config import get_settings


class GuardrailsResponse(BaseModel):
    """Final secured response delivered to the presentation layer."""
    text: str
    verdict: Literal["allowed", "blocked", "redacted", "denied_closed"] = "allowed"
    citations: List[Citation] = Field(default_factory=list)
    blocked_rule: Optional[str] = None
    category: Optional[str] = None
    severity: Optional[str] = None
    alert_title: Optional[str] = None
    alert_message: Optional[str] = None


REFUSAL_MESSAGES = {
    "SEC-I-01": (
        "🚨 BLOCKED: PROMPT INJECTION DETECTED",
        "Security Alert: That looks like an attempt to override or manipulate instructions (Rule SEC-I-01). This incident has been logged to the immutable audit trail."
    ),
    "SEC-I-02": (
        "🚨 BLOCKED: JAILBREAK / PERSONA SPOOF DETECTED",
        "Security Alert: Persona manipulation or safety bypass attempt blocked (Rule SEC-I-02). Operating under sovereign constraints."
    ),
    "SEC-I-03": (
        "🚨 BLOCKED: SYSTEM PROMPT DISCLOSURE DETECTED",
        "Security Alert: Requests to reveal internal system instructions, configuration, or security rules are strictly prohibited (Rule SEC-I-03). Incident logged."
    ),
    "SEC-I-04": (
        "🚨 BLOCKED: BULK DATA EXFILTRATION DETECTED",
        "Security Alert: Bulk document dumps or raw data exports are prohibited (Rule SEC-I-04). I can summarize or answer specific questions instead. Request logged."
    ),
    "SEC-I-05": (
        "⚠️ REQUEST OUT OF OPERATIONAL SCOPE",
        "Notice: This inquiry falls outside the operational mandate of Kavach (Rule SEC-I-05). I am restricted to authorized MRPL engineering and safety documentation."
    ),
    "SEC-I-06": (
        "🚨 BLOCKED: OBFUSCATION WRAPPER DETECTED",
        "Security Alert: Obfuscated or encoded instruction bypass detected and blocked (Rule SEC-I-06). Incident logged."
    ),
}


class GuardrailsEngine:
    """The central security controller wrapping the entire RAG pipeline."""

    def __init__(self, actions: Optional[GuardrailActions] = None, rag_chain: Optional[RAGChain] = None):
        self.actions = actions or GuardrailActions()
        self.rag_chain = rag_chain or get_rag_chain()
        self.audit_logger = get_audit_logger()
        self.settings = get_settings()

    def generate(
        self,
        user_msg: str,
        role: Union[Role, str] = Role.ANALYST,
        session_id: str = "default_session",
        conversation_history: Optional[str] = None,
    ) -> GuardrailsResponse:
        """Process user query through bidirectional guardrails with fail-closed guarantee."""
        role_str = role.name.lower() if isinstance(role, Role) else str(role).lower()

        try:
            # ----------------------------------------------------
            # 1. INPUT RAILS: Screen user query (SR-01 to SR-05)
            # ----------------------------------------------------
            # Check prompt injection & jailbreak
            is_inj, rule, sev, note = self.actions.check_injection(user_msg)
            if is_inj:
                return self._handle_block(
                    rule_id=rule or "SEC-I-01",
                    category="injection",
                    severity=sev or "high",
                    user_msg=user_msg,
                    session_id=session_id,
                    role=role_str,
                    note=note,
                )

            # Check bulk exfiltration
            is_exf, rule, sev, note = self.actions.check_exfiltration(user_msg)
            if is_exf:
                return self._handle_block(
                    rule_id=rule or "SEC-I-04",
                    category="exfiltration",
                    severity=sev or "critical",
                    user_msg=user_msg,
                    session_id=session_id,
                    role=role_str,
                    note=note,
                )

            # Check system prompt disclosure
            is_disc, rule, sev, note = self.actions.check_disclosure(user_msg)
            if is_disc:
                return self._handle_block(
                    rule_id=rule or "SEC-I-03",
                    category="disclosure",
                    severity=sev or "high",
                    user_msg=user_msg,
                    session_id=session_id,
                    role=role_str,
                    note=note,
                )

            # Check out of scope
            is_scope, rule, sev, note = self.actions.check_scope(user_msg)
            if is_scope:
                return self._handle_block(
                    rule_id=rule or "SEC-I-05",
                    category="scope",
                    severity=sev or "low",
                    user_msg=user_msg,
                    session_id=session_id,
                    role=role_str,
                    note=note,
                )

            # ----------------------------------------------------
            # 2. GENERATION: Execute RAG Chain
            # ----------------------------------------------------
            answer: Answer = self.rag_chain.generate(
                question=user_msg,
                role=role,
                conversation_history=conversation_history,
            )

            # ----------------------------------------------------
            # 3. OUTPUT RAILS: Screen model draft (SEC-O-01 to SEC-O-05)
            # ----------------------------------------------------
            if answer.verdict == "refused":
                rule_id = answer.triggered_rules[0] if answer.triggered_rules else "SEC-R-01"
                self.audit_logger.log_event(AuditRecord(
                    session_id=session_id,
                    role=role_str,
                    stage="retrieval",
                    verdict="blocked",
                    rule_id=rule_id,
                    category="clearance_intercept",
                    severity="high",
                    input_excerpt=self.audit_logger.sanitize_excerpt(user_msg),
                    ai_response=answer.text,
                    note="Access blocked: requested information resides in higher clearance tier.",
                ))
                return GuardrailsResponse(
                    text=answer.text,
                    verdict="blocked",
                    citations=[],
                    blocked_rule=rule_id,
                    category="clearance_intercept",
                    severity="high",
                    alert_title="🛡️ SECURITY INTERCEPT: HIGHER CLEARANCE REQUIRED",
                    alert_message="Access denied under sovereign air-gap policy: Information classification exceeds caller rank.",
                )

            output_text = answer.text


            # Check if model echoed system prompt rules (SEC-O-03)
            if "RULES (non-negotiable" in output_text or "You are Kavach, a secure sovereign" in output_text:
                return self._handle_block(
                    rule_id="SEC-O-03",
                    category="disclosure",
                    severity="high",
                    user_msg=user_msg,
                    session_id=session_id,
                    role=role_str,
                    note="Model output leaked internal system prompt rules",
                    stage="output",
                )

            # Apply role-based redaction (SEC-O-01, SEC-O-02)
            redacted_text, was_redacted, redacted_cats = self.actions.redact(output_text, role=role_str)
            if was_redacted:
                self.audit_logger.log_event(AuditRecord(
                    session_id=session_id,
                    role=role_str,
                    stage="output",
                    verdict="redacted",
                    rule_id="SEC-O-01",
                    category="pii_or_financial",
                    severity="medium",
                    input_excerpt=self.audit_logger.sanitize_excerpt(user_msg),
                    note=f"Redacted categories: {', '.join(redacted_cats)}",
                ))
                return GuardrailsResponse(
                    text=redacted_text,
                    verdict="redacted",
                    citations=answer.citations,
                    blocked_rule="SEC-O-01",
                    category="redaction",
                    severity="medium",
                    alert_title="ℹ️ REDACTED: SENSITIVE VALUES MASKED",
                    alert_message=f"Values withheld according to clearance policy for role '{role_str.upper()}'.",
                )

            # Allowed turn — log for Total Telemetry
            self.audit_logger.log_event(AuditRecord(
                session_id=session_id,
                role=role_str,
                stage="output",
                verdict="allowed",
                rule_id="ALLOW-RAG",
                category="benign",
                severity="low",
                input_excerpt=self.audit_logger.sanitize_excerpt(user_msg),
                ai_response=self.audit_logger.sanitize_excerpt(output_text, max_chars=200),
                note="Benign query passed all guardrails; grounded RAG response delivered.",
            ))

            return GuardrailsResponse(
                text=output_text,
                verdict="allowed",
                citations=answer.citations,
            )

        except Exception as exc:
            # ----------------------------------------------------
            # 4. FAIL-CLOSED INVARIANT (SEC-X-01, ENG-01)
            # ----------------------------------------------------
            # Log critical security incident and deny access
            self.audit_logger.log_event(AuditRecord(
                session_id=session_id,
                role=role_str,
                stage="system",
                verdict="denied_closed",
                rule_id="SEC-X-01",
                category="system_error",
                severity="critical",
                input_excerpt=self.audit_logger.sanitize_excerpt(user_msg),
                note=f"Fail-closed triggered due to engine exception: {str(exc)}",
            ))

            return GuardrailsResponse(
                text="🚨 Access Denied: Security validation encountered an error and failed-closed (Rule SEC-X-01). Request cannot be processed unguarded.",
                verdict="denied_closed",
                citations=[],
                blocked_rule="SEC-X-01",
                category="system_error",
                severity="critical",
                alert_title="🚨 CRITICAL: FAIL-CLOSED DENIAL",
                alert_message="System encountered an exception during security verification and failed-closed to prevent an unguarded answer.",
            )

    def _handle_block(
        self,
        rule_id: str,
        category: str,
        severity: str,
        user_msg: str,
        session_id: str,
        role: str,
        note: str,
        stage: Literal["input", "output"] = "input",
    ) -> GuardrailsResponse:
        """Record audit event and construct safe refusal response."""
        self.audit_logger.log_event(AuditRecord(
            session_id=session_id,
            role=role,
            stage=stage,
            verdict="blocked",
            rule_id=rule_id,
            category=category,
            severity=severity,  # type: ignore
            input_excerpt=self.audit_logger.sanitize_excerpt(user_msg),
            note=note,
        ))

        title, message = REFUSAL_MESSAGES.get(
            rule_id,
            ("🚨 BLOCKED BY GUARDRAILS", f"Security Alert: Action blocked by policy rule {rule_id}.")
        )

        return GuardrailsResponse(
            text=message,
            verdict="blocked",
            citations=[],
            blocked_rule=rule_id,
            category=category,
            severity=severity,
            alert_title=title,
            alert_message=message,
        )


_guardrails_engine_instance: Optional[GuardrailsEngine] = None


def get_guardrails_engine() -> GuardrailsEngine:
    global _guardrails_engine_instance
    if _guardrails_engine_instance is None:
        _guardrails_engine_instance = GuardrailsEngine()
    return _guardrails_engine_instance
