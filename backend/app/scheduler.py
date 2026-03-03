from __future__ import annotations

import logging
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select

from app.database import async_session
from app.models import TestSuite

logger = logging.getLogger("driftwatch.scheduler")

scheduler = AsyncIOScheduler()


async def _trigger_suite_run(suite_id: str) -> None:
    """Run a suite — dispatches to Celery if available, else runs in-process."""
    try:
        from worker.runner import execute_run
        execute_run.delay(suite_id)
        logger.info("Dispatched scheduled run for suite %s via Celery", suite_id)
        return
    except Exception:
        pass

    from app.services.runs import RunService
    async with async_session() as db:
        svc = RunService(db)
        suite = (await db.execute(select(TestSuite).where(TestSuite.id == uuid.UUID(suite_id)))).scalar_one_or_none()
        if suite is None:
            logger.warning("Suite %s not found for scheduled run", suite_id)
            return
        await svc.create_run(suite.id, suite.org_id, trigger="scheduled")
        await db.commit()
        logger.info("In-process scheduled run created for suite %s", suite_id)


async def load_scheduled_suites() -> None:
    async with async_session() as db:
        result = await db.execute(
            select(TestSuite).where(
                TestSuite.is_active.is_(True),
                TestSuite.schedule_cron.isnot(None),
            )
        )
        suites = result.scalars().all()

    for suite in suites:
        add_suite_job(str(suite.id), suite.schedule_cron)

    logger.info("Loaded %d scheduled suites", len(suites))


def add_suite_job(suite_id: str, cron_expr: str) -> None:
    job_id = f"suite_{suite_id}"
    try:
        trigger = CronTrigger.from_crontab(cron_expr)
    except ValueError:
        logger.error("Invalid cron expression '%s' for suite %s", cron_expr, suite_id)
        return

    if scheduler.get_job(job_id):
        scheduler.reschedule_job(job_id, trigger=trigger)
    else:
        scheduler.add_job(
            _trigger_suite_run,
            trigger=trigger,
            id=job_id,
            args=[suite_id],
            replace_existing=True,
        )


def remove_suite_job(suite_id: str) -> None:
    job_id = f"suite_{suite_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)


def update_suite_job(suite_id: str, cron_expr: str | None) -> None:
    if cron_expr is None:
        remove_suite_job(suite_id)
    else:
        add_suite_job(suite_id, cron_expr)
