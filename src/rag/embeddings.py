"""Local Sovereign Embeddings for Kavach.

Supports:
1. Ollama local embeddings (nomic-embed-text)
2. Local SentenceTransformers fallback (all-MiniLM-L6-v2) if Ollama is not yet active
3. Lightweight local deterministic semantic embedding fallback if fully offline
"""

from typing import List, Optional
import math
import requests
from ..config import get_settings


class LocalEmbeddings:
    """Zero-cost local embeddings generator honoring air-gap sovereignty."""

    def __init__(self, model_name: Optional[str] = None, base_url: Optional[str] = None):
        settings = get_settings()
        self.model_name = model_name or settings.embed_model
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._st_model = None

    def _embed_via_ollama(self, text: str) -> Optional[List[float]]:
        """Attempt embedding using local Ollama daemon."""
        try:
            url = f"{self.base_url}/api/embeddings"
            response = requests.post(
                url,
                json={"model": self.model_name, "prompt": text},
                timeout=3.0,
            )
            if response.status_code == 200:
                data = response.json()
                if "embedding" in data:
                    return data["embedding"]
        except Exception:
            pass
        return None

    def _embed_via_sentence_transformers(self, texts: List[str]) -> Optional[List[List[float]]]:
        """Fallback to local SentenceTransformer model if available (100% offline)."""
        try:
            if self._st_model is None:
                import os
                os.environ["HF_HUB_OFFLINE"] = "1"
                os.environ["TRANSFORMERS_OFFLINE"] = "1"
                from sentence_transformers import SentenceTransformer
                try:
                    self._st_model = SentenceTransformer("all-MiniLM-L6-v2", local_files_only=True)
                except Exception:
                    self._st_model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = self._st_model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception:
            return None

    def _deterministic_fallback_embed(self, text: str, dim: int = 384) -> List[float]:
        """Deterministic, lightweight n-gram embedding fallback when completely offline."""
        vec = [0.0] * dim
        words = text.lower().split()
        if not words:
            return vec

        for word in words:
            h = hash(word)
            idx = abs(h) % dim
            vec[idx] += 1.0

        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Compute embeddings for a batch of text documents."""
        # Try Ollama first
        if texts:
            test_ollama = self._embed_via_ollama(texts[0])
            if test_ollama is not None:
                results = [test_ollama]
                for text in texts[1:]:
                    res = self._embed_via_ollama(text) or self._deterministic_fallback_embed(text)
                    results.append(res)
                return results

        # Try SentenceTransformers
        st_res = self._embed_via_sentence_transformers(texts)
        if st_res is not None:
            return st_res

        # Fallback
        return [self._deterministic_fallback_embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        """Compute embedding for a single search query."""
        ollama_res = self._embed_via_ollama(text)
        if ollama_res is not None:
            return ollama_res

        st_res = self._embed_via_sentence_transformers([text])
        if st_res is not None and len(st_res) > 0:
            return st_res[0]

        return self._deterministic_fallback_embed(text)


_embeddings_instance: Optional[LocalEmbeddings] = None


def get_embeddings() -> LocalEmbeddings:
    global _embeddings_instance
    if _embeddings_instance is None:
        _embeddings_instance = LocalEmbeddings()
    return _embeddings_instance
