"""
OpenAI LLM Client
──────────────────
Async client for communicating with the OpenAI API.
Supports chat completions and streaming via the official SDK.

Replaces the previous Ollama client while maintaining the same
interface for seamless integration with the agent layer.
"""

import logging
from typing import AsyncIterator, Optional
from openai import AsyncOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Sentinel tokens (kept for interface compatibility) ───────
THINK_START = "__THINKING_START__"
THINK_END   = "__THINKING_END__"


def strip_think_tags(text: str) -> str:
    """No-op for OpenAI — GPT models don't produce think blocks."""
    return text.strip()


def extract_think_content(text: str) -> tuple[str, str]:
    """No-op for OpenAI — returns ('', original_text)."""
    return "", text.strip()


class OpenAIClient:
    """Async wrapper around the OpenAI Chat Completions API."""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.model = settings.OPENAI_MODEL
        self.timeout = settings.OPENAI_TIMEOUT
        self.max_tokens = settings.OPENAI_MAX_TOKENS
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                timeout=self.timeout,
            )
        return self._client

    # ── Core Chat ────────────────────────────────────────────

    async def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> str:
        """
        Send a chat request and return the final answer text.
        """
        model = model or self.model

        try:
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=self.max_tokens,
                stream=False,
            )
            content = response.choices[0].message.content or ""
            return content.strip()

        except Exception as e:
            logger.exception(f"OpenAI API error: {e}")
            raise RuntimeError(
                f"OpenAI API hatası: {str(e)}. "
                "Lütfen API anahtarınızın geçerli olduğundan emin olun."
            )

    async def chat_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """
        Stream chat response tokens as they arrive via SSE.
        """
        model = model or self.model

        try:
            stream = await self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=self.max_tokens,
                stream=True,
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    yield delta.content

        except Exception as e:
            logger.exception(f"OpenAI streaming error: {e}")
            raise RuntimeError(
                f"OpenAI streaming hatası: {str(e)}. "
                "Lütfen API anahtarınızı ve internet bağlantınızı kontrol edin."
            )

    # ── Health / Info ─────────────────────────────────────────

    async def health_check(self) -> dict:
        """Return basic connectivity status."""
        try:
            models = await self.client.models.list()
            model_names = [m.id for m in models.data[:20]]
            active = self.model in model_names or any(
                m.startswith(self.model.split("-")[0]) for m in model_names
            )
            return {
                "status": "ok",
                "provider": "openai",
                "configured_model": self.model,
                "model_available": active,
                "available_models": model_names[:10],
            }
        except Exception as e:
            return {
                "status": "unreachable",
                "provider": "openai",
                "error": str(e),
                "hint": "Check OPENAI_API_KEY in .env",
            }

    async def list_models(self) -> list[str]:
        models = await self.client.models.list()
        return [m.id for m in models.data]


# ── Singleton ─────────────────────────────────────────────────
llm = OpenAIClient()
