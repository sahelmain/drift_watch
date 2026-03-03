from __future__ import annotations

import asyncio
import logging
import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AlertConfig, AlertEvent, TestRun

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BACKOFF = 2


class AlertService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def check_and_alert(self, run: TestRun) -> list[AlertEvent]:
        configs = (
            await self.db.execute(
                select(AlertConfig).where(
                    AlertConfig.org_id == run.org_id,
                    AlertConfig.enabled.is_(True),
                    (AlertConfig.suite_id == run.suite_id) | (AlertConfig.suite_id.is_(None)),
                )
            )
        ).scalars().all()

        events: list[AlertEvent] = []
        for cfg in configs:
            triggered = self._evaluate(cfg, run)
            if not triggered:
                continue

            message = (
                f"[DriftWatch] Alert: {cfg.threshold_metric} "
                f"{'below' if run.pass_rate is not None and run.pass_rate < cfg.threshold_value else 'triggered'} "
                f"threshold {cfg.threshold_value} — "
                f"Suite run {run.id} pass_rate={run.pass_rate}"
            )

            sent = await self._dispatch(cfg.channel, cfg.destination, message)
            event = AlertEvent(
                alert_config_id=cfg.id,
                run_id=run.id,
                channel=cfg.channel,
                message=message,
                status="sent" if sent else "failed",
            )
            self.db.add(event)
            events.append(event)

        await self.db.flush()
        return events

    @staticmethod
    def _evaluate(cfg: AlertConfig, run: TestRun) -> bool:
        metric_value: float | None = None
        if cfg.threshold_metric == "pass_rate":
            metric_value = run.pass_rate
        elif cfg.threshold_metric == "total_tests":
            metric_value = float(run.total_tests) if run.total_tests is not None else None

        if metric_value is None:
            return False
        return metric_value < cfg.threshold_value

    async def _dispatch(self, channel: str, destination: str, message: str) -> bool:
        dispatch_map = {
            "slack": self.send_slack,
            "email": self.send_email,
            "pagerduty": self.send_pagerduty,
            "jira": self.send_jira,
        }
        handler = dispatch_map.get(channel)
        if handler is None:
            logger.warning("Unknown alert channel: %s", channel)
            return False

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                await handler(destination, message)
                return True
            except Exception:
                logger.exception("Alert dispatch attempt %d/%d failed (%s)", attempt, MAX_RETRIES, channel)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_BACKOFF ** attempt)
        return False

    @staticmethod
    async def send_slack(webhook_url: str, message: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook_url, json={"text": message})
            resp.raise_for_status()

    @staticmethod
    async def send_email(to: str, subject_and_body: str) -> None:
        import aiosmtplib
        from email.message import EmailMessage

        msg = EmailMessage()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg["Subject"] = "DriftWatch Alert"
        msg.set_content(subject_and_body)

        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASSWORD or None,
            start_tls=True,
        )

    @staticmethod
    async def send_pagerduty(service_id: str, message: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://events.pagerduty.com/v2/enqueue",
                json={
                    "routing_key": settings.PAGERDUTY_API_KEY,
                    "event_action": "trigger",
                    "payload": {
                        "summary": message,
                        "severity": "critical",
                        "source": "driftwatch",
                        "custom_details": {"service_id": service_id},
                    },
                },
            )
            resp.raise_for_status()

    @staticmethod
    async def send_jira(project: str, description: str) -> None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.JIRA_URL}/rest/api/3/issue",
                auth=(settings.JIRA_USER, settings.JIRA_TOKEN),
                json={
                    "fields": {
                        "project": {"key": project or settings.JIRA_PROJECT},
                        "summary": "DriftWatch Alert",
                        "description": {
                            "type": "doc",
                            "version": 1,
                            "content": [
                                {
                                    "type": "paragraph",
                                    "content": [{"type": "text", "text": description}],
                                }
                            ],
                        },
                        "issuetype": {"name": "Bug"},
                    }
                },
            )
            resp.raise_for_status()
