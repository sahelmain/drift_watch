"""Initial migration — create all tables.

Revision ID: 001
Revises:
Create Date: 2026-03-02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False, unique=True),
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="member"),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_org_id", "users", ["org_id"])

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key_hash", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(8), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("scopes", postgresql.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])
    op.create_index("ix_api_keys_org_id", "api_keys", ["org_id"])

    op.create_table(
        "test_suites",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("yaml_content", sa.Text, nullable=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("schedule_cron", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_test_suites_org_id", "test_suites", ["org_id"])

    op.create_table(
        "test_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("suite_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_suites.id"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("trigger", sa.String(50), nullable=False, server_default="manual"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pass_rate", sa.Float, nullable=True),
        sa.Column("total_tests", sa.Integer, nullable=True),
        sa.Column("passed_tests", sa.Integer, nullable=True),
        sa.Column("metadata", postgresql.JSON, nullable=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
    )
    op.create_index("ix_test_runs_suite_id", "test_runs", ["suite_id"])
    op.create_index("ix_test_runs_org_id", "test_runs", ["org_id"])
    op.create_index("ix_test_runs_started_at", "test_runs", ["started_at"])

    op.create_table(
        "test_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_runs.id"), nullable=False),
        sa.Column("test_name", sa.String(255), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("output", sa.Text, nullable=True),
        sa.Column("passed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("latency_ms", sa.Float, nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("cost", sa.Float, nullable=True),
    )
    op.create_index("ix_test_results_run_id", "test_results", ["run_id"])

    op.create_table(
        "assertion_results",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("result_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_results.id"), nullable=False),
        sa.Column("assertion_type", sa.String(100), nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("expected", postgresql.JSON, nullable=True),
        sa.Column("actual", postgresql.JSON, nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("message", sa.Text, nullable=True),
    )
    op.create_index("ix_assertion_results_result_id", "assertion_results", ["result_id"])

    op.create_table(
        "drift_scores",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("suite_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_suites.id"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_runs.id"), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_drift_scores_suite_id", "drift_scores", ["suite_id"])
    op.create_index("ix_drift_scores_timestamp", "drift_scores", ["timestamp"])

    op.create_table(
        "alert_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("suite_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_suites.id"), nullable=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("destination", sa.String(500), nullable=False),
        sa.Column("threshold_metric", sa.String(100), nullable=False),
        sa.Column("threshold_value", sa.Float, nullable=False),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alert_configs_org_id", "alert_configs", ["org_id"])

    op.create_table(
        "alert_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("alert_config_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("alert_configs.id"), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_runs.id"), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="sent"),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_alert_events_config_id", "alert_events", ["alert_config_id"])
    op.create_index("ix_alert_events_run_id", "alert_events", ["run_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("details", postgresql.JSON, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_logs_org_id", "audit_logs", ["org_id"])
    op.create_index("ix_audit_logs_timestamp", "audit_logs", ["timestamp"])

    op.create_table(
        "policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("suite_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_suites.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("metric", sa.String(100), nullable=False),
        sa.Column("operator", sa.String(10), nullable=False),
        sa.Column("threshold", sa.Float, nullable=False),
        sa.Column("action", sa.String(50), nullable=False, server_default="notify"),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_policies_org_id", "policies", ["org_id"])

    op.create_table(
        "datasets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("content", postgresql.JSON, nullable=True),
        sa.Column("row_count", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_datasets_org_id", "datasets", ["org_id"])

    op.create_table(
        "prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("suite_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("test_suites.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("yaml_content", sa.Text, nullable=False),
        sa.Column("change_message", sa.Text, nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_prompt_versions_suite_id", "prompt_versions", ["suite_id"])


def downgrade() -> None:
    op.drop_table("prompt_versions")
    op.drop_table("datasets")
    op.drop_table("policies")
    op.drop_table("audit_logs")
    op.drop_table("alert_events")
    op.drop_table("alert_configs")
    op.drop_table("drift_scores")
    op.drop_table("assertion_results")
    op.drop_table("test_results")
    op.drop_table("test_runs")
    op.drop_table("test_suites")
    op.drop_table("api_keys")
    op.drop_table("users")
    op.drop_table("organizations")
