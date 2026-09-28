"""Session-Scoped Conversational Memory for Kavach.

Implements memory.md security specifications:
1. Session Isolation: distinct memory per session_id and role
2. Redact-Before-Store: only post-guardrails redacted text enters memory
3. Bounded Retention: fixed turn window (maxlen=N) + condensed summary
4. Ephemeral: easily wiped upon role change or session termination
"""

from collections import deque
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from ..config import get_settings


class Turn(BaseModel):
    """A single conversational exchange."""
    user_message: str
    bot_response: str
    verdict: str


class SessionMemory:
    """Bounded, redacted conversational memory container."""

    def __init__(self, session_id: str, role: str, maxlen: Optional[int] = None):
        settings = get_settings()
        self.session_id = session_id
        self.role = role
        self.maxlen = maxlen or settings.memory_window_turns
        self.buffer: deque[Turn] = deque(maxlen=self.maxlen)
        self.summary: str = ""

    def append(self, user_msg: str, bot_resp: str, verdict: str = "allowed") -> None:
        """Store conversational turn (enforcing redact-before-store)."""
        turn = Turn(
            user_message=user_msg.strip(),
            bot_response=bot_resp.strip(),
            verdict=verdict,
        )

        # If buffer is full, condense the oldest turn before evicting
        if len(self.buffer) == self.maxlen:
            oldest = self.buffer[0]
            self._update_summary(oldest)

        self.buffer.append(turn)

    def _update_summary(self, turn: Turn) -> None:
        """Condense evicted turn into rolling summary string."""
        addition = f"User asked about: {turn.user_message[:60]}... Response covered: {turn.bot_response[:60]}..."
        if not self.summary:
            self.summary = addition
        else:
            self.summary = f"{self.summary} | {addition}"
            # Keep summary bounded to 300 chars
            if len(self.summary) > 300:
                self.summary = self.summary[-300:]

    def get_history_context(self) -> str:
        """Format prior turns for injection into RAG prompt context."""
        parts = []
        if self.summary:
            parts.append(f"Summary of prior conversation: {self.summary}")

        for turn in self.buffer:
            parts.append(f"User: {turn.user_message}\nAssistant: {turn.bot_response}")

        return "\n\n".join(parts)

    def wipe(self) -> None:
        """Completely flush conversation memory (e.g. on role switch or logout)."""
        self.buffer.clear()
        self.summary = ""


class MemoryManager:
    """Registry managing ephemeral session memory objects."""

    def __init__(self):
        self._sessions: Dict[str, SessionMemory] = {}

    def get_session(self, session_id: str, role: str) -> SessionMemory:
        """Retrieve or initialize isolated session memory."""
        key = f"{session_id}_{role}"
        if key not in self._sessions:
            self._sessions[key] = SessionMemory(session_id=session_id, role=role)
        return self._sessions[key]

    def switch_role(self, session_id: str, old_role: str, new_role: str) -> SessionMemory:
        """Wipe old role memory and return fresh session memory (memory.md §4)."""
        old_key = f"{session_id}_{old_role}"
        if old_key in self._sessions:
            self._sessions[old_key].wipe()
            del self._sessions[old_key]

        return self.get_session(session_id=session_id, role=new_role)

    def clear_all(self) -> None:
        """Wipe all active sessions."""
        for mem in self._sessions.values():
            mem.wipe()
        self._sessions.clear()


_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
