"""Evaluation engine: orchestrates suite execution and assertion evaluation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from driftwatch.core.providers import LLMProvider, get_provider
from driftwatch.core.suite_loader import AssertionSpec, SuiteSpec, TestSpec
from driftwatch.eval.assertions import AssertionResult, build_assertion


@dataclass
class TestRunResult:
    """Outcome of a single test case."""

    test_name: str
    model: str
    prompt: str
    output: str
    passed: bool
    assertion_results: list[AssertionResult]
    latency_ms: float
    token_count: int


@dataclass
class SuiteRunResult:
    """Aggregated outcome of an entire suite run."""

    suite_name: str
    started_at: datetime
    completed_at: datetime
    results: list[TestRunResult]
    total_tests: int = 0
    passed_tests: int = 0

    @property
    def pass_rate(self) -> float:
        return self.passed_tests / self.total_tests if self.total_tests else 0.0


def _infer_provider_name(model: str) -> str:
    """Best-effort mapping from model string to provider name."""
    model_lower = model.lower()
    if model_lower.startswith("claude"):
        return "anthropic"
    return "openai"


def evaluate_assertions(
    output: str,
    assertions: list[AssertionSpec],
    context: dict[str, Any] | None = None,
) -> list[AssertionResult]:
    """Run every assertion against *output*, returning a list of results."""
    results: list[AssertionResult] = []
    for spec in assertions:
        assertion = build_assertion(spec)
        results.append(assertion.evaluate(output, context))
    return results


class EvaluationEngine:
    """Runs test suites against LLM providers and evaluates outputs."""

    def __init__(self, concurrency: int = 5) -> None:
        self._concurrency = concurrency
        self._providers: dict[str, LLMProvider] = {}

    def _get_or_create_provider(
        self,
        model: str,
        overrides: dict[str, Any] | None = None,
    ) -> LLMProvider:
        name = _infer_provider_name(model)
        extra = (overrides or {}).get(name, {})
        cache_key = f"{name}:{id(extra)}"
        if cache_key not in self._providers:
            self._providers[cache_key] = get_provider(name, **extra)
        return self._providers[cache_key]

    async def run_test(
        self,
        test: TestSpec,
        provider: LLMProvider,
    ) -> TestRunResult:
        """Execute a single test and evaluate its assertions."""
        model = test.model or "gpt-4o"
        response = await provider.complete(test.prompt, model)

        context: dict[str, Any] = {
            "latency_ms": response.latency_ms,
            "token_count": response.token_count,
            "cost": 0.0,
        }
        assertion_results = evaluate_assertions(response.text, test.assertions, context)
        all_passed = all(r.passed for r in assertion_results)

        return TestRunResult(
            test_name=test.name,
            model=response.model,
            prompt=test.prompt,
            output=response.text,
            passed=all_passed,
            assertion_results=assertion_results,
            latency_ms=response.latency_ms,
            token_count=response.token_count,
        )

    async def run_suite(
        self,
        suite: SuiteSpec,
        provider_overrides: dict[str, Any] | None = None,
    ) -> SuiteRunResult:
        """Execute every test in *suite*, respecting concurrency limits."""
        started_at = datetime.now(timezone.utc)
        semaphore = asyncio.Semaphore(self._concurrency)

        async def _bounded(test: TestSpec) -> TestRunResult:
            async with semaphore:
                model = test.model or suite.model_default
                provider = self._get_or_create_provider(model, provider_overrides)
                return await self.run_test(test, provider)

        results = await asyncio.gather(*[_bounded(t) for t in suite.tests])
        completed_at = datetime.now(timezone.utc)

        passed = sum(1 for r in results if r.passed)
        return SuiteRunResult(
            suite_name=suite.name,
            started_at=started_at,
            completed_at=completed_at,
            results=list(results),
            total_tests=len(results),
            passed_tests=passed,
        )
