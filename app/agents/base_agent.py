"""
BaseAgent — Abstract foundation for all InnerCircle council members.
────────────────────────────────────────────────────────────────────
Each agent:
  • Has a unique role, name, system prompt and tone.
  • Retrieves relevant past interactions from ChromaDB.
  • Calls OpenAI GPT for generation.
  • Stores the interaction back into memory.

Streaming:
  think_stream() yields tokens via SSE for real-time UI rendering.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, AsyncIterator

from app.domain.models import AgentRole
from app.infrastructure.openai_client import llm, THINK_START, THINK_END
from app.infrastructure.chroma_client import get_memory, AgentMemory

logger = logging.getLogger(__name__)

AGENT_METADATA = {
    AgentRole.LIFE_COACH:  {"name": "Yaşam Koçu",              "color": "#8B5CF6", "icon": "🧭"},
    AgentRole.INVESTMENT:  {"name": "Yatırım & Finans",         "color": "#F59E0B", "icon": "📈"},
    AgentRole.PERFORMANCE: {"name": "Performans Koçu",          "color": "#10B981", "icon": "⚡"},
    AgentRole.CAREER:      {"name": "Kariyer Stratejisti",      "color": "#3B82F6", "icon": "🚀"},
    AgentRole.HEALTH:      {"name": "Sağlık & Zihin Mimarı",   "color": "#EF4444", "icon": "🧬"},
    AgentRole.SYNTHESIZER: {"name": "Sentezci",                 "color": "#6B7280", "icon": "🔮"},
}


@dataclass
class AgentResponse:
    content: str
    agent_role: AgentRole
    agent_name: str
    model_used: str
    tokens_estimated: int
    thinking: str = ""                   # Raw CoT content (not shown to user by default)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class BaseAgent(ABC):
    """Abstract base for all council agents."""

    role: AgentRole
    title: str
    description: str

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Core identity and expertise of this agent."""
        ...

    # ── Memory ───────────────────────────────────────────────

    @property
    def memory(self) -> AgentMemory:
        return get_memory(self.role)

    @property
    def name(self) -> str:
        return AGENT_METADATA[self.role]["name"]

    @property
    def color(self) -> str:
        return AGENT_METADATA[self.role]["color"]

    @property
    def icon(self) -> str:
        return AGENT_METADATA[self.role]["icon"]

    # ── Context Building ──────────────────────────────────────

    def _build_context(self, user_id: int, query: str, profile_context: str = "") -> str:
        """Retrieve relevant memory and construct system context."""
        memories = self.memory.retrieve(user_id=user_id, query=query, n_results=5)

        context_parts = []

        if profile_context:
            context_parts.append(f"[KULLANICI PROFİLİ]\n{profile_context}")

        if memories:
            mem_text = "\n\n".join(
                f"— {m['content'][:500]}" for m in memories if m["score"] > 0.3
            )
            if mem_text:
                context_parts.append(f"[GEÇMİŞ ETKİLEŞİMLER — İlgili bellekler]\n{mem_text}")

        return "\n\n".join(context_parts)

    def _build_messages(
        self,
        user_message: str,
        context: str,
        history: Optional[list[dict]] = None,
    ) -> list[dict]:
        """Construct the message list for OpenAI chat."""
        system = self.system_prompt
        if context:
            system += f"\n\n{context}"

        messages = [{"role": "system", "content": system}]

        # Include last N history turns for conversational continuity
        if history:
            for turn in history[-6:]:   # last 3 exchanges
                messages.append({"role": turn["role"], "content": turn["content"]})

        messages.append({"role": "user", "content": user_message})
        return messages

    # ── Core Generation ───────────────────────────────────────

    async def think(
        self,
        user_id: int,
        message: str,
        profile_context: str = "",
        history: Optional[list[dict]] = None,
        store_memory: bool = True,
    ) -> AgentResponse:
        """Generate a response and optionally persist the interaction."""
        context = self._build_context(user_id, message, profile_context)
        messages = self._build_messages(message, context, history)

        try:
            response_text = await llm.chat(messages=messages)
        except RuntimeError as e:
            response_text = (
                f"Şu anda AI servisine bağlanılamıyor. "
                f"Lütfen API anahtarınızın geçerli olduğundan emin olun. Hata: {e}"
            )

        if store_memory and response_text and not response_text.startswith("Şu anda AI"):
            interaction = f"Kullanıcı: {message}\n{self.name}: {response_text}"
            self.memory.store(
                user_id=user_id,
                content=interaction,
                role="interaction",
                extra_metadata={"session_type": "chat"},
            )

        tokens_est = len(message.split()) + len(response_text.split())

        return AgentResponse(
            content=response_text,
            agent_role=self.role,
            agent_name=self.name,
            model_used=f"openai/{llm.model}",
            tokens_estimated=tokens_est,
        )

    async def think_stream(
        self,
        user_id: int,
        message: str,
        profile_context: str = "",
        history: Optional[list[dict]] = None,
    ) -> AsyncIterator[str]:
        """
        Stream tokens as they are generated via OpenAI SSE.
        Each token is yielded immediately for real-time UI rendering.
        """
        context = self._build_context(user_id, message, profile_context)
        messages = self._build_messages(message, context, history)

        full_response = ""

        async for token in llm.chat_stream(messages=messages):
            full_response += token
            yield token

        # Store after streaming completes
        if full_response:
            interaction = f"Kullanıcı: {message}\n{self.name}: {full_response}"
            self.memory.store(
                user_id=user_id,
                content=interaction,
                role="interaction",
                extra_metadata={"session_type": "stream"},
            )

    async def generate_insight(self, user_id: int, profile_context: str = "") -> Optional[str]:
        """
        Produce a single proactive insight for a user.
        Called by Celery background tasks. Non-intrusive.
        """
        prompt = (
            "Kullanıcının geçmiş etkileşimlerine ve profiline dayanarak, "
            "bu hafta için beklenmedik bir bağlantı, derin bir soru veya "
            "veri odaklı bir gözlem içeren tek bir yüksek değerli insight üret. "
            "Maksimum 3 cümle. Karar verme, öneri dayatma yasak. "
            "Sadece düşündürücü, ilginç bir perspektif sun."
        )
        memories = self.memory.retrieve(user_id=user_id, query="geçmiş hedefler ve gelişimler", n_results=8)
        if not memories:
            return None  # No context to generate from

        mem_text = "\n".join(m["content"][:300] for m in memories[:5])
        full_prompt = f"{prompt}\n\nGeçmiş context:\n{mem_text}"

        try:
            response = await llm.chat(
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": full_prompt},
                ],
                temperature=0.85,
            )
            return response
        except Exception as e:
            logger.warning(f"Insight generation failed for agent {self.role}: {e}")
            return None
