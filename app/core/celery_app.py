"""
Celery Application Factory
───────────────────────────
Background task processing for proactive insight generation.
Broker: Redis    Backend: Redis
"""

from celery import Celery
from celery.schedules import crontab
from app.core.config import settings


def create_celery_app() -> Celery:
    app = Celery(
        "innercircle",
        broker=settings.CELERY_BROKER_URL,
        backend=settings.CELERY_RESULT_BACKEND,
        include=["app.tasks.insight_generator"],
    )

    app.conf.update(
        # Serialization
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        # Timezone
        timezone="UTC",
        enable_utc=True,
        # Performance
        worker_prefetch_multiplier=1,
        task_acks_late=True,
        # Beat schedule — proactive insight generation
        beat_schedule={
            "generate-insights-all-users": {
                "task": "app.tasks.insight_generator.generate_insights_for_all_users",
                "schedule": crontab(
                    minute=0,
                    hour=f"*/{settings.INSIGHT_GENERATION_INTERVAL_HOURS}",
                ),
                "kwargs": {},
            },
        },
    )

    return app


celery_app = create_celery_app()
