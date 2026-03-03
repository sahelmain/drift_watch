from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, model_validator


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

class _OrmBase(BaseModel):
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Auth / Token
# ---------------------------------------------------------------------------

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse | None = None


class TokenPayload(BaseModel):
    sub: str
    exp: int | None = None


# ---------------------------------------------------------------------------
# Organization
# ---------------------------------------------------------------------------

class OrgCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9\-]+$")
    plan: str = "free"


class OrgUpdate(BaseModel):
    name: str | None = None
    plan: str | None = None


class OrgResponse(_OrmBase):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    created_at: datetime


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class UserCreate(BaseModel):
    email: str = Field(..., max_length=320)
    password: str = Field(..., min_length=8)
    role: str = "member"


class RegisterRequest(BaseModel):
    email: str = Field(..., max_length=320)
    password: str = Field(..., min_length=6)
    org_name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: str
    password: str


class UserResponse(_OrmBase):
    id: uuid.UUID
    email: str
    role: str
    org_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class MemberAdd(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    role: str = "member"


# ---------------------------------------------------------------------------
# API Key
# ---------------------------------------------------------------------------

class ApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    scopes: dict | None = None
    expires_at: datetime | None = None


class ApiKeyResponse(_OrmBase):
    id: uuid.UUID
    key_prefix: str
    name: str
    org_id: uuid.UUID
    scopes: dict | None
    created_at: datetime
    expires_at: datetime | None
    last_used_at: datetime | None


class ApiKeyCreated(ApiKeyResponse):
    """Returned only on creation — includes the raw key."""
    raw_key: str


# ---------------------------------------------------------------------------
# Test Suite
# ---------------------------------------------------------------------------

class TestSuiteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    yaml_content: str | None = None
    schedule_cron: str | None = None


class TestSuiteUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    yaml_content: str | None = None
    schedule_cron: str | None = None
    is_active: bool | None = None


class TestSuiteResponse(_OrmBase):
    id: uuid.UUID
    name: str
    description: str | None
    yaml_content: str | None
    org_id: uuid.UUID
    schedule_cron: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Test Run
# ---------------------------------------------------------------------------

class TestRunCreate(BaseModel):
    trigger: str = "manual"
    metadata_: dict | None = Field(None, alias="metadata")


class TestRunResponse(_OrmBase):
    id: uuid.UUID
    suite_id: uuid.UUID
    status: str
    trigger: str
    started_at: datetime | None
    completed_at: datetime | None
    pass_rate: float | None
    total_tests: int | None
    passed_tests: int | None
    metadata_: dict | None
    org_id: uuid.UUID


class TestRunDetail(TestRunResponse):
    results: list[TestResultResponse] = []


# ---------------------------------------------------------------------------
# Test Result
# ---------------------------------------------------------------------------

class TestResultResponse(_OrmBase):
    id: uuid.UUID
    run_id: uuid.UUID
    test_name: str
    prompt: str
    model: str
    output: str | None
    passed: bool
    latency_ms: float | None
    token_count: int | None
    cost: float | None
    assertion_results: list[AssertionResultResponse] = []


# ---------------------------------------------------------------------------
# Assertion Result
# ---------------------------------------------------------------------------

class AssertionResultResponse(_OrmBase):
    id: uuid.UUID
    result_id: uuid.UUID
    assertion_type: str
    passed: bool
    expected: dict | None
    actual: dict | None
    score: float | None
    message: str | None


# ---------------------------------------------------------------------------
# Drift Score
# ---------------------------------------------------------------------------

class DriftScoreResponse(_OrmBase):
    id: uuid.UUID
    suite_id: uuid.UUID
    run_id: uuid.UUID
    metric: str
    value: float
    timestamp: datetime


# ---------------------------------------------------------------------------
# Alert Config
# ---------------------------------------------------------------------------

class AlertConfigCreate(BaseModel):
    suite_id: uuid.UUID | None = None
    channel: str = Field(..., pattern=r"^(slack|email|pagerduty|jira)$")
    destination: str = Field(..., min_length=1)
    threshold_metric: str
    threshold_value: float
    enabled: bool = True


class AlertConfigUpdate(BaseModel):
    channel: str | None = None
    destination: str | None = None
    threshold_metric: str | None = None
    threshold_value: float | None = None
    enabled: bool | None = None


class AlertConfigResponse(_OrmBase):
    id: uuid.UUID
    suite_id: uuid.UUID | None
    org_id: uuid.UUID
    channel: str
    destination: str
    threshold_metric: str
    threshold_value: float
    enabled: bool
    created_at: datetime


class AlertEventResponse(_OrmBase):
    id: uuid.UUID
    alert_config_id: uuid.UUID
    run_id: uuid.UUID
    channel: str
    message: str
    status: str
    sent_at: datetime


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

class AuditLogResponse(_OrmBase):
    id: uuid.UUID
    org_id: uuid.UUID
    user_id: uuid.UUID
    action: str
    resource_type: str
    resource_id: str
    details: dict | None
    ip_address: str | None
    timestamp: datetime


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------

class PolicyCreate(BaseModel):
    suite_id: uuid.UUID | None = None
    name: str = Field(..., min_length=1, max_length=255)
    metric: str
    operator: str = Field(..., pattern=r"^(lt|le|gt|ge|eq|ne)$")
    threshold: float
    action: str = Field("notify", pattern=r"^(block|warn|notify)$")
    enabled: bool = True


class PolicyUpdate(BaseModel):
    name: str | None = None
    metric: str | None = None
    operator: str | None = None
    threshold: float | None = None
    action: str | None = None
    enabled: bool | None = None


class PolicyResponse(_OrmBase):
    id: uuid.UUID
    org_id: uuid.UUID
    suite_id: uuid.UUID | None
    name: str
    metric: str
    operator: str
    threshold: float
    action: str
    enabled: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    content: dict | list | None = None
    row_count: int = 0


class DatasetResponse(_OrmBase):
    id: uuid.UUID
    org_id: uuid.UUID
    name: str
    version: int
    description: str | None
    row_count: int
    created_at: datetime


class DatasetDetail(DatasetResponse):
    content: dict | list | None


# ---------------------------------------------------------------------------
# Prompt Version
# ---------------------------------------------------------------------------

class PromptVersionResponse(_OrmBase):
    id: uuid.UUID
    suite_id: uuid.UUID
    version: int
    yaml_content: str
    change_message: str | None
    created_by: uuid.UUID
    created_at: datetime


# ---------------------------------------------------------------------------
# CI Check
# ---------------------------------------------------------------------------

class CICheckRequest(BaseModel):
    suite_id: uuid.UUID
    commit_sha: str = Field(..., min_length=1)


class CICheckResponse(BaseModel):
    passed: bool
    suite_id: uuid.UUID
    commit_sha: str
    run_id: uuid.UUID | None = None
    pass_rate: float | None = None
    message: str = ""


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

class OrgSettingsOrg(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    plan: str
    created_at: datetime

class OrgSettingsApiKey(BaseModel):
    id: uuid.UUID
    prefix: str
    name: str
    created_at: datetime
    last_used_at: datetime | None = None

class OrgSettingsMember(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    created_at: datetime

class OrgSettingsUsage(BaseModel):
    runs_this_month: int = 0
    suites_count: int = 0
    plan_limit: int = 1000

class OrgSettingsResponse(BaseModel):
    org: OrgSettingsOrg
    members: list[OrgSettingsMember] = []
    api_keys: list[OrgSettingsApiKey] = []
    usage: OrgSettingsUsage = OrgSettingsUsage()

class OrgSettingsUpdate(BaseModel):
    org: OrgSettingsOrg | None = None

class OrgSettings(BaseModel):
    name: str | None = None
    plan: str | None = None
    slack_webhook_url: str | None = None


# ---------------------------------------------------------------------------
# Webhook test
# ---------------------------------------------------------------------------

class WebhookTestRequest(BaseModel):
    channel: str = Field(..., pattern=r"^(slack|email|pagerduty|jira)$")
    destination: str


# ---------------------------------------------------------------------------
# Pagination wrapper
# ---------------------------------------------------------------------------

class PaginatedResponse(BaseModel):
    items: list
    total: int
    page: int
    limit: int
    pages: int
