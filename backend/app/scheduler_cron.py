"""
Render cron job entry point.

Runs once per invocation, checks for suites with active cron schedules,
and dispatches any that are due. Designed as a run-and-exit script for
platforms that manage scheduling externally (Render Cron Jobs, etc).
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.config import settings
from app.database import async_session, create_tables
from app.models import TestSuite
from app.sentry_setup import init_sentry
from app.services.runs import RunService

init_sentry()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
logger = logging.getLogger("driftwatch.cron")


async def main() -> None:
    import app.models  # noqa: F401

    if settings.AUTO_CREATE_SCHEMA:
        await create_tables()
        logger.info("Schema auto-create enabled for cron")
    else:
        logger.info("Schema auto-create disabled for cron")

    async with async_session() as db:
        result = await db.execute(
            select(TestSuite).where(
                TestSuite.is_active.is_(True),
                TestSuite.schedule_cron.isnot(None),
            )
        )
        suites = result.scalars().all()

        if not suites:
            logger.info("No scheduled suites found")
            return

        svc = RunService(db)
        for suite in suites:
            try:
                await svc.create_run(
                    suite.id,
                    suite.org_id,
                    trigger="scheduled",
                )
                logger.info("Created scheduled run for suite %s", suite.id)
            except Exception:
                logger.exception("Failed to create run for suite %s", suite.id)

        await db.commit()
        logger.info("Cron tick complete — processed %d suites", len(suites))


if __name__ == "__main__":
    asyncio.run(main())
