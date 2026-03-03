from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from celery import Celery

from app.config import settings

logger = logging.getLogger("driftwatch.worker")

celery_app = Celery(
    "driftwatch",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=4,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


def _run_async(coro):
    """Run an async coroutine in a fresh event loop (Celery workers are sync)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=10,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=120,
    acks_late=True,
    name="worker.execute_run",
)
def execute_run(self, run_id: str) -> dict:
    return _run_async(_execute_run_async(run_id))


async def _execute_run_async(run_id: str) -> dict:
    from app.database import async_session
    from app.models import TestRun, TestSuite
    from app.services.alerts import AlertService
    from app.services.runs import RunService
    from sqlalchemy import select

    async with async_session() as db:
        run = (await db.execute(
            select(TestRun).where(TestRun.id == uuid.UUID(run_id))
        )).scalar_one_or_none()

        if run is None:
            logger.error("Run %s not found", run_id)
            return {"status": "not_found"}

        if run.status == "completed":
            logger.info("Run %s already completed — skipping", run_id)
            return {"status": "already_completed"}

        run.status = "running"
        run.started_at = datetime.now(UTC)
        await db.flush()

        suite = (await db.execute(
            select(TestSuite).where(TestSuite.id == run.suite_id)
        )).scalar_one_or_none()

        if suite is None:
            run.status = "failed"
            await db.commit()
            return {"status": "suite_not_found"}

        try:
            results = _evaluate_suite(suite)
        except Exception:
            logger.exception("Evaluation failed for run %s", run_id)
            run.status = "failed"
            run.completed_at = datetime.now(UTC)
            await db.commit()
            return {"status": "evaluation_failed"}

        svc = RunService(db)
        await svc.save_results(run.id, results)
        await svc.compute_drift(suite.id)

        alert_svc = AlertService(db)
        refreshed = await svc.get_run(run.id)
        if refreshed:
            await alert_svc.check_and_alert(refreshed)

        await db.commit()
        logger.info("Run %s completed — %d tests", run_id, len(results))
        return {"status": "completed", "tests": len(results)}


def _evaluate_suite(suite) -> list[dict]:
    """
    Placeholder evaluation engine.

    In production this would parse the suite YAML, iterate test cases,
    call LLM providers, run assertions, and return structured results.
    """
    import yaml

    tests: list[dict] = []
    if not suite.yaml_content:
        return tests

    try:
        spec = yaml.safe_load(suite.yaml_content)
    except Exception:
        logger.warning("Failed to parse YAML for suite %s", suite.id)
        return tests

    if not isinstance(spec, dict):
        return tests

    for tc in spec.get("tests", []):
        tests.append({
            "test_name": tc.get("name", "unnamed"),
            "prompt": tc.get("prompt", ""),
            "model": tc.get("model", "gpt-4"),
            "output": "[placeholder output]",
            "passed": True,
            "latency_ms": 0.0,
            "token_count": 0,
            "cost": 0.0,
            "assertions": [
                {
                    "assertion_type": a.get("type", "contains"),
                    "passed": True,
                    "expected": a.get("expected"),
                    "actual": None,
                    "score": 1.0,
                    "message": "Placeholder assertion",
                }
                for a in tc.get("assertions", [])
            ],
        })

    return tests
