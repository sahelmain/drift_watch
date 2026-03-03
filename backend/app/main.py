from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings

logger = logging.getLogger("driftwatch")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting DriftWatch API")

    if settings.AUTO_CREATE_SCHEMA:
        from app.database import create_tables
        import app.models  # noqa: F401 — ensure models registered

        await create_tables()
        logger.info("Schema auto-create enabled")
        logger.info("Database tables ready")
    else:
        logger.info("Schema auto-create disabled")

    if settings.ENABLE_INLINE_SCHEDULER:
        try:
            from app.scheduler import scheduler, load_scheduled_suites

            await load_scheduled_suites()
            scheduler.start()
            logger.info("Inline scheduler enabled")
            logger.info("Scheduler started")
        except Exception:
            logger.warning(
                "Scheduler failed to start — running without scheduled jobs",
                exc_info=True,
            )
    else:
        logger.info("Inline scheduler disabled")

    yield

    if settings.ENABLE_INLINE_SCHEDULER:
        try:
            from app.scheduler import scheduler

            scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")
        except Exception:
            pass


def create_app() -> FastAPI:
    app = FastAPI(
        title="DriftWatch",
        description="LLM evaluation and drift monitoring platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        logger.warning("OpenTelemetry instrumentation unavailable", exc_info=True)

    from app.api.routes import router
    app.include_router(router)

    @app.get("/api/health")
    async def health_check():
        checks: dict[str, str] = {}
        try:
            from app.database import engine
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:
            checks["database"] = f"error: {exc}"

        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            await r.ping()
            await r.aclose()
            checks["redis"] = "ok"
        except Exception:
            checks["redis"] = "unavailable"

        overall = "ok" if checks.get("database") == "ok" else "degraded"
        return {"status": overall, "checks": checks}

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

    return app


app = create_app()
