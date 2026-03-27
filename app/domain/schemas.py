from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, EmailStr, field_validator
from app.domain.models import AgentRole


# ─────────────────────── AUTH / USER ───────────────────────

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    password: str

    @field_validator("username")
    @classmethod
    def username_alphanumeric(cls, v: str) -> str:
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username must be alphanumeric (underscores and hyphens allowed)")
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters")
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ─────────────────────── USER PROFILE ───────────────────────

class ProfileCreate(BaseModel):
    age: Optional[int] = None
    occupation: Optional[str] = None
    goals: Optional[List[str]] = None
    interests: Optional[List[str]] = None
    risk_tolerance: Optional[str] = None       # low / medium / high
    health_focus: Optional[str] = None
    career_stage: Optional[str] = None
    financial_context: Optional[str] = None


class ProfileUpdate(ProfileCreate):
    pass


class ProfileResponse(BaseModel):
    id: int
    user_id: int
    age: Optional[int]
    occupation: Optional[str]
    goals: Optional[List[str]]
    interests: Optional[List[str]]
    risk_tolerance: Optional[str]
    health_focus: Optional[str]
    career_stage: Optional[str]
    financial_context: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────── COUNCIL / CHAT ─────────────────────

class CouncilQueryRequest(BaseModel):
    message: str
    agent_role: Optional[AgentRole] = None    # None → auto-route to Synthesizer
    session_id: Optional[int] = None          # None → create new session

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        if len(v) > 4000:
            raise ValueError("Message too long (max 4000 chars)")
        return v


class AgentInfo(BaseModel):
    role: AgentRole
    name: str
    title: str
    description: str
    color: str
    icon: str


class CouncilQueryResponse(BaseModel):
    session_id: int
    message_id: int
    agent_role: AgentRole
    agent_name: str
    response: str
    model_used: str
    tokens_estimated: int
    created_at: datetime


# ─────────────────────── SESSION ────────────────────────────

class SessionResponse(BaseModel):
    id: int
    user_id: int
    agent_role: AgentRole
    title: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    message_count: int = 0

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: int
    session_id: int
    role: str
    content: str
    agent_role: Optional[AgentRole]
    tokens_used: Optional[int]
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionDetailResponse(BaseModel):
    session: SessionResponse
    messages: List[MessageResponse]


# ─────────────────────── INSIGHTS ───────────────────────────

class InsightResponse(BaseModel):
    id: int
    user_id: int
    agent_role: AgentRole
    title: str
    content: str
    insight_type: Optional[str]
    is_read: bool
    generated_at: datetime
    expires_at: Optional[datetime]

    model_config = {"from_attributes": True}
