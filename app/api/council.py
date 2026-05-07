"""
Council API — /council
────────────────────────
Multi-agent conversation endpoints.
Supports both standard and streaming (SSE) responses.
"""

import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.domain.models import (
    User, UserProfile, ConversationSession, Message, AgentRole
)
from app.domain.schemas import (
    CouncilQueryRequest, CouncilQueryResponse,
    SessionResponse, SessionDetailResponse, MessageResponse
)
from app.agents.council import council
from app.core.metrics import (
    COUNCIL_QUERIES_TOTAL, AGENT_QUERY_COUNTER, LLM_LATENCY
)

router = APIRouter(tags=["Council"])
logger = logging.getLogger(__name__)


# ── Helpers ──────────────────────────────────────────────────

def _build_profile_context(profile: Optional[UserProfile]) -> str:
    if not profile:
        return ""
    parts = []
    if profile.age:
        parts.append(f"Yaş: {profile.age}")
    if profile.occupation:
        parts.append(f"Meslek: {profile.occupation}")
    if profile.career_stage:
        parts.append(f"Kariyer aşaması: {profile.career_stage}")
    if profile.risk_tolerance:
        parts.append(f"Risk toleransı: {profile.risk_tolerance}")
    if profile.goals:
        parts.append(f"Hedefler: {', '.join(profile.goals)}")
    if profile.interests:
        parts.append(f"İlgi alanları: {', '.join(profile.interests)}")
    if profile.health_focus:
        parts.append(f"Sağlık odağı: {profile.health_focus}")
    if profile.financial_context:
        parts.append(f"Finansal durum: {profile.financial_context}")
    return "\n".join(parts)


