from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(50), nullable=False, default="free")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list[User]] = relationship("User", back_populates="organization", lazy="selectin")
    suites: Mapped[list[TestSuite]] = relationship("TestSuite", back_populates="organization", lazy="selectin")
    api_keys: Mapped[list[ApiKey]] = relationship("ApiKey", back_populates="organization", lazy="selectin")
    alert_configs: Mapped[list[AlertConfig]] = relationship("AlertConfig", back_populates="organization", lazy="selectin")
    audit_logs: Mapped[list[AuditLog]] = relationship("AuditLog", back_populates="organization", lazy="selectin")
    policies: Mapped[list[Policy]] = relationship("Policy", back_populates="organization", lazy="selectin")
    datasets: Mapped[list[Dataset]] = relationship("Dataset", back_populates="organization", lazy="selectin")
    runs: Mapped[list[TestRun]] = relationship("TestRun", back_populates="organization", lazy="selectin")


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization: Mapped[Organization] = relationship("Organization", back_populates="users")


class ApiKey(Base):
    __tablename__ = "api_keys"
    __table_args__ = (
        Index("ix_api_keys_key_hash", "key_hash"),
        Index("ix_api_keys_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(8), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False)
    scopes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped[Organization] = relationship("Organization", back_populates="api_keys")


class TestSuite(Base):
    __tablename__ = "test_suites"
    __table_args__ = (
        Index("ix_test_suites_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    yaml_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False)
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    organization: Mapped[Organization] = relationship("Organization", back_populates="suites")
    runs: Mapped[list[TestRun]] = relationship("TestRun", back_populates="suite", lazy="selectin")
    drift_scores: Mapped[list[DriftScore]] = relationship("DriftScore", back_populates="suite", lazy="selectin")
    prompt_versions: Mapped[list[PromptVersion]] = relationship("PromptVersion", back_populates="suite", lazy="selectin")


class TestRun(Base):
    __tablename__ = "test_runs"
    __table_args__ = (
        Index("ix_test_runs_suite_id", "suite_id"),
        Index("ix_test_runs_org_id", "org_id"),
        Index("ix_test_runs_started_at", "started_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    suite_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("test_suites.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    trigger: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pass_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_tests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed_tests: Mapped[int | None] = mapped_column(Integer, nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False)

    suite: Mapped[TestSuite] = relationship("TestSuite", back_populates="runs")
    organization: Mapped[Organization] = relationship("Organization", back_populates="runs")
    results: Mapped[list[TestResult]] = relationship("TestResult", back_populates="run", lazy="selectin")
    drift_scores: Mapped[list[DriftScore]] = relationship("DriftScore", back_populates="run", lazy="selectin")


class TestResult(Base):
    __tablename__ = "test_results"
    __table_args__ = (
        Index("ix_test_results_run_id", "run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("test_runs.id"), nullable=False)
    test_name: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost: Mapped[float | None] = mapped_column(Float, nullable=True)

    run: Mapped[TestRun] = relationship("TestRun", back_populates="results")
    assertion_results: Mapped[list[AssertionResult]] = relationship("AssertionResult", back_populates="result", lazy="selectin")


class AssertionResult(Base):
    __tablename__ = "assertion_results"
    __table_args__ = (
        Index("ix_assertion_results_result_id", "result_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    result_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("test_results.id"), nullable=False)
    assertion_type: Mapped[str] = mapped_column(String(100), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    expected: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actual: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    result: Mapped[TestResult] = relationship("TestResult", back_populates="assertion_results")


class DriftScore(Base):
    __tablename__ = "drift_scores"
    __table_args__ = (
        Index("ix_drift_scores_suite_id", "suite_id"),
        Index("ix_drift_scores_timestamp", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    suite_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("test_suites.id"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("test_runs.id"), nullable=False)
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    suite: Mapped[TestSuite] = relationship("TestSuite", back_populates="drift_scores")
    run: Mapped[TestRun] = relationship("TestRun", back_populates="drift_scores")


class AlertConfig(Base):
    __tablename__ = "alert_configs"
    __table_args__ = (
        Index("ix_alert_configs_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    suite_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("test_suites.id"), nullable=True)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    destination: Mapped[str] = mapped_column(String(500), nullable=False)
    threshold_metric: Mapped[str] = mapped_column(String(100), nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization] = relationship("Organization", back_populates="alert_configs")
    events: Mapped[list[AlertEvent]] = relationship("AlertEvent", back_populates="config", lazy="selectin")


class AlertEvent(Base):
    __tablename__ = "alert_events"
    __table_args__ = (
        Index("ix_alert_events_config_id", "alert_config_id"),
        Index("ix_alert_events_run_id", "run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    alert_config_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("alert_configs.id"), nullable=False)
    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("test_runs.id"), nullable=False)
    channel: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="sent")
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    config: Mapped[AlertConfig] = relationship("AlertConfig", back_populates="events")


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_org_id", "org_id"),
        Index("ix_audit_logs_timestamp", "timestamp"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization] = relationship("Organization", back_populates="audit_logs")


class Policy(Base):
    __tablename__ = "policies"
    __table_args__ = (
        Index("ix_policies_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False)
    suite_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("test_suites.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    metric: Mapped[str] = mapped_column(String(100), nullable=False)
    operator: Mapped[str] = mapped_column(String(10), nullable=False)
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False, default="notify")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization] = relationship("Organization", back_populates="policies")


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = (
        Index("ix_datasets_org_id", "org_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    organization: Mapped[Organization] = relationship("Organization", back_populates="datasets")


class PromptVersion(Base):
    __tablename__ = "prompt_versions"
    __table_args__ = (
        Index("ix_prompt_versions_suite_id", "suite_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    suite_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("test_suites.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    yaml_content: Mapped[str] = mapped_column(Text, nullable=False)
    change_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    suite: Mapped[TestSuite] = relationship("TestSuite", back_populates="prompt_versions")
