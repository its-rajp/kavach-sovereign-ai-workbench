"""Configuration module for Kavach.

Loads declarative settings from config/config.yaml and environment variables.
"""

from pathlib import Path
from typing import Optional
import os
import yaml
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """System settings for Kavach."""

    llm_model: str = Field(default="qwen2.5:3b", description="Ollama LLM model name")
    embed_model: str = Field(default="nomic-embed-text", description="Embedding model name")
    ollama_base_url: str = Field(default="http://localhost:11434", description="Local Ollama endpoint")
    request_timeout_seconds: int = Field(default=30, description="Ollama call timeout")

    chunk_size: int = Field(default=800, description="Document chunk size in chars")
    chunk_overlap: int = Field(default=120, description="Chunk overlap in chars")
    top_k: int = Field(default=4, description="Maximum retrieved chunks per query")
    similarity_threshold: float = Field(default=0.25, description="Minimum cosine similarity")

    vectorstore_dir: Path = Field(default=Path("data/vectorstore"))
    raw_docs_dir: Path = Field(default=Path("data/raw"))
    audit_log_path: Path = Field(default=Path("logs/audit.jsonl"))
    audit_db_path: Path = Field(default=Path("logs/audit.db"))
    audit_csv_path: Path = Field(default=Path("logs/kavach_audit_ledger.csv"), description="CSV telemetry ledger")

    max_answer_chars: int = Field(default=1500, description="Anti-exfiltration output length cap")
    allow_network: bool = Field(default=False, description="Sovereignty runtime network egress guard")
    fail_closed: bool = Field(default=True, description="Fail-closed behavior on security errors")
    memory_window_turns: int = Field(default=6, description="Session buffer turn window")
    admin_password: str = Field(default="MRPL_SOVEREIGN_2026", description="Admin override password for RBAC gate")


_settings: Optional[Settings] = None


def get_settings(config_path: Optional[Path] = None) -> Settings:
    """Load and cache settings singleton."""
    global _settings
    if _settings is not None and config_path is None:
        return _settings

    target_path = config_path or Path(__file__).resolve().parent.parent / "config" / "config.yaml"
    data = {}

    if target_path.exists():
        with open(target_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
            if isinstance(yaml_data, dict):
                data.update(yaml_data)

    # Environment variable overrides
    if os.getenv("KAVACH_LLM_MODEL"):
        data["llm_model"] = os.getenv("KAVACH_LLM_MODEL")
    if os.getenv("KAVACH_OLLAMA_BASE_URL"):
        data["ollama_base_url"] = os.getenv("KAVACH_OLLAMA_BASE_URL")
    if os.getenv("KAVACH_CHUNK_SIZE"):
        data["chunk_size"] = int(os.getenv("KAVACH_CHUNK_SIZE"))
    if os.getenv("KAVACH_TOP_K"):
        data["top_k"] = int(os.getenv("KAVACH_TOP_K"))
    if os.getenv("KAVACH_ALLOW_NETWORK"):
        data["allow_network"] = os.getenv("KAVACH_ALLOW_NETWORK").lower() in ("1", "true", "yes")

    settings = Settings(**data)
    if config_path is None:
        _settings = settings
    return settings
