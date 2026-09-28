"""Persistent Vector Indexer for Kavach.

Provides local-first vector indexing and search over confidential document chunks.
Uses zero-dependency persistent JSON/numpy index with ChromaDB compatibility seam.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import json
import math
from .chunker import DocumentChunk
from ..rag.embeddings import get_embeddings, LocalEmbeddings
from ..config import get_settings


class Indexer:
    """Stores chunk embeddings and performs top-k semantic search."""

    def __init__(self, storage_dir: Optional[Path] = None, embeddings: Optional[LocalEmbeddings] = None):
        settings = get_settings()
        self.storage_dir = Path(storage_dir or settings.vectorstore_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.store_file = self.storage_dir / "chunks_index.json"
        self.embeddings = embeddings or get_embeddings()
        self.items: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Load stored chunks from disk."""
        if self.store_file.exists():
            try:
                with open(self.store_file, "r", encoding="utf-8") as f:
                    self.items = json.load(f)
            except Exception:
                self.items = []

    def _save(self) -> None:
        """Persist chunk index to disk."""
        with open(self.store_file, "w", encoding="utf-8") as f:
            json.dump(self.items, f, indent=2)

    def index_chunks(self, chunks: List[DocumentChunk]) -> int:
        """Embed and persist new chunks into the vector store."""
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        vectors = self.embeddings.embed_documents(texts)

        new_items = []
        existing_ids = {item["chunk_id"] for item in self.items}

        for chunk, vector in zip(chunks, vectors):
            if chunk.chunk_id in existing_ids:
                # Update existing
                self.items = [it for it in self.items if it["chunk_id"] != chunk.chunk_id]

            new_items.append({
                "chunk_id": chunk.chunk_id,
                "text": chunk.text,
                "metadata": chunk.metadata,
                "vector": vector,
            })

        self.items.extend(new_items)
        self._save()
        return len(new_items)

    @staticmethod
    def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
        """Compute cosine similarity between two float vectors."""
        if not v1 or not v2 or len(v1) != len(v2):
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 <= 0.0 or norm2 <= 0.0:
            return 0.0
        return dot / (norm1 * norm2)

    def search(
        self,
        query: str,
        top_k: int = 4,
        threshold: float = 0.0,
        max_rank: Optional[int] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search the indexed corpus using query embedding similarity with optional metadata/rank filtering."""
        if not self.items:
            return []

        query_vec = self.embeddings.embed_query(query)
        scored = []

        for item in self.items:
            meta = item.get("metadata", {})

            # Filter by maximum rank if specified
            if max_rank is not None:
                chunk_rank = int(meta.get("clearance_rank", 1))
                if chunk_rank > max_rank:
                    continue

            # Filter by where dictionary (ChromaDB-compatible syntax)
            if where:
                matched = True
                for k, v in where.items():
                    if isinstance(v, dict):
                        if "$lte" in v and int(meta.get(k, 1)) > int(v["$lte"]):
                            matched = False
                            break
                        if "$gte" in v and int(meta.get(k, 1)) < int(v["$gte"]):
                            matched = False
                            break
                        if "$eq" in v and meta.get(k) != v["$eq"]:
                            matched = False
                            break
                    elif meta.get(k) != v:
                        matched = False
                        break
                if not matched:
                    continue

            sim = self._cosine_similarity(query_vec, item["vector"])
            if sim >= threshold:
                # Keyword boost for exact industrial terms (furnace, CDU, turbine, capacity, temperature, etc.)
                query_tokens = [t.lower() for t in query.split() if len(t) > 3]
                text_lower = item["text"].lower()
                matches = sum(1 for tok in query_tokens if tok in text_lower)
                # Apply modest boost for relevant query term occurrences
                effective_score = sim + min(0.15, matches * 0.03)

                scored.append({
                    "chunk_id": item["chunk_id"],
                    "text": item["text"],
                    "metadata": item["metadata"],
                    "score": round(effective_score, 4),
                    "base_sim": round(sim, 4),
                })

        # Sort descending by similarity score
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def count(self, max_rank: Optional[int] = None) -> int:
        """Return total indexed chunks, optionally filtered by rank."""
        if max_rank is None:
            return len(self.items)
        return len([it for it in self.items if int(it.get("metadata", {}).get("clearance_rank", 1)) <= max_rank])

    def get_all_chunks(self, max_rank: Optional[int] = None) -> List[Dict[str, Any]]:
        """Return all indexed chunk records, optionally filtered by max clearance rank."""
        if max_rank is None:
            return list(self.items)
        return [
            it for it in self.items
            if int(it.get("metadata", {}).get("clearance_rank", 1)) <= max_rank
        ]

    def clear(self) -> None:
        """Clear all stored vectors."""
        self.items = []
        self._save()



_indexer_instance: Optional[Indexer] = None


def get_indexer() -> Indexer:
    global _indexer_instance
    if _indexer_instance is None:
        _indexer_instance = Indexer()
    return _indexer_instance
