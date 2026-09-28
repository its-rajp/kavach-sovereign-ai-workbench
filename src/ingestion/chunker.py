"""Document Chunker for Kavach.

Splits extracted pages into overlapping text chunks with source and clearance metadata.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    """Represents an atomic text chunk prepared for embedding."""
    chunk_id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _detect_clearance(text: str) -> str:
    """Infer document clearance level from headers and text markers."""
    lower = text.lower()
    if "top secret" in lower or "secret" in lower or "emergency shutdown override" in lower:
        return "secret"
    if "confidential" in lower or "proprietary" in lower or "internal use only" in lower:
        return "confidential"
    if "restricted" in lower:
        return "restricted"
    return "public"


def split_text_recursive(text: str, chunk_size: int = 800, chunk_overlap: int = 120) -> List[str]:
    """Recursively split text by paragraphs, sentences, and words with overlap."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    chunks: List[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end]

        # Prefer breaking on paragraph or sentence boundary if near end
        if end < len(text):
            break_point = max(
                chunk.rfind("\n\n"),
                chunk.rfind("\n"),
                chunk.rfind(". "),
            )
            if break_point > chunk_size // 2:
                end = start + break_point + 1
                chunk = text[start:end]

        cleaned = chunk.strip()
        if cleaned:
            chunks.append(cleaned)

        if end >= len(text):
            break
        start = max(start + 1, end - chunk_overlap)

    return chunks


def chunk_documents(
    pages: List[Dict[str, Any]],
    chunk_size: int = 800,
    chunk_overlap: int = 120,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> List[DocumentChunk]:
    """Split page documents into DocumentChunk objects with provenance tracking."""
    result: List[DocumentChunk] = []

    for page in pages:
        text = page.get("text", "")
        meta = page.get("metadata", {})
        source = meta.get("source", "unknown")
        page_num = meta.get("page", 1)

        raw_chunks = split_text_recursive(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        for idx, chunk_text in enumerate(raw_chunks):
            chunk_id = f"{source}_p{page_num}_c{idx+1}"
            clearance = _detect_clearance(chunk_text)

            chunk_meta = dict(meta)
            if extra_metadata:
                chunk_meta.update(extra_metadata)

            chunk_meta.update({
                "chunk_id": chunk_id,
                "chunk_index": idx + 1,
                "clearance": chunk_meta.get("clearance", clearance),
                "char_length": len(chunk_text),
            })

            result.append(DocumentChunk(
                chunk_id=chunk_id,
                text=chunk_text,
                metadata=chunk_meta,
            ))

    return result

