"""Custom Security Actions for Kavach Guardrails.

Implements input screening, semantic similarity checks, and output validation.
"""

from typing import Tuple, Optional, List
import math
from .patterns import (
    INJECTION_REGEX,
    JAILBREAK_REGEX,
    DISCLOSURE_REGEX,
    EXFILTRATION_REGEX,
    OBFUSCATION_REGEX,
    ATTACK_PHRASE_BANK,
)
from ..rag.embeddings import get_embeddings
from ..security.redaction import redact_for_role


def _cosine_sim(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 <= 0 or n2 <= 0:
        return 0.0
    return dot / (n1 * n2)


class GuardrailActions:
    """Evaluates security predicates across input and output layers."""

    def __init__(self):
        self.embeddings = get_embeddings()
        self._cached_phrase_embeddings = {}
        self._init_phrase_embeddings()

    def _init_phrase_embeddings(self):
        """Pre-compute embeddings for attack phrase bank for fast cosine checks."""
        for rule_id, phrases in ATTACK_PHRASE_BANK.items():
            self._cached_phrase_embeddings[rule_id] = [
                self.embeddings.embed_query(phrase) for phrase in phrases
            ]

    def check_injection(self, text: str) -> Tuple[bool, Optional[str], Optional[str], str]:
        """Check for prompt injection and jailbreaks (SEC-I-01, SEC-I-02, SEC-I-06)."""
        # 1. Regex checks
        for p in INJECTION_REGEX:
            if p.search(text):
                return True, "SEC-I-01", "high", f"Regex match on injection pattern: '{p.pattern}'"

        for p in JAILBREAK_REGEX:
            if p.search(text):
                return True, "SEC-I-02", "high", f"Regex match on jailbreak pattern: '{p.pattern}'"

        for p in OBFUSCATION_REGEX:
            if p.search(text):
                return True, "SEC-I-06", "high", f"Obfuscation wrapper detected"

        # 2. Semantic similarity check against phrase bank
        query_vec = self.embeddings.embed_query(text)
        for rule_id in ["SEC-I-01", "SEC-I-02"]:
            for bank_vec in self._cached_phrase_embeddings.get(rule_id, []):
                sim = _cosine_sim(query_vec, bank_vec)
                if sim >= 0.82:  # High confidence semantic paraphrase match
                    return True, rule_id, "high", f"Semantic paraphrase match (similarity={sim:.2f})"

        return False, None, None, ""

    def check_exfiltration(self, text: str) -> Tuple[bool, Optional[str], Optional[str], str]:
        """Check for bulk data exfiltration attempts (SEC-I-04)."""
        for p in EXFILTRATION_REGEX:
            if p.search(text):
                return True, "SEC-I-04", "critical", f"Regex match on exfiltration pattern: '{p.pattern}'"

        query_vec = self.embeddings.embed_query(text)
        for bank_vec in self._cached_phrase_embeddings.get("SEC-I-04", []):
            sim = _cosine_sim(query_vec, bank_vec)
            if sim >= 0.82:
                return True, "SEC-I-04", "critical", f"Semantic exfiltration match (similarity={sim:.2f})"

        return False, None, None, ""

    def check_disclosure(self, text: str) -> Tuple[bool, Optional[str], Optional[str], str]:
        """Check for system prompt disclosure requests (SEC-I-03)."""
        for p in DISCLOSURE_REGEX:
            if p.search(text):
                return True, "SEC-I-03", "high", f"Regex match on disclosure pattern: '{p.pattern}'"

        query_vec = self.embeddings.embed_query(text)
        for bank_vec in self._cached_phrase_embeddings.get("SEC-I-03", []):
            sim = _cosine_sim(query_vec, bank_vec)
            if sim >= 0.82:
                return True, "SEC-I-03", "high", f"Semantic disclosure match (similarity={sim:.2f})"

        return False, None, None, ""

    def check_scope(self, text: str) -> Tuple[bool, Optional[str], Optional[str], str]:
        """Check if request is wildly outside authorized industrial domain (SEC-I-05)."""
        lower = text.lower()
        out_of_scope_cues = ["write a poem", "who won the", "recipe for", "how do i make a bomb", "play a game"]
        for cue in out_of_scope_cues:
            if cue in lower:
                return True, "SEC-I-05", "low", f"Out of operational domain: '{cue}'"
        return False, None, None, ""

    def check_grounding(self, answer: str, context: str) -> Tuple[bool, float]:
        """Verify model output claims correspond to retrieved context (SEC-O-05)."""
        if not context.strip():
            return False, 0.0

        ans_words = set(w.lower() for w in answer.split() if len(w) > 4)
        ctx_words = set(w.lower() for w in context.split() if len(w) > 4)

        if not ans_words:
            return True, 1.0

        overlap = len(ans_words.intersection(ctx_words))
        ratio = overlap / len(ans_words)
        return ratio >= 0.20, ratio

    def redact(self, text: str, role: str) -> Tuple[str, bool, List[str]]:
        """Apply role-based redaction to output text."""
        return redact_for_role(text, role)
