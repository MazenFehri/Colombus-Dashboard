import logging
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.database import SessionLocal
from app.config import settings
from app import models
from app.services import digest_builder, email_service

logger = logging.getLogger("colombus.scheduler")
_scheduler: BackgroundScheduler | None = None


def run_digest_job() -> None:
    """Build today's digest once and email every opted-in user.
    Per-user failures are logged and skipped so the batch always completes."""
    db = SessionLocal()
    try:
        users = db.query(models.User).filter_by(digest_enabled=True, is_active=True).all()
        if not users:
            return
        subject, html = digest_builder.build_digest_html(db, date.today())
        for user in users:
            try:
                email_service.send_email(user.email, subject, html)
            except Exception as exc:
                logger.warning("digest send failed for %s: %s", user.email, exc)
    finally:
        db.close()


def start_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = BackgroundScheduler(timezone=settings.digest_timezone)
    _scheduler.add_job(
        run_digest_job,
        CronTrigger(hour=settings.digest_hour, minute=0, timezone=settings.digest_timezone),
        id="daily_news_digest",
        replace_existing=True,
    )
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
