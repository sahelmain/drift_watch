from __future__ import annotations

import json
import math
import re
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from prometheus_client import generate_latest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import Response

from app.config import settings
from app.database import async_session, get_db
from app.models import (
    AlertConfig,
    AuditLog,
    Dataset,
    Organization,
    Policy,
    TestRun,
    TestSuite,
    User,
)
from app.schemas import (
    AlertConfigCreate,
    AlertConfigResponse,
    AlertConfigUpdate,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyResponse,
    AuditLogResponse,
    CICheckRequest,
    CICheckResponse,
    ClientDriftPointResponse,
    ClientTestRunDetailResponse,
    ClientTestRunResponse,
    DatasetCreate,
    DatasetDetail,
    DatasetResponse,
    LoginRequest,
    MemberAdd,
    OrgCreate,
    OrgResponse,
    OrgSettingsApiKey,
    OrgSettingsMember,
    OrgSettingsOrg,
    OrgSettingsResponse,
    OrgSettingsUpdate,
    OrgSettingsUsage,
    PaginatedResponse,
    PolicyCreate,
    PolicyResponse,
    PolicyUpdate,
    RegisterRequest,
    TestSuiteCreate,
    TestSuiteResponse,
    TestSuiteUpdate,
    Token,
    UserResponse,
    WebhookTestRequest,
)
from app.services.alerts import AlertService
from app.services.auth import (
    create_access_token,
    create_api_key,
    get_current_user,
    hash_password,
    require_role,
    verify_password,
)
from app.services.billing import BillingService
from app.services.run_executor import execute_run as execute_run_inline
from app.services.runs import RunService

router = APIRouter(prefix="/api")


def _paginate(items: list, total: int, page: int, limit: int) -> PaginatedResponse:
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        limit=limit,
        pages=max(1, math.ceil(total / limit)),
    )


