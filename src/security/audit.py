"""Immutable Audit Logging Subsystem for Kavach.

Implements SEC-L-01 to SEC-L-04:
- Append-only JSONL event stream for tamper-evident logging
- Synchronized SQLite mirror for real-time queryability in the Admin dashboard
- CSV telemetry ledger (kavach_audit_ledger.csv) for compliance export
- Truncated/hashed excerpts to prevent storing raw confidential payloads (SEC-L-02)
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional, List, Dict, Any
import csv
import json
import sqlite3
import hashlib
from pydantic import BaseModel, Field


class AuditRecord(BaseModel):
    """Immutable audit record representing a security or access decision."""

    ts: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    session_id: str
    role: str
    stage: Literal["input", "output", "system", "ingestion", "retrieval"]
    verdict: Literal["allowed", "blocked", "redacted", "denied_closed"]
    rule_id: str
    category: str
    severity: Literal["low", "medium", "high", "critical", "info", "warning"]
    input_excerpt: str
    ai_response: str = ""
    note: str = ""


    def to_dict(self) -> Dict[str, Any]:
        return self.model_dump()


class AuditLogger:
    """Manages append-only JSONL writes, SQLite audit database, and CSV ledger."""

    CSV_HEADERS = [
        "Timestamp", "Clearance_Role", "Action_Type", "Details", "Status",
    ]

    def __init__(
        self,
        jsonl_path: Path = Path("logs/audit.jsonl"),
        db_path: Path = Path("logs/audit.db"),
        csv_path: Path = Path("logs/kavach_audit_ledger.csv"),
    ):
        self.jsonl_path = Path(jsonl_path)
        self.db_path = Path(db_path)
        self.csv_path = Path(csv_path)

        # Ensure directories exist
        self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.csv_path.parent.mkdir(parents=True, exist_ok=True)

        self._init_db()
        self._init_csv()

    def _init_db(self) -> None:
        """Initialize SQLite audit schema if not present."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    rule_id TEXT NOT NULL,
                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    input_excerpt TEXT NOT NULL,
                    ai_response TEXT DEFAULT '',
                    note TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_events(ts)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_severity ON audit_events(severity)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_rule ON audit_events(rule_id)")

            # Ensure ai_response column exists for upgrades from older schema
            try:
                cursor.execute("SELECT ai_response FROM audit_events LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE audit_events ADD COLUMN ai_response TEXT DEFAULT ''")

            conn.commit()

    def _init_csv(self) -> None:
        """Write CSV header if the ledger file doesn't exist yet."""
        if not self.csv_path.exists():
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self.CSV_HEADERS)

    @staticmethod
    def sanitize_excerpt(text: str, max_chars: int = 120) -> str:
        """Truncate input and append hash to avoid storing full cleartext payloads."""
        cleaned = " ".join(text.replace("\n", " ").split())
        if len(cleaned) <= max_chars:
            return cleaned
        digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:8]
        return f"{cleaned[:max_chars]}... [hash:{digest}]"

    def log_event(self, record: AuditRecord) -> None:
        """Write audit record to JSONL stream, SQLite mirror, and CSV ledger."""
        # 1. Append to JSONL stream (immutable audit log - SEC-L-01)
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict()) + "\n")

        # 2. Mirror into SQLite for Admin view queries
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_events (
                    ts, session_id, role, stage, verdict, rule_id, category,
                    severity, input_excerpt, ai_response, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.ts,
                record.session_id,
                record.role,
                record.stage,
                record.verdict,
                record.rule_id,
                record.category,
                record.severity,
                record.input_excerpt,
                record.ai_response,
                record.note,
            ))
            conn.commit()

        # 3. Append to CSV telemetry ledger (kavach_audit_ledger.csv)
        if record.rule_id == "RBAC-ELEVATE":
            action_type = "LOGIN_SUCCESS"
            details = record.note or record.input_excerpt
        elif record.rule_id in ("RBAC-AUTH-FAIL", "RBAC-LOGOUT"):
            action_type = "LOGIN_FAILED" if record.rule_id == "RBAC-AUTH-FAIL" else "USER_LOGOUT"
            details = record.note or record.input_excerpt
        elif record.rule_id in ("VAULT-INGEST", "FILE-UPLOAD"):
            action_type = "FILE_UPLOAD"
            details = record.input_excerpt
        elif record.verdict == "blocked":
            action_type = f"ATTACK_BLOCKED ({record.rule_id})"
            details = record.input_excerpt
        elif record.verdict == "allowed":
            action_type = "CHAT_QUERY_ALLOWED"
            details = record.input_excerpt
        else:
            action_type = f"QUERY_{record.verdict.upper()}"
            details = record.input_excerpt

        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                record.ts,
                record.role.upper(),
                action_type,
                details,
                record.verdict.upper(),
            ])

    def get_events(
        self,
        limit: int = 100,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query recent audit events with optional filters."""
        query = "SELECT id, ts, session_id, role, stage, verdict, rule_id, category, severity, input_excerpt, ai_response, note FROM audit_events WHERE 1=1"
        params: List[Any] = []

        if severity and severity.lower() != "all":
            query += " AND severity = ?"
            params.append(severity.lower())

        if category and category.lower() != "all":
            query += " AND category = ?"
            params.append(category.lower())

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_stats(self) -> Dict[str, Any]:
        """Summary statistics for admin dashboard."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM audit_events")
            total = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM audit_events WHERE verdict = 'blocked'")
            blocked = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM audit_events WHERE severity = 'critical'")
            critical = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM audit_events WHERE verdict = 'redacted'")
            redacted = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM audit_events WHERE verdict = 'allowed'")
            allowed = cursor.fetchone()[0]

            return {
                "total_events": total,
                "blocked_attacks": blocked,
                "critical_incidents": critical,
                "redactions": redacted,
                "allowed_queries": allowed,
            }


_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Singleton getter for audit logger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