def _get_or_create_session(
    db: Session, user_id: int, agent_role: AgentRole,
    session_id: Optional[int], first_message: str
) -> ConversationSession:
    if session_id:
        session = db.query(ConversationSession).filter(
            ConversationSession.id == session_id,
            ConversationSession.user_id == user_id,
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        return session

    title = first_message[:80] + ("…" if len(first_message) > 80 else "")
    session = ConversationSession(
        user_id=user_id,
        agent_role=agent_role,
        title=title,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _get_session_history(db: Session, session_id: int) -> list[dict]:
    messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .limit(20)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in messages]


# ── Endpoints ─────────────────────────────────────────────────

@router.get(
    "/agents",
    summary="List all council agents",
    description="Returns metadata for all 6 InnerCircle AGI council members.",
)
def list_agents(current_user: User = Depends(get_current_user)):
    return council.get_agent_info()


@router.post(
    "/ask",
    response_model=CouncilQueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask the council",
    description=(
        "Send a message to a specific council agent or let the council auto-route. "
        "Returns a full response. For streaming, use /council/ask/stream."
    ),
)
async def ask_council(
    payload: CouncilQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(UserProfile).filter(
        UserProfile.user_id == current_user.id
    ).first()
    profile_context = _build_profile_context(profile)

    # Determine final agent role (for session creation before routing)
    requested_role = payload.agent_role

    # Create / fetch session (role will be resolved by council)
    temp_role = requested_role or AgentRole.SYNTHESIZER
    session = _get_or_create_session(
        db, current_user.id, temp_role,
        payload.session_id, payload.message
    )

    history = _get_session_history(db, session.id)

    # Save user message
    user_msg = Message(
        session_id=session.id,
        role="user",
        content=payload.message,
    )
    db.add(user_msg)
    db.commit()

    # Call council
    import time
    start = time.perf_counter()
    try:
        response = await council.think(
            user_id=current_user.id,
            message=payload.message,
            requested_role=requested_role,
            profile_context=profile_context,
            history=history,
        )
    except Exception as e:
        logger.exception(f"Council error for user {current_user.id}: {e}")
        raise HTTPException(status_code=503, detail=f"Council unavailable: {str(e)}")
    finally:
        elapsed = time.perf_counter() - start
        LLM_LATENCY.observe(elapsed)

    # Update session role if auto-routed
    if session.agent_role != response.agent_role:
        session.agent_role = response.agent_role
        db.commit()

    # Save assistant message
    assistant_msg = Message(
        session_id=session.id,
        role="assistant",
        content=response.content,
        agent_role=response.agent_role,
        tokens_used=response.tokens_estimated,
    )
    db.add(assistant_msg)
    db.commit()
    db.refresh(assistant_msg)

    # Metrics
    COUNCIL_QUERIES_TOTAL.inc()
    AGENT_QUERY_COUNTER.labels(agent_role=response.agent_role.value).inc()

    logger.info(
        f"Council query completed | user={current_user.username} "
        f"agent={response.agent_role.value} tokens≈{response.tokens_estimated}"
    )

    return CouncilQueryResponse(
        session_id=session.id,
        message_id=assistant_msg.id,
        agent_role=response.agent_role,
        agent_name=response.agent_name,
        response=response.content,
        model_used=response.model_used,
        tokens_estimated=response.tokens_estimated,
        created_at=response.created_at,
    )


@router.post(
    "/ask/stream",
    summary="Ask the council (streaming SSE)",
    description="Stream agent response tokens via Server-Sent Events.",
)
async def ask_council_stream(
    payload: CouncilQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = db.query(UserProfile).filter(
        UserProfile.user_id == current_user.id
    ).first()
    profile_context = _build_profile_context(profile)

    requested_role = payload.agent_role
    temp_role = requested_role or AgentRole.SYNTHESIZER
    session = _get_or_create_session(
        db, current_user.id, temp_role,
        payload.session_id, payload.message
    )

    history = _get_session_history(db, session.id)

    user_msg = Message(
        session_id=session.id,
        role="user",
        content=payload.message,
    )
    db.add(user_msg)
    db.commit()

    async def event_generator():
        full_response = ""

        # Send metadata event first
        meta = {
            "event": "start",
            "session_id": session.id,
            "agent_role": (requested_role or AgentRole.SYNTHESIZER).value,
        }
        yield f"data: {json.dumps(meta)}\n\n"

        try:
            async for token in council.think_stream(
                user_id=current_user.id,
                message=payload.message,
                requested_role=requested_role,
                profile_context=profile_context,
                history=history,
            ):
                full_response += token
                yield f"data: {json.dumps({'token': token})}\n\n"

            # Save to DB after streaming completes
            agent_role_val = requested_role or AgentRole.SYNTHESIZER
            assistant_msg = Message(
                session_id=session.id,
                role="assistant",
                content=full_response,
                agent_role=agent_role_val,
                tokens_used=len(full_response.split()),
            )
            db.add(assistant_msg)
            db.commit()

            COUNCIL_QUERIES_TOTAL.inc()
            AGENT_QUERY_COUNTER.labels(agent_role=agent_role_val.value).inc()

            yield f"data: {json.dumps({'event': 'done', 'message_id': assistant_msg.id})}\n\n"

        except Exception as e:
            logger.exception(f"Streaming error for user {current_user.id}: {e}")
            yield f"data: {json.dumps({'event': 'error', 'detail': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Sessions ──────────────────────────────────────────────────

@router.get(
    "/sessions",
    response_model=List[SessionResponse],
    summary="List conversation sessions",
)
def list_sessions(
    agent_role: Optional[AgentRole] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(ConversationSession).filter(
        ConversationSession.user_id == current_user.id
    )
    if agent_role:
        q = q.filter(ConversationSession.agent_role == agent_role)
    sessions = q.order_by(ConversationSession.started_at.desc()).offset(skip).limit(limit).all()

    result = []
    for s in sessions:
        msg_count = db.query(Message).filter(Message.session_id == s.id).count()
        sr = SessionResponse(
            id=s.id,
            user_id=s.user_id,
            agent_role=s.agent_role,
            title=s.title,
            started_at=s.started_at,
            ended_at=s.ended_at,
            message_count=msg_count,
        )
        result.append(sr)
    return result


@router.get(
    "/sessions/{session_id}",
    response_model=SessionDetailResponse,
    summary="Get session with messages",
)
def get_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
        ConversationSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.created_at.asc())
        .all()
    )
    msg_count = len(messages)
    session_resp = SessionResponse(
        id=session.id, user_id=session.user_id, agent_role=session.agent_role,
        title=session.title, started_at=session.started_at, ended_at=session.ended_at,
        message_count=msg_count,
    )
    msg_resps = [MessageResponse.model_validate(m) for m in messages]
    return SessionDetailResponse(session=session_resp, messages=msg_resps)


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a session",
)
def delete_session(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    session = db.query(ConversationSession).filter(
        ConversationSession.id == session_id,
        ConversationSession.user_id == current_user.id,
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    db.delete(session)
    db.commit()