def _stringify_json_value(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _client_run_status(run: TestRun) -> str:
    if run.status == "completed":
        total = run.total_tests or 0
        passed = run.passed_tests or 0
        return "passed" if total == 0 or passed == total else "failed"
    if run.status == "failed":
        return "error"
    return run.status


def _duration_ms(run: TestRun) -> float | None:
    if run.started_at is None or run.completed_at is None:
        return None
    return max((run.completed_at - run.started_at).total_seconds() * 1000, 0.0)


def _serialize_run(run: TestRun, include_results: bool = False) -> ClientTestRunResponse | ClientTestRunDetailResponse:
    suite = run.__dict__.get("suite")
    total_tests = run.total_tests or 0
    passed_tests = run.passed_tests or 0
    payload = {
        "id": run.id,
        "suite_id": run.suite_id,
        "suite_name": suite.name if suite is not None else None,
        "status": _client_run_status(run),
        "trigger": run.trigger,
        "pass_rate": run.pass_rate,
        "total_tests": total_tests,
        "passed_tests": passed_tests,
        "failed_tests": max(total_tests - passed_tests, 0),
        "duration_ms": _duration_ms(run),
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "created_at": run.started_at or run.completed_at,
    }
    if not include_results:
        return ClientTestRunResponse(**payload)

    return ClientTestRunDetailResponse(
        **payload,
        results=[
            {
                "id": result.id,
                "run_id": result.run_id,
                "test_name": result.test_name,
                "model": result.model,
                "passed": result.passed,
                "output": result.output,
                "latency_ms": result.latency_ms,
                "tokens_used": result.token_count or 0,
                "cost": result.cost,
                "assertions": [
                    {
                        "name": assertion.assertion_type,
                        "type": assertion.assertion_type,
                        "passed": assertion.passed,
                        "expected": _stringify_json_value(assertion.expected),
                        "actual": _stringify_json_value(assertion.actual),
                        "message": assertion.message,
                    }
                    for assertion in result.assertion_results
                ],
            }
            for result in run.results
        ],
    )


def _serialize_timeline(runs: list[TestRun]) -> list[ClientDriftPointResponse]:
    completed_runs = sorted(
        [run for run in runs if run.completed_at is not None and run.pass_rate is not None],
        key=lambda run: run.completed_at or run.started_at,
    )
    timeline: list[ClientDriftPointResponse] = []
    previous_fraction: float | None = None
    for run in completed_runs:
        pass_rate_fraction = (run.pass_rate or 0.0) / 100.0
        total_tests = run.total_tests or 0
        passed_tests = run.passed_tests or 0
        drift_score = 0.0 if previous_fraction is None else abs(pass_rate_fraction - previous_fraction)
        timeline.append(
            ClientDriftPointResponse(
                date=run.completed_at or run.started_at,
                pass_rate=pass_rate_fraction,
                drift_score=drift_score,
                run_id=run.id,
                total_tests=total_tests,
                failed_tests=max(total_tests - passed_tests, 0),
            )
        )
        previous_fraction = pass_rate_fraction
    return timeline


# --------------------------------------------------------------------------- #
# Sentry verification (remove after confirming events appear)
# --------------------------------------------------------------------------- #


@router.get("/sentry-test")
async def sentry_test():
    raise RuntimeError("Sentry backend test — safe to ignore")


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #


@router.post("/auth/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    exists = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=400, detail="Email already registered")

    slug = re.sub(r"[^a-z0-9]+", "-", body.org_name.lower()).strip("-") or "org"
    org = Organization(name=body.org_name, slug=slug)
    db.add(org)
    await db.flush()

    user = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role="admin",
        org_id=org.id,
    )
    db.add(user)
    await db.flush()

    token = create_access_token({"sub": str(user.id)})
    user_resp = UserResponse.model_validate(user)
    return Token(access_token=token, user=user_resp)


@router.post("/auth/login", response_model=Token)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")

    token = create_access_token({"sub": str(user.id)})
    user_resp = UserResponse.model_validate(user)
    return Token(access_token=token, user=user_resp)


@router.get("/auth/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)):
    return user


# --------------------------------------------------------------------------- #
# Orgs
# --------------------------------------------------------------------------- #


@router.post("/orgs", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_org(body: OrgCreate, user: User = Depends(require_role("admin")), db: AsyncSession = Depends(get_db)):
    org = Organization(name=body.name, slug=body.slug, plan=body.plan)
    db.add(org)
    await db.flush()
    return org


@router.get("/orgs/{org_id}", response_model=OrgResponse)
async def get_org(org_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org = (await db.execute(select(Organization).where(Organization.id == org_id))).scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.post("/orgs/{org_id}/members", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def add_member(
    org_id: uuid.UUID,
    body: MemberAdd,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    member = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        org_id=org_id,
    )
    db.add(member)
    await db.flush()
    return member


@router.get("/orgs/{org_id}/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    org_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.models import ApiKey

    rows = (await db.execute(select(ApiKey).where(ApiKey.org_id == org_id))).scalars().all()
    return rows


@router.post("/orgs/{org_id}/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def create_api_key_endpoint(
    org_id: uuid.UUID,
    body: ApiKeyCreate,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    api_key, raw_key = await create_api_key(db, org_id, body.name, body.scopes, body.expires_at)
    return ApiKeyCreated(
        id=api_key.id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        org_id=api_key.org_id,
        scopes=api_key.scopes,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        raw_key=raw_key,
    )


@router.delete("/orgs/{org_id}/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    org_id: uuid.UUID,
    key_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.models import ApiKey

    key = (await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.org_id == org_id))).scalar_one_or_none()
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    await db.delete(key)


# --------------------------------------------------------------------------- #
# Suites
# --------------------------------------------------------------------------- #


@router.get("/suites", response_model=PaginatedResponse)
async def list_suites(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(TestSuite).where(TestSuite.org_id == user.org_id, TestSuite.is_active.is_(True))
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        (await db.execute(base.order_by(TestSuite.created_at.desc()).offset((page - 1) * limit).limit(limit)))
        .scalars()
        .all()
    )
    items = [TestSuiteResponse.model_validate(r) for r in rows]
    return _paginate(items, total, page, limit)


@router.post("/suites", response_model=TestSuiteResponse, status_code=status.HTTP_201_CREATED)
async def create_suite(
    body: TestSuiteCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    billing = BillingService(db)
    if not await billing.check_quota(user.org_id, "suites"):
        raise HTTPException(status_code=402, detail="Suite limit reached for your plan")

    suite = TestSuite(
        name=body.name,
        description=body.description,
        yaml_content=body.yaml_content,
        org_id=user.org_id,
        schedule_cron=body.schedule_cron,
    )
    db.add(suite)
    await db.flush()
    return suite


@router.get("/suites/{suite_id}", response_model=TestSuiteResponse)
async def get_suite(suite_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    suite = (await db.execute(select(TestSuite).where(TestSuite.id == suite_id))).scalar_one_or_none()
    if suite is None:
        raise HTTPException(status_code=404, detail="Suite not found")
    return suite


@router.put("/suites/{suite_id}", response_model=TestSuiteResponse)
async def update_suite(
    suite_id: uuid.UUID,
    body: TestSuiteUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    suite = (await db.execute(select(TestSuite).where(TestSuite.id == suite_id))).scalar_one_or_none()
    if suite is None:
        raise HTTPException(status_code=404, detail="Suite not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(suite, field, value)
    await db.flush()
    await db.refresh(suite)
    return suite


@router.delete("/suites/{suite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_suite(suite_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    suite = (await db.execute(select(TestSuite).where(TestSuite.id == suite_id))).scalar_one_or_none()
    if suite is None:
        raise HTTPException(status_code=404, detail="Suite not found")
    suite.is_active = False
    await db.flush()


# --------------------------------------------------------------------------- #
# Runs
# --------------------------------------------------------------------------- #


@router.post("/suites/{suite_id}/run", response_model=ClientTestRunResponse, status_code=status.HTTP_201_CREATED)
async def trigger_run(
    suite_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    billing = BillingService(db)
    if not await billing.check_quota(user.org_id, "runs"):
        raise HTTPException(status_code=402, detail="Run limit reached for your plan")

    svc = RunService(db)
    run = await svc.create_run(
        suite_id,
        user.org_id,
        trigger="manual",
        dispatch_to_worker=not settings.ENABLE_INLINE_RUNS,
    )
    if not settings.ENABLE_INLINE_RUNS:
        return _serialize_run(run)

    await db.commit()
    await execute_run_inline(run.id)

    async with async_session() as refreshed_db:
        refreshed = await RunService(refreshed_db).get_run(run.id)
        if refreshed is None:
            raise HTTPException(status_code=500, detail="Run execution failed to reload")
        return _serialize_run(refreshed)


@router.get("/runs", response_model=PaginatedResponse)
async def list_runs(
    suite_id: uuid.UUID | None = None,
    run_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = RunService(db)
    rows, _ = await svc.list_runs(user.org_id, suite_id, None, 1, 1000)
    items = [_serialize_run(run) for run in rows]
    if run_status:
        items = [item for item in items if item.status == run_status]
    total = len(items)
    start_idx = (page - 1) * limit
    items = items[start_idx : start_idx + limit]
    return _paginate(items, total, page, limit)


@router.get("/runs/{run_id}", response_model=ClientTestRunDetailResponse)
async def get_run(run_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    svc = RunService(db)
    run = await svc.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return _serialize_run(run, include_results=True)


@router.get("/drift/{suite_id}", response_model=list[ClientDriftPointResponse])
async def get_drift(suite_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    svc = RunService(db)
    rows, _ = await svc.list_runs(user.org_id, suite_id, None, 1, 1000)
    return _serialize_timeline(rows)


# --------------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------------- #


@router.get("/alerts", response_model=list[AlertConfigResponse])
async def list_alerts(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(AlertConfig).where(AlertConfig.org_id == user.org_id))).scalars().all()
    return rows


@router.post("/alerts", response_model=AlertConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_alert(
    body: AlertConfigCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = AlertConfig(
        suite_id=body.suite_id,
        org_id=user.org_id,
        channel=body.channel,
        destination=body.destination,
        threshold_metric=body.threshold_metric,
        threshold_value=body.threshold_value,
        enabled=body.enabled,
    )
    db.add(cfg)
    await db.flush()
    return cfg


@router.put("/alerts/{alert_id}", response_model=AlertConfigResponse)
async def update_alert(
    alert_id: uuid.UUID,
    body: AlertConfigUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    cfg = (await db.execute(select(AlertConfig).where(AlertConfig.id == alert_id))).scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail="Alert config not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(cfg, field, value)
    await db.flush()
    return cfg


@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(alert_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    cfg = (await db.execute(select(AlertConfig).where(AlertConfig.id == alert_id))).scalar_one_or_none()
    if cfg is None:
        raise HTTPException(status_code=404, detail="Alert config not found")
    await db.delete(cfg)


@router.post("/webhooks/test", status_code=status.HTTP_200_OK)
async def test_webhook(
    body: WebhookTestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    svc = AlertService(db)
    dispatch_map = {
        "slack": lambda: svc.send_slack(body.destination, "DriftWatch test alert"),
        "email": lambda: svc.send_email(body.destination, "DriftWatch test alert"),
        "pagerduty": lambda: svc.send_pagerduty(body.destination, "DriftWatch test alert"),
        "jira": lambda: svc.send_jira(body.destination, "DriftWatch test alert"),
    }
    handler = dispatch_map.get(body.channel)
    if handler is None:
        raise HTTPException(status_code=400, detail="Unknown channel")
    try:
        await handler()
        return {"status": "sent"}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))


# --------------------------------------------------------------------------- #
# Policies
# --------------------------------------------------------------------------- #


@router.get("/policies", response_model=list[PolicyResponse])
async def list_policies(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Policy).where(Policy.org_id == user.org_id))).scalars().all()
    return rows


@router.post("/policies", response_model=PolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_policy(body: PolicyCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    p = Policy(
        org_id=user.org_id,
        suite_id=body.suite_id,
        name=body.name,
        metric=body.metric,
        operator=body.operator,
        threshold=body.threshold,
        action=body.action,
        enabled=body.enabled,
    )
    db.add(p)
    await db.flush()
    return p


@router.put("/policies/{policy_id}", response_model=PolicyResponse)
async def update_policy(
    policy_id: uuid.UUID,
    body: PolicyUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    p = (await db.execute(select(Policy).where(Policy.id == policy_id))).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(p, field, value)
    await db.flush()
    return p


@router.delete("/policies/{policy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_policy(
    policy_id: uuid.UUID, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    p = (await db.execute(select(Policy).where(Policy.id == policy_id))).scalar_one_or_none()
    if p is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    await db.delete(p)


# --------------------------------------------------------------------------- #
# Datasets
# --------------------------------------------------------------------------- #


@router.get("/datasets", response_model=list[DatasetResponse])
async def list_datasets(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Dataset).where(Dataset.org_id == user.org_id))).scalars().all()
    return rows


@router.post("/datasets", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    body: DatasetCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    ds = Dataset(
        org_id=user.org_id,
        name=body.name,
        description=body.description,
        content=body.content,
        row_count=body.row_count,
    )
    db.add(ds)
    await db.flush()
    return ds


@router.get("/datasets/{dataset_id}", response_model=DatasetDetail)
async def get_dataset(
    dataset_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ds = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if ds is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return ds


# --------------------------------------------------------------------------- #
# CI Check
# --------------------------------------------------------------------------- #


@router.post("/ci/check", response_model=CICheckResponse)
async def ci_check(body: CICheckRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    latest_run = (
        await db.execute(
            select(TestRun)
            .where(TestRun.suite_id == body.suite_id, TestRun.status == "completed")
            .order_by(TestRun.completed_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()

    if latest_run is None:
        return CICheckResponse(
            passed=False,
            suite_id=body.suite_id,
            commit_sha=body.commit_sha,
            message="No completed runs found",
        )

    policies = (
        (
            await db.execute(
                select(Policy).where(
                    Policy.enabled.is_(True),
                    (Policy.suite_id == body.suite_id) | (Policy.suite_id.is_(None)),
                    Policy.org_id == user.org_id,
                )
            )
        )
        .scalars()
        .all()
    )

    passed = True
    messages: list[str] = []
    for policy in policies:
        if policy.action != "block":
            continue
        metric_val = latest_run.pass_rate if policy.metric == "pass_rate" else None
        if metric_val is None:
            continue
        ops = {
            "lt": metric_val < policy.threshold,
            "le": metric_val <= policy.threshold,
            "gt": metric_val > policy.threshold,
            "ge": metric_val >= policy.threshold,
            "eq": metric_val == policy.threshold,
            "ne": metric_val != policy.threshold,
        }
        if ops.get(policy.operator, False):
            passed = False
            messages.append(f"Policy '{policy.name}' violated: {policy.metric} {policy.operator} {policy.threshold}")

    return CICheckResponse(
        passed=passed,
        suite_id=body.suite_id,
        commit_sha=body.commit_sha,
        run_id=latest_run.id,
        pass_rate=latest_run.pass_rate,
        message="; ".join(messages) if messages else "All policies passed",
    )


# --------------------------------------------------------------------------- #
# Audit Log
# --------------------------------------------------------------------------- #


@router.get("/audit-log", response_model=PaginatedResponse)
async def list_audit_log(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(AuditLog).where(AuditLog.org_id == user.org_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    rows = (
        (await db.execute(base.order_by(AuditLog.timestamp.desc()).offset((page - 1) * limit).limit(limit)))
        .scalars()
        .all()
    )
    items = [AuditLogResponse.model_validate(r) for r in rows]
    return _paginate(items, total, page, limit)


# --------------------------------------------------------------------------- #
# Metrics (Prometheus)
# --------------------------------------------------------------------------- #


@router.get("/metrics")
async def prometheus_metrics():
    return Response(content=generate_latest(), media_type="text/plain; version=0.0.4; charset=utf-8")


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #


async def _build_settings_response(org: Organization, db: AsyncSession) -> OrgSettingsResponse:
    from datetime import datetime, timezone

    from app.models import ApiKey as ApiKeyModel

    members_rows = (await db.execute(select(User).where(User.org_id == org.id))).scalars().all()
    keys_rows = (await db.execute(select(ApiKeyModel).where(ApiKeyModel.org_id == org.id))).scalars().all()

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    runs_count = (
        await db.execute(
            select(func.count()).select_from(
                select(TestRun)
                .where(
                    TestRun.org_id == org.id,
                    TestRun.started_at >= month_start,
                )
                .subquery()
            )
        )
    ).scalar() or 0

    suites_count = (
        await db.execute(
            select(func.count()).select_from(
                select(TestSuite)
                .where(
                    TestSuite.org_id == org.id,
                    TestSuite.is_active.is_(True),
                )
                .subquery()
            )
        )
    ).scalar() or 0

    plan_limits = {"free": 1000, "pro": 10000, "enterprise": 100000}

    return OrgSettingsResponse(
        org=OrgSettingsOrg(
            id=org.id,
            name=org.name,
            slug=org.slug,
            plan=org.plan,
            created_at=org.created_at,
        ),
        members=[OrgSettingsMember(id=m.id, email=m.email, role=m.role, created_at=m.created_at) for m in members_rows],
        api_keys=[
            OrgSettingsApiKey(
                id=k.id,
                prefix=k.key_prefix,
                name=k.name,
                created_at=k.created_at,
                last_used_at=k.last_used_at,
            )
            for k in keys_rows
        ],
        usage=OrgSettingsUsage(
            runs_this_month=runs_count,
            suites_count=suites_count,
            plan_limit=plan_limits.get(org.plan, 1000),
        ),
    )


@router.get("/settings", response_model=OrgSettingsResponse)
async def get_settings(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    org = (await db.execute(select(Organization).where(Organization.id == user.org_id))).scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return await _build_settings_response(org, db)


@router.put("/settings", response_model=OrgSettingsResponse)
async def update_settings(
    body: OrgSettingsUpdate,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    org = (await db.execute(select(Organization).where(Organization.id == user.org_id))).scalar_one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if body.org is not None:
        if body.org.name:
            org.name = body.org.name
        if body.org.slug:
            org.slug = body.org.slug
    await db.flush()
    return await _build_settings_response(org, db)


@router.post("/settings/api-keys", response_model=ApiKeyCreated, status_code=status.HTTP_201_CREATED)
async def settings_create_api_key(
    body: ApiKeyCreate,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    api_key, raw_key = await create_api_key(db, user.org_id, body.name, body.scopes, body.expires_at)
    return ApiKeyCreated(
        id=api_key.id,
        key_prefix=api_key.key_prefix,
        name=api_key.name,
        org_id=api_key.org_id,
        scopes=api_key.scopes,
        created_at=api_key.created_at,
        expires_at=api_key.expires_at,
        last_used_at=api_key.last_used_at,
        raw_key=raw_key,
    )


@router.delete("/settings/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def settings_revoke_api_key(
    key_id: uuid.UUID,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    from app.models import ApiKey as ApiKeyModel

    key = (
        await db.execute(select(ApiKeyModel).where(ApiKeyModel.id == key_id, ApiKeyModel.org_id == user.org_id))
    ).scalar_one_or_none()
    if key is None:
        raise HTTPException(status_code=404, detail="API key not found")
    await db.delete(key)


@router.post("/settings/members", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def settings_add_member(
    body: MemberAdd,
    user: User = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    member = User(
        email=body.email,
        password_hash=hash_password(body.password),
        role=body.role,
        org_id=user.org_id,
    )
    db.add(member)
    await db.flush()
    return member
