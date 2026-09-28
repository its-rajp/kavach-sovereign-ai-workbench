"""Unit tests for Kavach RAG Pipeline & Role Filtering."""

import pytest
from src.security.rbac import Role, check_clearance, filter_chunks_by_role
from src.security.redaction import redact_for_role


def test_clearance_hierarchy():
    # Admin has access to secret, confidential, restricted, public
    assert check_clearance(Role.ADMIN, "secret") is True
    assert check_clearance(Role.ADMIN, "confidential") is True

    # Analyst has restricted and public, but not secret
    assert check_clearance(Role.ANALYST, "restricted") is True
    assert check_clearance(Role.ANALYST, "secret") is False

    # Guest only has public
    assert check_clearance(Role.GUEST, "public") is True
    assert check_clearance(Role.GUEST, "confidential") is False


def test_filter_chunks_by_role():
    chunks = [
        {"chunk_id": "c1", "text": "Public overview", "metadata": {"clearance": "public"}},
        {"chunk_id": "c2", "text": "Confidential financials", "metadata": {"clearance": "confidential"}},
        {"chunk_id": "c3", "text": "Top secret override code", "metadata": {"clearance": "secret"}},
    ]

    analyst_chunks = filter_chunks_by_role(chunks, role=Role.ANALYST)
    assert len(analyst_chunks) == 1
    assert analyst_chunks[0]["chunk_id"] == "c1"

    admin_chunks = filter_chunks_by_role(chunks, role=Role.ADMIN)
    assert len(admin_chunks) == 3


def test_redaction_for_role():
    text = "The quarterly outlay is INR 4,820 crore and emergency key is SHUTDOWN_OVERRIDE_KEY='ESD-98421'."

    # Admin: no redaction
    sanitized_admin, redacted_admin, _ = redact_for_role(text, role=Role.ADMIN)
    assert redacted_admin is False
    assert "INR 4,820 crore" in sanitized_admin

    # Analyst: financial & root keys redacted
    sanitized_analyst, redacted_analyst, _ = redact_for_role(text, role=Role.ANALYST)
    assert redacted_analyst is True
    assert "[REDACTED: FINANCIAL_CURRENCY]" in sanitized_analyst
    assert "[REDACTED: HIGH_PRESSURE_OVERRIDE]" in sanitized_analyst
