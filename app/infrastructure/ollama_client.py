"""
Ollama HTTP Client
──────────────────
Async client for communicating with a local Ollama instance.
Supports chat completions and streaming via httpx.

DeepSeek-R1 Support:
  The model produces <think>...</think> internal reasoning blocks before
  the final answer. This client strips those blocks from non-streaming
  responses and emits special __THINKING_START__ / __THINKING_END__
  sentinel tokens during streaming so the UI can render a "reasoning"
  panel separately.
"""

import json
import logging
import re
from typing import AsyncIterator, Optional
import httpx
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── DeepSeek-R1 Think Tag Utilities ──────────────────────────

THINK_START = "__THINKING_START__"
THINK_END   = "__THINKING_END__"

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


def strip_think_tags(text: str) -> str:
    """Remove <think>...</think> blocks from DeepSeek-R1 output."""
    return _THINK_BLOCK_RE.sub("", text).strip()


def extract_think_content(text: str) -> tuple[str, str]:
    """
    Split DeepSeek-R1 output into (thinking_text, answer_text).
    Returns ('', original) if no think blocks found.
    """
    thinking_parts: list[str] = []
    for match in _THINK_BLOCK_RE.finditer(text):
        inner = match.group(0)[7:-8].strip()  # strip <think> and </think>
        thinking_parts.append(inner)
    answer = _THINK_BLOCK_RE.sub("", text).strip()
    return "\n\n".join(thinking_parts), answer


class OllamaClient:
    """Thin async wrapper around the Ollama REST API."""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT

    # ── Core Chat ────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Send a chat request and return the final answer text.
        DeepSeek-R1 <think> blocks are automatically stripped.
        """
        model = model or self.model
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                raw = data["message"]["content"]
                return strip_think_tags(raw)
            except httpx.ConnectError:
                logger.error(f"Cannot connect to Ollama at {self.base_url}")
                raise RuntimeError(
                    "Ollama is not reachable. Please ensure it is running "
                    f"(ollama serve) and accessible at {self.base_url}."
                )
            except httpx.HTTPStatusError as e:
                logger.error(f"Ollama API error: {e.response.status_code} — {e.response.text}")
                raise RuntimeError(f"Ollama API error: {e.response.status_code}")
            except Exception as e:
                logger.exception(f"Unexpected Ollama error: {e}")
                raise

    async def chat_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """
        Stream chat response tokens as they arrive.

        DeepSeek-R1 handling:
          • When a <think> block starts, emits THINK_START sentinel.
          • Tokens inside <think> are still yielded (UI decides display).
          • When </think> is detected, emits THINK_END sentinel.
          • Subsequent tokens are the actual answer.
        """
        model = model or self.model
        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature},
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/chat",
                    json=payload,
                ) as resp:
                    resp.raise_for_status()

                    buffer = ""
                    in_think = False

                    async for line in resp.aiter_lines():
                        if not line.strip():
                            continue
                        try:
                            chunk = json.loads(line)
                            token = chunk.get("message", {}).get("content", "")
                            if not token:
                                if chunk.get("done"):
                                    break
                                continue

                            buffer += token

                            # Detect opening <think>
                            if not in_think and "<think>" in buffer.lower():
                                in_think = True
                                yield THINK_START
                                # Yield everything after <think>
                                after = re.split(r"<think>", buffer, flags=re.IGNORECASE, maxsplit=1)
                                if len(after) > 1:
                                    yield after[1]
                                buffer = ""
                                continue

                            # Detect closing </think>
                            if in_think and "</think>" in buffer.lower():
                                in_think = False
                                # Yield content before </think>
                                parts = re.split(r"</think>", buffer, flags=re.IGNORECASE, maxsplit=1)
                                if parts[0]:
                                    yield parts[0]
                                yield THINK_END
                                # Yield remainder (actual answer starts)
                                if len(parts) > 1 and parts[1]:
                                    yield parts[1]
                                buffer = ""
                                continue

                            # Normal token — yield and clear buffer
                            yield buffer
                            buffer = ""

                            if chunk.get("done"):
                                break

                        except json.JSONDecodeError:
                            continue

                    # Flush remaining buffer
                    if buffer:
                        yield buffer

            except httpx.ConnectError:
                raise RuntimeError(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    "Make sure Ollama is running: `ollama serve`"
                )

    # ── Health / Info ─────────────────────────────────────────

    async def health_check(self) -> dict:
        """Return basic connectivity status and available models."""
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                resp = await client.get(f"{self.base_url}/api/tags")
                models = [m["name"] for m in resp.json().get("models", [])]
                active = self.model in models or any(
                    m.startswith(self.model.split(":")[0]) for m in models
                )
                if not active:
                    logger.warning(
                        f"Model '{self.model}' not found in Ollama. "
                        f"Run: ollama pull {self.model}"
                    )
                return {
                    "status": "ok",
                    "base_url": self.base_url,
                    "configured_model": self.model,
                    "model_available": active,
                    "available_models": models,
                    "pull_command": f"ollama pull {self.model}" if not active else None,
                }
            except Exception as e:
                return {
                    "status": "unreachable",
                    "base_url": self.base_url,
                    "error": str(e),
                    "hint": "Run: ollama serve",
                }

    async def list_models(self) -> list[str]:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{self.base_url}/api/tags")
            return [m["name"] for m in resp.json().get("models", [])]


# ── Singleton ─────────────────────────────────────────────────
ollama = OllamaClient()
