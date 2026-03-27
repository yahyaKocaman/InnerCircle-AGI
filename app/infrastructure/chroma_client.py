"""
ChromaDB Agent Memory
─────────────────────
Each council agent has its own ChromaDB collection for persistent,
per-user vector memory. Enables context retrieval across sessions.
"""

import logging
import hashlib
from datetime import datetime, timezone
from typing import Optional
import chromadb
from chromadb.config import Settings as ChromaSettings
from app.core.config import settings
from app.domain.models import AgentRole

logger = logging.getLogger(__name__)

# ── Chroma Client (singleton) ─────────────────────────────────
_chroma_client: Optional[chromadb.PersistentClient] = None


def get_chroma_client() -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        logger.info(f"ChromaDB initialised at: {settings.CHROMA_PERSIST_DIR}")
    return _chroma_client


# ── Agent Memory ──────────────────────────────────────────────

class AgentMemory:
    """
    Per-agent vector memory backed by ChromaDB.

    Collection naming: innercircle_{agent_role}
    Documents are stored with metadata: user_id, role, timestamp.
    Retrieval is filtered by user_id for privacy isolation.
    """

    def __init__(self, agent_role: AgentRole):
        self.agent_role = agent_role
        self.collection_name = f"innercircle_{agent_role.value}"
        self._collection: Optional[chromadb.Collection] = None

    @property
    def collection(self) -> chromadb.Collection:
        if self._collection is None:
            client = get_chroma_client()
            self._collection = client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def _make_id(self, user_id: int, content: str) -> str:
        """Deterministic document ID based on user + content hash."""
        hash_val = hashlib.sha256(f"{user_id}:{content[:200]}".encode()).hexdigest()[:16]
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        return f"u{user_id}_{ts}_{hash_val}"

    def store(
        self,
        user_id: int,
        content: str,
        role: str = "interaction",     # interaction / insight / profile
        extra_metadata: Optional[dict] = None,
    ) -> str:
        """Store a text document in the agent's collection."""
        doc_id = self._make_id(user_id, content)
        metadata = {
            "user_id": str(user_id),
            "agent_role": self.agent_role.value,
            "role": role,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if extra_metadata:
            metadata.update(extra_metadata)

        self.collection.add(
            ids=[doc_id],
            documents=[content],
            metadatas=[metadata],
        )
        logger.debug(f"[{self.agent_role.value}] Stored memory for user {user_id}: {doc_id}")
        return doc_id

    def retrieve(
        self,
        user_id: int,
        query: str,
        n_results: int = 5,
    ) -> list[dict]:
        """Retrieve relevant memories for a user by semantic similarity."""
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where={"user_id": str(user_id)},
            )
            docs      = results.get("documents", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]
            distances = results.get("distances",  [[]])[0]

            return [
                {
                    "content":  doc,
                    "metadata": meta,
                    "score":    round(1 - dist, 4),  # cosine similarity
                }
                for doc, meta, dist in zip(docs, metadatas, distances)
            ]
        except Exception as e:
            logger.warning(f"Memory retrieval failed for user {user_id}: {e}")
            return []

    def count_user_docs(self, user_id: int) -> int:
        try:
            result = self.collection.get(where={"user_id": str(user_id)})
            return len(result["ids"])
        except Exception:
            return 0

    def clear_user_memory(self, user_id: int) -> int:
        """Delete all memory documents for a specific user. Returns count deleted."""
        try:
            result = self.collection.get(where={"user_id": str(user_id)})
            ids = result["ids"]
            if ids:
                self.collection.delete(ids=ids)
            logger.info(f"[{self.agent_role.value}] Cleared {len(ids)} docs for user {user_id}")
            return len(ids)
        except Exception as e:
            logger.warning(f"Failed to clear memory for user {user_id}: {e}")
            return 0


# ── Pre-built memory instances (one per agent) ────────────────
agent_memories: dict[AgentRole, AgentMemory] = {
    role: AgentMemory(role) for role in AgentRole
}


def get_memory(role: AgentRole) -> AgentMemory:
    return agent_memories[role]
