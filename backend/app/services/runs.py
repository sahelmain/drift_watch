from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    AssertionResult,
    DriftScore,
    TestResult,
    TestRun,
    TestSuite,
)


class RunService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_run(
        self,
        suite_id: uuid.UUID,
        org_id: uuid.UUID,
        trigger: str = "manual",
        metadata_: dict | None = None,
    ) -> TestRun:
        run = TestRun(
            suite_id=suite_id,
            org_id=org_id,
            status="pending",
            trigger=trigger,
            metadata_=metadata_,
        )
        self.db.add(run)
        await self.db.flush()

        self._dispatch_to_worker(run.id)
        return run

    async def get_run(self, run_id: uuid.UUID) -> TestRun | None:
        result = await self.db.execute(
            select(TestRun)
            .where(TestRun.id == run_id)
            .options(
                selectinload(TestRun.results).selectinload(TestResult.assertion_results),
            )
        )
        return result.scalar_one_or_none()

    async def list_runs(
        self,
        org_id: uuid.UUID,
        suite_id: uuid.UUID | None = None,
        status: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[TestRun], int]:
        q = select(TestRun).where(TestRun.org_id == org_id)
        count_q = select(func.count(TestRun.id)).where(TestRun.org_id == org_id)

        if suite_id:
            q = q.where(TestRun.suite_id == suite_id)
            count_q = count_q.where(TestRun.suite_id == suite_id)
        if status:
            q = q.where(TestRun.status == status)
            count_q = count_q.where(TestRun.status == status)

        total = (await self.db.execute(count_q)).scalar() or 0
        q = q.order_by(TestRun.started_at.desc()).offset((page - 1) * limit).limit(limit)
        rows = (await self.db.execute(q)).scalars().all()
        return list(rows), total

    async def compute_drift(self, suite_id: uuid.UUID) -> list[DriftScore]:
        runs = (
            await self.db.execute(
                select(TestRun)
                .where(TestRun.suite_id == suite_id, TestRun.status == "completed")
                .order_by(TestRun.completed_at.asc())
            )
        ).scalars().all()

        scores: list[DriftScore] = []
        for run in runs:
            if run.pass_rate is not None:
                score = DriftScore(
                    suite_id=suite_id,
                    run_id=run.id,
                    metric="pass_rate",
                    value=run.pass_rate,
                    timestamp=run.completed_at or datetime.now(UTC),
                )
                self.db.add(score)
                scores.append(score)

        await self.db.flush()
        return scores

    async def get_drift_timeline(self, suite_id: uuid.UUID) -> list[DriftScore]:
        result = await self.db.execute(
            select(DriftScore)
            .where(DriftScore.suite_id == suite_id)
            .order_by(DriftScore.timestamp.asc())
        )
        return list(result.scalars().all())

    async def save_results(
        self,
        run_id: uuid.UUID,
        results: list[dict],
    ) -> None:
        run = await self.get_run(run_id)
        if run is None:
            return

        total = len(results)
        passed = 0

        for r in results:
            tr = TestResult(
                run_id=run_id,
                test_name=r["test_name"],
                prompt=r["prompt"],
                model=r["model"],
                output=r.get("output"),
                passed=r.get("passed", False),
                latency_ms=r.get("latency_ms"),
                token_count=r.get("token_count"),
                cost=r.get("cost"),
            )
            self.db.add(tr)
            await self.db.flush()

            if r.get("passed"):
                passed += 1

            for a in r.get("assertions", []):
                ar = AssertionResult(
                    result_id=tr.id,
                    assertion_type=a["assertion_type"],
                    passed=a.get("passed", False),
                    expected=a.get("expected"),
                    actual=a.get("actual"),
                    score=a.get("score"),
                    message=a.get("message"),
                )
                self.db.add(ar)

        run.total_tests = total
        run.passed_tests = passed
        run.pass_rate = (passed / total * 100) if total > 0 else 0.0
        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        await self.db.flush()

    @staticmethod
    def _dispatch_to_worker(run_id: uuid.UUID) -> None:
        try:
            from worker.runner import execute_run
            execute_run.delay(str(run_id))
        except Exception:
            pass
