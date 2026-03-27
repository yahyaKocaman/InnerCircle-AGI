"""
Insights API — /insights
─────────────────────────
Proactively generated insights from Celery background workers.
Users can list, read, and dismiss insights.
"""

import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.api.deps import get_db, get_current_user
from app.domain.models import User, Insight, AgentRole
from app.domain.schemas import InsightResponse
from app.core.metrics import INSIGHTS_READ_TOTAL

router = APIRouter(tags=["Insights"])
logger = logging.getLogger(__name__)


@router.get(
    "/",
    response_model=List[InsightResponse],
    summary="Get proactive insights",
    description="Returns unread (or all) proactively generated insights for the authenticated user.",
)
def list_insights(
    unread_only: bool = Query(True, description="Return only unread insights"),
    agent_role: Optional[AgentRole] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Insight).filter(Insight.user_id == current_user.id)
    if unread_only:
        q = q.filter(Insight.is_read == False)  # noqa: E712
    if agent_role:
        q = q.filter(Insight.agent_role == agent_role)

    # Filter out expired insights
    now = datetime.now(timezone.utc)
    insights = (
        q.order_by(Insight.generated_at.desc())
        .limit(limit)
        .all()
    )
    # Exclude expired
    valid = [i for i in insights if not i.expires_at or i.expires_at > now]
    return valid


@router.get(
    "/count",
    summary="Unread insight count",
    description="Returns the number of unread insights for notification badge.",
)
def get_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    count = (
        db.query(Insight)
        .filter(Insight.user_id == current_user.id, Insight.is_read == False)  # noqa: E712
        .count()
    )
    return {"unread_count": count}


@router.patch(
    "/{insight_id}/read",
    response_model=InsightResponse,
    summary="Mark insight as read",
)
def mark_as_read(
    insight_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insight = db.query(Insight).filter(
        Insight.id == insight_id,
        Insight.user_id == current_user.id,
    ).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")

    insight.is_read = True
    db.commit()
    db.refresh(insight)

    INSIGHTS_READ_TOTAL.inc()
    return insight


@router.post(
    "/mark-all-read",
    summary="Mark all insights as read",
)
def mark_all_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    updated = (
        db.query(Insight)
        .filter(Insight.user_id == current_user.id, Insight.is_read == False)  # noqa: E712
        .update({"is_read": True})
    )
    db.commit()
    return {"marked_read": updated}


@router.delete(
    "/{insight_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dismiss an insight",
)
def dismiss_insight(
    insight_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    insight = db.query(Insight).filter(
        Insight.id == insight_id,
        Insight.user_id == current_user.id,
    ).first()
    if not insight:
        raise HTTPException(status_code=404, detail="Insight not found")
    db.delete(insight)
    db.commit()
