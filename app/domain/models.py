import enum
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean,
    ForeignKey, Enum as SAEnum, Text, JSON
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.infrastructure.database import Base


# ── Enums ────────────────────────────────────────────────────

class AgentRole(str, enum.Enum):
    LIFE_COACH   = "life_coach"
    INVESTMENT   = "investment"
    PERFORMANCE  = "performance"
    CAREER       = "career"
    HEALTH       = "health"
    SYNTHESIZER  = "synthesizer"


# ── User ─────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50), unique=True, index=True, nullable=False)
    email           = Column(String(255), unique=True, index=True, nullable=False)
    full_name       = Column(String(100), nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    profile  = relationship("UserProfile", back_populates="user", uselist=False,
                            cascade="all, delete-orphan")
    sessions = relationship("ConversationSession", back_populates="user",
                            cascade="all, delete-orphan")
    insights = relationship("Insight", back_populates="user",
                            cascade="all, delete-orphan")


# ── User Profile ─────────────────────────────────────────────

class UserProfile(Base):
    """Enriched user context — feeds into each agent's system prompt."""
    __tablename__ = "user_profiles"

    id             = Column(Integer, primary_key=True, index=True)
    user_id        = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    age            = Column(Integer, nullable=True)
    occupation     = Column(String(200), nullable=True)
    goals          = Column(JSON, nullable=True)          # list[str]
    interests      = Column(JSON, nullable=True)          # list[str]
    risk_tolerance = Column(String(20), nullable=True)    # low / medium / high
    health_focus   = Column(String(500), nullable=True)
    career_stage   = Column(String(100), nullable=True)   # junior / mid / senior / executive
    financial_context = Column(String(500), nullable=True)
    created_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at     = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                            onupdate=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="profile")


# ── Conversation Session ──────────────────────────────────────

class ConversationSession(Base):
    __tablename__ = "conversation_sessions"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_role = Column(SAEnum(AgentRole), nullable=False)
    title      = Column(String(300), nullable=True)      # auto-generated from first message
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at   = Column(DateTime, nullable=True)

    user     = relationship("User", back_populates="sessions")
    messages = relationship("Message", back_populates="session",
                            cascade="all, delete-orphan", order_by="Message.created_at")


# ── Message ──────────────────────────────────────────────────

class Message(Base):
    __tablename__ = "messages"

    id          = Column(Integer, primary_key=True, index=True)
    session_id  = Column(Integer, ForeignKey("conversation_sessions.id"), nullable=False)
    role        = Column(String(20), nullable=False)      # user / assistant / system
    content     = Column(Text, nullable=False)
    agent_role  = Column(SAEnum(AgentRole), nullable=True)
    tokens_used = Column(Integer, nullable=True)
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    session = relationship("ConversationSession", back_populates="messages")


# ── Insight ──────────────────────────────────────────────────

class Insight(Base):
    """Proactively generated insights by Celery background tasks."""
    __tablename__ = "insights"

    id           = Column(Integer, primary_key=True, index=True)
    user_id      = Column(Integer, ForeignKey("users.id"), nullable=False)
    agent_role   = Column(SAEnum(AgentRole), nullable=False)
    title        = Column(String(300), nullable=False)
    content      = Column(Text, nullable=False)
    insight_type = Column(String(50), nullable=True)     # observation / question / trend
    is_read      = Column(Boolean, default=False)
    generated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at   = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="insights")