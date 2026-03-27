"""
Insight Generator — Celery Background Task
────────────────────────────────────────────
Proactively generates high-value, non-intrusive insights for each user.
Runs every 6 hours via Celery Beat.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.core.celery_app import celery_app
from app.infrastructure.database import SessionLocal
from app.domain.models import User, UserProfile, Insight, AgentRole
from app.agents.life_coach import life_coach
from app.agents.investment import investment_agent
from app.agents.performance import performance_agent
from app.agents.career import career_agent
from app.agents.health import health_agent
from app.agents.synthesizer import synthesizer_agent
from app.core.config import settings

logger = logging.getLogger(__name__)

# Map each role to its agent instance
INSIGHT_AGENTS = {
    AgentRole.LIFE_COACH:   life_coach,
    AgentRole.INVESTMENT:   investment_agent,
    AgentRole.PERFORMANCE:  performance_agent,
    AgentRole.CAREER:       career_agent,
    AgentRole.HEALTH:       health_agent,
    AgentRole.SYNTHESIZER:  synthesizer_agent,
}

# Insight type labels
INSIGHT_TITLES = {
    AgentRole.LIFE_COACH:   "Yaşam Perspektifi",
    AgentRole.INVESTMENT:   "Piyasa Gözlemi",
    AgentRole.PERFORMANCE:  "Performans Notu",
    AgentRole.CAREER:       "Kariyer Sinyali",
    AgentRole.HEALTH:       "Sağlık İçgörüsü",
    AgentRole.SYNTHESIZER:  "Konsey Sentezi",
}


def _build_profile_context(profile: UserProfile | None) -> str:
    if not profile:
        return ""
    parts = []
    if profile.age:          parts.append(f"Yaş: {profile.age}")
    if profile.occupation:   parts.append(f"Meslek: {profile.occupation}")
    if profile.goals:        parts.append(f"Hedefler: {', '.join(profile.goals)}")
    if profile.career_stage: parts.append(f"Kariyer: {profile.career_stage}")
    return "\n".join(parts)


async def _generate_user_insights(user_id: int, profile_context: str):
    """Generate one insight per agent for a single user (async)."""
    db = SessionLocal()
    try:
        # Count existing unread insights — don't flood
        unread_count = (
            db.query(Insight)
            .filter(Insight.user_id == user_id, Insight.is_read == False)  # noqa: E712
            .count()
        )
        if unread_count >= settings.MAX_INSIGHTS_PER_AGENT * len(AgentRole):
            logger.info(f"User {user_id} already has {unread_count} unread insights — skipping")
            return

        expiry = datetime.now(timezone.utc) + timedelta(days=3)
        generated = 0

        for role, agent in INSIGHT_AGENTS.items():
            try:
                content = await agent.generate_insight(
                    user_id=user_id,
                    profile_context=profile_context,
                )
                if not content:
                    continue

                insight = Insight(
                    user_id=user_id,
                    agent_role=role,
                    title=INSIGHT_TITLES[role],
                    content=content,
                    insight_type="observation",
                    expires_at=expiry,
                )
                db.add(insight)
                generated += 1

            except Exception as e:
                logger.warning(f"Insight generation failed for role={role.value} user={user_id}: {e}")
                continue

        db.commit()
        logger.info(f"Generated {generated} insights for user {user_id}")

    finally:
        db.close()


@celery_app.task(name="app.tasks.insight_generator.generate_insights_for_all_users")
def generate_insights_for_all_users():
    """
    Celery Beat task: runs every 6 hours.
    Generates proactive insights for all active users.
    """
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.is_active == True).all()  # noqa: E712
        logger.info(f"Starting proactive insight generation for {len(users)} users")

        for user in users:
            profile = db.query(UserProfile).filter(
                UserProfile.user_id == user.id
            ).first()
            profile_context = _build_profile_context(profile)

            try:
                asyncio.run(_generate_user_insights(user.id, profile_context))
            except Exception as e:
                logger.warning(f"Failed insight generation for user {user.id}: {e}")
                continue

    finally:
        db.close()

    return {"status": "completed", "timestamp": datetime.now(timezone.utc).isoformat()}


@celery_app.task(name="app.tasks.insight_generator.generate_insights_for_user")
def generate_insights_for_user(user_id: int):
    """On-demand insight generation for a single user."""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"status": "error", "detail": "User not found"}
        profile = db.query(UserProfile).filter(UserProfile.user_id == user_id).first()
        profile_context = _build_profile_context(profile)
    finally:
        db.close()

    asyncio.run(_generate_user_insights(user_id, profile_context))
    return {"status": "completed", "user_id": user_id}
