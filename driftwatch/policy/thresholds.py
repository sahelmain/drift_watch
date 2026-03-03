"""Policy engine for evaluating quality gates and drift thresholds."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from driftwatch.eval.engine import SuiteRunResult
from driftwatch.eval.statistics import DriftReport


class Operator(str, Enum):
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    EQ = "eq"


class Action(str, Enum):
    BLOCK = "block"
    WARN = "warn"
    NOTIFY = "notify"


class PolicyRule(BaseModel):
    """A single rule that compares a metric against a threshold."""

    metric: str  # pass_rate | drift_score | latency | cost
    operator: Operator
    threshold: float
    action: Action = Action.WARN


class PolicySet(BaseModel):
    """Collection of policy rules."""

    rules: list[PolicyRule] = Field(default_factory=list)


@dataclass
class PolicyViolation:
    """Details about a single policy rule that was violated."""

    rule: PolicyRule
    actual_value: float
    message: str


@dataclass
class PolicyEvaluation:
    """Result of evaluating a ``PolicySet`` against a run."""

    passed: bool
    violations: list[PolicyViolation] = field(default_factory=list)
    warnings: list[PolicyViolation] = field(default_factory=list)


def _compare(actual: float, operator: Operator, threshold: float) -> bool:
    if operator == Operator.GT:
        return actual > threshold
    if operator == Operator.LT:
        return actual < threshold
    if operator == Operator.GTE:
        return actual >= threshold
    if operator == Operator.LTE:
        return actual <= threshold
    if operator == Operator.EQ:
        return actual == threshold
    return False


def _resolve_metric(
    rule: PolicyRule,
    run_result: SuiteRunResult,
    drift_report: DriftReport | None,
) -> float | None:
    """Extract the numeric value for *rule.metric* from the available data."""
    metric = rule.metric.lower()
    if metric == "pass_rate":
        return run_result.pass_rate
    if metric == "drift_score" and drift_report is not None:
        return drift_report.psi_score
    if metric == "latency":
        if run_result.results:
            return sum(r.latency_ms for r in run_result.results) / len(run_result.results)
        return 0.0
    if metric == "cost":
        return 0.0
    return None


def evaluate_policies(
    policies: PolicySet,
    run_result: SuiteRunResult,
    drift_report: DriftReport | None = None,
) -> PolicyEvaluation:
    """Evaluate all policy rules and return a ``PolicyEvaluation``.

    A rule whose ``action`` is ``block`` causes the overall evaluation
    to fail.  Rules with ``warn`` / ``notify`` are collected as warnings
    but do not block.
    """
    violations: list[PolicyViolation] = []
    warnings: list[PolicyViolation] = []

    for rule in policies.rules:
        value = _resolve_metric(rule, run_result, drift_report)
        if value is None:
            continue

        satisfied = _compare(value, rule.operator, rule.threshold)
        if not satisfied:
            violation = PolicyViolation(
                rule=rule,
                actual_value=value,
                message=(
                    f"Policy violated: {rule.metric} {rule.operator.value} "
                    f"{rule.threshold} — actual {value}"
                ),
            )
            if rule.action == Action.BLOCK:
                violations.append(violation)
            else:
                warnings.append(violation)

    return PolicyEvaluation(
        passed=len(violations) == 0,
        violations=violations,
        warnings=warnings,
    )
