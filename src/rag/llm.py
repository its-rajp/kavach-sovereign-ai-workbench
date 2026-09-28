"""Local LLM Client for Kavach.

Communicates with local Ollama daemon (qwen2.5:3b / llama3:8b / phi3:mini).
Features deterministic fallback for offline/air-gapped environments.
"""

from typing import Optional, Dict, Any, List
import requests
from ..config import get_settings


class LocalLLM:
    """Client for local inference via Ollama."""

    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
    ):
        settings = get_settings()
        self.model = model or settings.llm_model
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.temperature = temperature
        self.timeout = settings.request_timeout_seconds

    def is_available(self) -> bool:
        """Check if local Ollama daemon is reachable."""
        try:
            res = requests.get(f"{self.base_url}/api/tags", timeout=1.5)
            return res.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate response via Ollama with fail-safe local extractive fallback."""
        if self.is_available():
            try:
                payload: Dict[str, Any] = {
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                    }
                }
                if system_prompt:
                    payload["system"] = system_prompt

                res = requests.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    timeout=self.timeout,
                )
                if res.status_code == 200:
                    data = res.json()
                    response_str = data.get("response", "").strip()
                    if response_str:
                        return response_str
                else:
                    print(f"⚠️ Ollama returned non-200 status code: {res.status_code} - {res.text[:200]}")
            except Exception as e:
                print(f"⚠️ Ollama generate exception ({type(e).__name__}): {e}")

        # Offline deterministic extraction fallback: summarize relevant context
        print("ℹ️ Using offline extractive fallback for response.")
        return self._extractive_fallback(prompt)

    @staticmethod
    def _extractive_fallback(prompt: str) -> str:
        """Grounding-preserving fallback when Ollama daemon is starting or inactive."""
        context_part = ""
        question_part = ""

        # Find context block within prompt
        if "--- CONTEXT START ---" in prompt and "--- CONTEXT END ---" in prompt:
            context_part = prompt.split("--- CONTEXT START ---")[1].split("--- CONTEXT END ---")[0].strip()
            if "User Question:" in prompt:
                question_part = prompt.split("User Question:")[1].split("Answer:")[0].strip()
        elif "CONTEXT:" in prompt and "USER QUESTION:" in prompt:
            context_part = prompt.split("CONTEXT:")[1].split("USER QUESTION:")[0].strip()
            question_part = prompt.split("USER QUESTION:")[1].strip()

        if context_part:
            if "No relevant confidential documents found" in context_part:
                return "I do not have information regarding this query in the authorized confidential documentation."

            # Return grounded summary of the retrieved context
            sentences = [s.strip() for s in context_part.split(".") if s.strip()]
            q_words = set(question_part.lower().split())

            relevant = []
            for s in sentences:
                s_words = set(s.lower().split())
                if len(q_words.intersection(s_words)) >= 2:
                    relevant.append(s)

            if relevant:
                return ". ".join(relevant[:3]) + "."
            elif sentences:
                return sentences[0] + "."

        return "I do not have sufficient authorized information in the provided documentation to answer this question."


_llm_instance: Optional[LocalLLM] = None


def get_llm() -> LocalLLM:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = LocalLLM()
    return _llm_instance
