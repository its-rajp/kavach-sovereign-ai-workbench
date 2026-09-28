"""Unit tests for Kavach Session-Scoped Conversational Memory."""

import pytest
from src.memory.session import MemoryManager, SessionMemory


def test_session_isolation():
    manager = MemoryManager()
    session_a = manager.get_session("session_1", "analyst")
    session_b = manager.get_session("session_2", "analyst")

    session_a.append("Hello from user 1", "Response 1")
    assert len(session_a.buffer) == 1
    assert len(session_b.buffer) == 0


def test_memory_sliding_window_and_summary():
    mem = SessionMemory(session_id="test", role="analyst", maxlen=3)
    for i in range(5):
        mem.append(f"Question {i}", f"Answer {i}")

    # Buffer capped at maxlen=3
    assert len(mem.buffer) == 3
    # Evicted turns condensed into summary
    assert "Question 0" in mem.summary or "Question 1" in mem.summary


def test_role_switch_wiping():
    manager = MemoryManager()
    session = manager.get_session("sess_alpha", "analyst")
    session.append("Sensitive query", "Confidential answer")
    assert len(session.buffer) == 1

    # Switch role to guest -> old session memory flushed
    guest_session = manager.switch_role("sess_alpha", "analyst", "guest")
    assert len(guest_session.buffer) == 0
    assert guest_session.summary == ""
