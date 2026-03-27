"""
InnerCircle AGI — Council Orchestrator (LangGraph)
────────────────────────────────────────────────────
Routes user queries to the appropriate council agent.
Uses LangGraph StateGraph for stateful, conditional routing.

Flow:
  user_message
      ↓
  [router] → classify intent → choose agent
      ↓
  [agent_node] → retrieve memory → ollama → store memory
      ↓
  [synthesizer_node] (optional, for cross-domain queries)
      ↓
  AgentResponse
"""

import logging
from typing import Optional, TypedDict, AsyncIterator
from langgraph.graph import StateGraph, END

from app.domain.models import AgentRole
from app.agents.base_agent import AgentResponse, AGENT_METADATA
from app.agents.life_coach import life_coach
from app.agents.investment import investment_agent
from app.agents.performance import performance_agent
from app.agents.career import career_agent
from app.agents.health import health_agent
from app.agents.synthesizer import synthesizer_agent

logger = logging.getLogger(__name__)

# ── Agent Registry ────────────────────────────────────────────
AGENT_REGISTRY = {
    AgentRole.LIFE_COACH:   life_coach,
    AgentRole.INVESTMENT:   investment_agent,
    AgentRole.PERFORMANCE:  performance_agent,
    AgentRole.CAREER:       career_agent,
    AgentRole.HEALTH:       health_agent,
    AgentRole.SYNTHESIZER:  synthesizer_agent,
}

# ── Routing Keywords ──────────────────────────────────────────
ROUTING_KEYWORDS = {
    AgentRole.INVESTMENT: [
        "yatırım", "borsa", "kripto", "hisse", "portföy", "para", "finans",
        "bütçe", "tasarruf", "faiz", "döviz", "emtia", "altın", "bitcoin",
        "invest", "stock", "finance", "budget", "wealth", "crypto"
    ],
    AgentRole.PERFORMANCE: [
        "antrenman", "egzersiz", "spor", "koşu", "kas", "kilo", "fizikel",
        "recovery", "uyku program", "performans", "atletik", "workout",
        "gym", "training", "strength", "cardio", "sport", "fitness"
    ],
    AgentRole.CAREER: [
        "kariyer", "iş", "işe alım", "maaş", "terfi", "cv", "mülakat",
        "şirket", "yönetici", "liderlik", "network", "linkedin", "meslek",
        "career", "job", "salary", "promotion", "work", "professional"
    ],
    AgentRole.HEALTH: [
        "sağlık", "hastalık", "doktor", "ilaç", "beslenme", "diyet",
        "hormon", "enerji seviyesi", "yorgunluk", "stres", "anksiyete",
        "uyku kalitesi", "beyin", "zihin", "meditasyon", "biohack",
        "health", "nutrition", "sleep", "stress", "mind", "brain"
    ],
    AgentRole.LIFE_COACH: [
        "mutluluk", "amaç", "anlam", "hedef", "motivasyon", "alışkanlık",
        "değer", "hayat", "ilişki", "karar", "kişisel gelişim", "büyüme",
        "happiness", "purpose", "meaning", "goal", "habit", "life", "growth"
    ],
}


# ── LangGraph State ───────────────────────────────────────────

class CouncilState(TypedDict):
    user_id: int
    message: str
    requested_role: Optional[str]        # Explicit role from user or None
    resolved_role: Optional[str]         # Role after routing decision
    profile_context: str
    history: list[dict]
    response: Optional[AgentResponse]
    error: Optional[str]


# ── Graph Nodes ───────────────────────────────────────────────

def routing_node(state: CouncilState) -> CouncilState:
    """
    Determine which agent should handle this query.
    Priority: explicit request > keyword detection > synthesizer fallback.
    """
    if state.get("requested_role"):
        state["resolved_role"] = state["requested_role"]
        return state

    message_lower = state["message"].lower()
    scores: dict[AgentRole, int] = {role: 0 for role in AgentRole}

    for role, keywords in ROUTING_KEYWORDS.items():
        for kw in keywords:
            if kw in message_lower:
                scores[role] += 1

    best_role = max(scores, key=lambda r: scores[r])
    if scores[best_role] > 0:
        state["resolved_role"] = best_role.value
    else:
        state["resolved_role"] = AgentRole.SYNTHESIZER.value

    logger.debug(f"Council routing: '{state['message'][:60]}' → {state['resolved_role']}")
    return state


def decide_next(state: CouncilState) -> str:
    """Conditional edge: which agent node to call."""
    role = state.get("resolved_role", AgentRole.SYNTHESIZER.value)
    return role


# ── Orchestrator ──────────────────────────────────────────────

class CouncilOrchestrator:
    """
    Manages the LangGraph council graph.
    Provides both sync-compatible async think() and streaming think_stream().
    """

    def __init__(self):
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(CouncilState)

        # Router node
        graph.add_node("router", routing_node)
        graph.set_entry_point("router")

        # Agent nodes (placeholders — actual LLM call in think())
        # We don't add async nodes to the graph as LangGraph sync nodes
        # cannot await. Instead the graph resolves the role; agents are
        # called directly after compile.
        graph.add_conditional_edges(
            "router",
            decide_next,
            {role.value: END for role in AgentRole},
        )

        return graph.compile()

    def _resolve_role(self, message: str, requested_role: Optional[AgentRole]) -> AgentRole:
        """Run only the routing logic synchronously."""
        state: CouncilState = {
            "user_id": 0,
            "message": message,
            "requested_role": requested_role.value if requested_role else None,
            "resolved_role": None,
            "profile_context": "",
            "history": [],
            "response": None,
            "error": None,
        }
        result = self._graph.invoke(state)
        role_str = result.get("resolved_role", AgentRole.SYNTHESIZER.value)
        try:
            return AgentRole(role_str)
        except ValueError:
            return AgentRole.SYNTHESIZER

    async def think(
        self,
        user_id: int,
        message: str,
        requested_role: Optional[AgentRole] = None,
        profile_context: str = "",
        history: Optional[list[dict]] = None,
    ) -> AgentResponse:
        """Route to the appropriate agent and get a full response."""
        resolved_role = self._resolve_role(message, requested_role)
        agent = AGENT_REGISTRY[resolved_role]

        logger.info(f"Council dispatching to [{resolved_role.value}] for user {user_id}")

        return await agent.think(
            user_id=user_id,
            message=message,
            profile_context=profile_context,
            history=history or [],
        )

    async def think_stream(
        self,
        user_id: int,
        message: str,
        requested_role: Optional[AgentRole] = None,
        profile_context: str = "",
        history: Optional[list[dict]] = None,
    ) -> AsyncIterator[str]:
        """Route to the appropriate agent and stream the response."""
        resolved_role = self._resolve_role(message, requested_role)
        agent = AGENT_REGISTRY[resolved_role]

        async for token in agent.think_stream(
            user_id=user_id,
            message=message,
            profile_context=profile_context,
            history=history or [],
        ):
            yield token

    @staticmethod
    def get_agent_info() -> list[dict]:
        """Return metadata for all council agents."""
        return [
            {
                "role":        role.value,
                "name":        AGENT_METADATA[role]["name"],
                "color":       AGENT_METADATA[role]["color"],
                "icon":        AGENT_METADATA[role]["icon"],
                "title":       AGENT_REGISTRY[role].title,
                "description": AGENT_REGISTRY[role].description,
            }
            for role in AgentRole
        ]


# ── Singleton ─────────────────────────────────────────────────
council = CouncilOrchestrator()
