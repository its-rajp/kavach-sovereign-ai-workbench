"""Durable Memory Store Seam for Kavach.

Future extensibility point for durable session persistence (structure.md).
"""

from typing import Optional, Dict, Any
from pathlib import Path


class DurableStoreSeam:
    """Interface placeholder for enterprise-grade persistent session caches."""

    def __init__(self, persistence_dir: Optional[Path] = None):
        self.persistence_dir = persistence_dir

    def persist(self, session_id: str, data: Dict[str, Any]) -> bool:
        # Default MVP behavior: ephemeral only (NFR-09)
        return False

    def load(self, session_id: str) -> Optional[Dict[str, Any]]:
        return None
