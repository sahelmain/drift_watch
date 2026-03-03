from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Organization, TestRun, TestSuite

PLAN_LIMITS: dict[str, dict[str, int | float]] = {
    "free": {"runs_per_month": 100, "max_suites": 1},
    "pro": {"runs_per_month": 10_000, "max_suites": 50},
    "enterprise": {"runs_per_month": float("inf"), "max_suites": float("inf")},
}


class BillingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record_usage(self, org_id: uuid.UUID, metric: str, amount: int = 1) -> None:
        """No-op placeholder — usage is derived from actual run/suite counts."""
        pass

    async def get_usage(
        self,
        org_id: uuid.UUID,
        period: str = "current_month",
    ) -> dict[str, int]:
        start = self._period_start(period)

        runs_count = (
            await self.db.execute(
                select(func.count(TestRun.id)).where(
                    TestRun.org_id == org_id,
                    TestRun.started_at >= start,
                )
            )
        ).scalar() or 0

        suites_count = (
            await self.db.execute(
                select(func.count(TestSuite.id)).where(
                    TestSuite.org_id == org_id,
                    TestSuite.is_active.is_(True),
                )
            )
        ).scalar() or 0

        return {"runs": runs_count, "suites": suites_count}

    async def check_quota(self, org_id: uuid.UUID, metric: str) -> bool:
        """Return True if the org is within its plan limits for *metric*."""
        org = (
            await self.db.execute(select(Organization).where(Organization.id == org_id))
        ).scalar_one_or_none()

        if org is None:
            return False

        limits = PLAN_LIMITS.get(org.plan, PLAN_LIMITS["free"])
        usage = await self.get_usage(org_id)

        if metric == "runs":
            return usage["runs"] < limits["runs_per_month"]
        if metric == "suites":
            return usage["suites"] < limits["max_suites"]

        return True

    @staticmethod
    def _period_start(period: str) -> datetime:
        now = datetime.now(UTC)
        if period == "current_month":
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return now - timedelta(days=30)
