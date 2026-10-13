"""Incident Dispatcher Webhook for Kavach Sovereign AI Workbench.

Dispatches non-blocking, asynchronous security alert notifications to a
configurable webhook endpoint (e.g. ntfy.sh or custom SOC SIEM) upon
guardrail trigger or adversarial probe detection.
"""

import os
import asyncio
import threading
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import requests

logger = logging.getLogger("kavach.alert_dispatcher")

DEFAULT_WEBHOOK_URL = "https://ntfy.sh/kavach-sovereign-alerts"


def _send_webhook_sync(url: str, payload: Dict[str, Any], timeout: float = 2.0) -> None:
    """Send webhook HTTP POST with strict timeout and silent error handling."""
    try:
        headers = {
            "Title": f"KAVACH ALERT: {payload.get('rule', 'UNKNOWN')}",
            "Priority": "high" if "SEC-I-04" in payload.get("rule", "") or "SEC-I-01" in payload.get("rule", "") else "default",
            "Tags": "shield,warning,rotating_light",
        }
        res = requests.post(
            url,
            json=payload,
            headers=headers,
            timeout=timeout,
        )
        if res.status_code in (200, 201, 202, 204):
            logger.info(f"Dispatched security alert for rule {payload.get('rule')} to {url}")
        else:
            logger.warning(f"Webhook returned status {res.status_code}: {res.text[:100]}")
    except requests.exceptions.Timeout:
        logger.warning(f"Alert webhook {url} timed out after {timeout}s (non-blocking).")
    except Exception as exc:
        logger.warning(f"Failed to dispatch security alert to {url}: {exc}")


async def dispatch_security_alert(
    rule_id: str,
    user_role: str,
    query_snippet: str,
    timestamp: Optional[str] = None,
    webhook_url: Optional[str] = None,
) -> None:
    """Non-blocking async security alert dispatcher.

    Sends an HTTP POST to the configured webhook endpoint with a 2-second timeout.
    Fails silently on connection errors with a logged warning.

    Args:
        rule_id: Triggered security rule (e.g., 'SEC-I-04', 'SEC-I-01', 'SEC-R-01')
        user_role: Caller clearance role ('operator', 'analyst', 'commander')
        query_snippet: Excerpt of user query
        timestamp: ISO8601 or formatted timestamp
        webhook_url: Optional custom webhook endpoint; defaults to KAVACH_ALERT_WEBHOOK or ntfy.sh
    """
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    url = webhook_url or os.getenv("KAVACH_ALERT_WEBHOOK", DEFAULT_WEBHOOK_URL)

    payload = {
        "rule": rule_id,
        "role": user_role,
        "query": query_snippet[:100] if query_snippet else "",
        "time": ts,
    }

    loop = asyncio.get_running_loop()
    # Run in default thread pool executor with 2.0s timeout to never block event loop
    try:
        await asyncio.wait_for(
            loop.run_in_executor(None, _send_webhook_sync, url, payload, 2.0),
            timeout=2.0,
        )
    except asyncio.TimeoutError:
        logger.warning(f"Alert webhook {url} exceeded async 2.0s SLA.")
    except Exception as exc:
        logger.warning(f"Alert dispatcher encountered error: {exc}")


def dispatch_security_alert_sync(
    rule_id: str,
    user_role: str,
    query_snippet: str,
    timestamp: Optional[str] = None,
    webhook_url: Optional[str] = None,
) -> None:
    """Synchronous / background thread dispatcher for non-async execution contexts."""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    url = webhook_url or os.getenv("KAVACH_ALERT_WEBHOOK", DEFAULT_WEBHOOK_URL)

    payload = {
        "rule": rule_id,
        "role": user_role,
        "query": query_snippet[:100] if query_snippet else "",
        "time": ts,
    }

    t = threading.Thread(
        target=_send_webhook_sync,
        args=(url, payload, 2.0),
        daemon=True,
    )
    t.start()


def trigger_alert(
    rule_id: str,
    user_role: str,
    query_snippet: str,
    timestamp: Optional[str] = None,
) -> None:
    """Universal dispatcher that uses asyncio.create_task if a loop is active, else background thread."""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(dispatch_security_alert(rule_id, user_role, query_snippet, ts))
    except RuntimeError:
        dispatch_security_alert_sync(rule_id, user_role, query_snippet, ts)
