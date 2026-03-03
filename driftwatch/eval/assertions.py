"""Assertion types for evaluating LLM outputs."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class AssertionResult:
    """Outcome of a single assertion evaluation."""

    passed: bool
    expected: Any
    actual: Any
    score: float | None = None
    message: str = ""


class BaseAssertion(ABC):
    """Base class every assertion type inherits from."""

    @abstractmethod
    def evaluate(self, output: str, context: dict[str, Any] | None = None) -> AssertionResult:
        """Evaluate *output* and return an ``AssertionResult``."""


class MaxLengthAssertion(BaseAssertion):
    def __init__(self, value: int) -> None:
        self.max_length = int(value)

    def evaluate(self, output: str, context: dict[str, Any] | None = None) -> AssertionResult:
        length = len(output)
        passed = length <= self.max_length
        return AssertionResult(
            passed=passed,
            expected=f"<= {self.max_length} chars",
            actual=length,
            message="" if passed else f"Output length {length} exceeds max {self.max_length}",
        )


class MinLengthAssertion(BaseAssertion):
    def __init__(self, value: int) -> None:
        self.min_length = int(value)

    def evaluate(self, output: str, context: dict[str, Any] | None = None) -> AssertionResult:
        length = len(output)
        passed = length >= self.min_length
        return AssertionResult(
            passed=passed,
            expected=f">= {self.min_length} chars",
            actual=length,
            message="" if passed else f"Output length {length} below min {self.min_length}",
        )


class ContainsAssertion(BaseAssertion):
    def __init__(self, value: list[str] | str, case_insensitive: bool = False) -> None:
        self.substrings = value if isinstance(value, list) else [value]
        self.case_insensitive = case_insensitive

    def evaluate(self, output: str, context: dict[str, Any] | None = None) -> AssertionResult:
        check_output = output.lower() if self.case_insensitive else output
        missing = [
            s
            for s in self.substrings
            if (s.lower() if self.case_insensitive else s) not in check_output
        ]
        passed = len(missing) == 0
        return AssertionResult(
            passed=passed,
            expected=self.substrings,
            actual=missing if missing else "all found",
            message="" if passed else f"Missing substrings: {missing}",
        )


class NotContainsAssertion(BaseAssertion):
    def __init__(self, value: list[str] | str, case_insensitive: bool = False) -> None:
        self.substrings = value if isinstance(value, list) else [value]
        self.case_insensitive = case_insensitive

    def evaluate(self, output: str, context: dict[str, Any] | None = None) -> AssertionResult:
        check_output = output.lower() if self.case_insensitive else output
        found = [
            s
            for s in self.substrings
            if (s.lower() if self.case_insensitive else s) in check_output
        ]
        passed = len(found) == 0
        return AssertionResult(
            passed=passed,
            expected=f"none of {self.substrings}",
            actual=found if found else "none found",
            message="" if passed else f"Unwanted substrings found: {found}",
        )


class RegexAssertion(BaseAssertion):
    def __init__(self, value: str) -> None:
        self.pattern = value
        self._compiled = re.compile(value)

    def evaluate(self, output: str, context: dict[str, Any] | None = None) -> AssertionResult:
        match = self._compiled.search(output)
        passed = match is not None
        return AssertionResult(
            passed=passed,
            expected=f"matches /{self.pattern}/",
            actual=match.group(0) if match else "no match",
            message="" if passed else f"Regex /{self.pattern}/ did not match",
        )


class ExactMatchAssertion(BaseAssertion):
    def __init__(self, value: str) -> None:
        self.expected_value = value

    def evaluate(self, output: str, context: dict[str, Any] | None = None) -> AssertionResult:
        passed = output.strip() == str(self.expected_value).strip()
        return AssertionResult(
            passed=passed,
            expected=self.expected_value,
            actual=output.strip(),
            message="" if passed else "Exact match failed",
        )


class SemanticSimilarityAssertion(BaseAssertion):
    """Uses sentence-transformers to compute cosine similarity."""

    _model_cache: dict[str, Any] = {}

    def __init__(self, reference: str, threshold: float = 0.8) -> None:
        self.reference = reference
        self.threshold = threshold

    @classmethod
    def _get_model(cls) -> Any:
        if "default" not in cls._model_cache:
            from sentence_transformers import SentenceTransformer

            cls._model_cache["default"] = SentenceTransformer("all-MiniLM-L6-v2")
        return cls._model_cache["default"]

    def evaluate(self, output: str, context: dict[str, Any] | None = None) -> AssertionResult:
        import numpy as np

        model = self._get_model()
        embeddings = model.encode([output, self.reference])
        cosine_sim = float(
            np.dot(embeddings[0], embeddings[1])
            / (np.linalg.norm(embeddings[0]) * np.linalg.norm(embeddings[1]) + 1e-10)
        )
        passed = cosine_sim >= self.threshold
        return AssertionResult(
            passed=passed,
            expected=f">= {self.threshold}",
            actual=round(cosine_sim, 4),
            score=round(cosine_sim, 4),
            message="" if passed else f"Similarity {cosine_sim:.4f} below threshold {self.threshold}",
        )


class JsonSchemaAssertion(BaseAssertion):
    def __init__(self, schema: dict[str, Any]) -> None:
        self.schema = schema

    def evaluate(self, output: str, context: dict[str, Any] | None = None) -> AssertionResult:
        import jsonschema

        try:
            data = json.loads(output)
        except json.JSONDecodeError as exc:
            return AssertionResult(
                passed=False,
                expected="valid JSON",
                actual=str(exc),
                message=f"Output is not valid JSON: {exc}",
            )

        try:
            jsonschema.validate(instance=data, schema=self.schema)
            return AssertionResult(passed=True, expected="schema match", actual=data)
        except jsonschema.ValidationError as exc:
            return AssertionResult(
                passed=False,
                expected="schema match",
                actual=exc.message,
                message=f"Schema validation failed: {exc.message}",
            )


class LLMJudgeAssertion(BaseAssertion):
    """Delegates evaluation to another LLM acting as a judge."""

    def __init__(
        self,
        rubric: str,
        judge_model: str = "gpt-4o",
        provider_name: str = "openai",
    ) -> None:
        self.rubric = rubric
        self.judge_model = judge_model
        self.provider_name = provider_name

    def evaluate(self, output: str, context: dict[str, Any] | None = None) -> AssertionResult:
        import asyncio

        from driftwatch.core.providers import get_provider

        provider = context.get("judge_provider") if context else None
        if provider is None:
            provider = get_provider(self.provider_name)

        prompt = (
            "You are an evaluation judge. Evaluate the following output against "
            "the rubric. Respond with a JSON object containing 'pass' (bool) and "
            "'score' (float 0-1) and 'reason' (string).\n\n"
            f"Rubric: {self.rubric}\n\nOutput to evaluate:\n{output}"
        )

        try:
            response = asyncio.get_event_loop().run_until_complete(
                provider.complete(prompt, self.judge_model)
            )
            result_data = json.loads(response.text)
            passed = bool(result_data.get("pass", False))
            score = float(result_data.get("score", 0.0))
            reason = result_data.get("reason", "")
            return AssertionResult(
                passed=passed,
                expected="judge approval",
                actual=reason,
                score=score,
                message=reason,
            )
        except Exception as exc:
            return AssertionResult(
                passed=False,
                expected="judge approval",
                actual=str(exc),
                message=f"LLM judge evaluation failed: {exc}",
            )


class CostAssertion(BaseAssertion):
    def __init__(self, budget: float) -> None:
        self.budget = budget

    def evaluate(self, output: str, context: dict[str, Any] | None = None) -> AssertionResult:
        actual_cost = (context or {}).get("cost", 0.0)
        passed = actual_cost <= self.budget
        return AssertionResult(
            passed=passed,
            expected=f"<= ${self.budget}",
            actual=f"${actual_cost}",
            score=actual_cost,
            message="" if passed else f"Cost ${actual_cost} exceeds budget ${self.budget}",
        )


class LatencyAssertion(BaseAssertion):
    def __init__(self, threshold_ms: float) -> None:
        self.threshold_ms = threshold_ms

    def evaluate(self, output: str, context: dict[str, Any] | None = None) -> AssertionResult:
        actual_ms = (context or {}).get("latency_ms", 0.0)
        passed = actual_ms <= self.threshold_ms
        return AssertionResult(
            passed=passed,
            expected=f"<= {self.threshold_ms}ms",
            actual=f"{actual_ms}ms",
            score=actual_ms,
            message="" if passed else f"Latency {actual_ms}ms exceeds {self.threshold_ms}ms",
        )


class CustomAssertion(BaseAssertion):
    """Runs a Python expression with ``output`` in scope."""

    def __init__(self, expression: str) -> None:
        self.expression = expression

    def evaluate(self, output: str, context: dict[str, Any] | None = None) -> AssertionResult:
        local_ns: dict[str, Any] = {"output": output, **(context or {})}
        _safe_builtins = {
            "len": len, "int": int, "float": float, "str": str,
            "bool": bool, "list": list, "dict": dict, "set": set,
            "tuple": tuple, "abs": abs, "min": min, "max": max,
            "sum": sum, "round": round, "sorted": sorted,
            "isinstance": isinstance, "type": type, "range": range,
            "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
            "any": any, "all": all, "True": True, "False": False, "None": None,
        }
        try:
            result = eval(self.expression, {"__builtins__": _safe_builtins}, local_ns)  # noqa: S307
            passed = bool(result)
            return AssertionResult(
                passed=passed,
                expected="expression is truthy",
                actual=result,
                message="" if passed else f"Expression evaluated to {result}",
            )
        except Exception as exc:
            return AssertionResult(
                passed=False,
                expected="expression is truthy",
                actual=str(exc),
                message=f"Expression raised: {exc}",
            )


_ASSERTION_REGISTRY: dict[str, type[BaseAssertion]] = {
    "max_length": MaxLengthAssertion,
    "min_length": MinLengthAssertion,
    "contains": ContainsAssertion,
    "not_contains": NotContainsAssertion,
    "regex": RegexAssertion,
    "exact_match": ExactMatchAssertion,
    "semantic_similarity": SemanticSimilarityAssertion,
    "json_schema": JsonSchemaAssertion,
    "llm_judge": LLMJudgeAssertion,
    "cost": CostAssertion,
    "latency": LatencyAssertion,
    "custom": CustomAssertion,
}


def build_assertion(spec: Any) -> BaseAssertion:
    """Construct the appropriate ``BaseAssertion`` subclass from an ``AssertionSpec``."""
    from driftwatch.core.suite_loader import AssertionSpec

    if not isinstance(spec, AssertionSpec):
        raise TypeError(f"Expected AssertionSpec, got {type(spec)}")

    cls = _ASSERTION_REGISTRY.get(spec.type)
    if cls is None:
        raise ValueError(f"Unknown assertion type: '{spec.type}'")

    if spec.type in ("max_length", "min_length"):
        return cls(value=spec.value)
    if spec.type in ("contains", "not_contains"):
        return cls(value=spec.value, case_insensitive=spec.case_insensitive)
    if spec.type == "regex":
        return cls(value=spec.value)
    if spec.type == "exact_match":
        return cls(value=spec.value)
    if spec.type == "semantic_similarity":
        return cls(reference=spec.reference or "", threshold=spec.threshold or 0.8)
    if spec.type == "json_schema":
        return cls(schema=spec.schema_ or {})
    if spec.type == "llm_judge":
        return cls(
            rubric=spec.rubric or "",
            judge_model=spec.judge_model or "gpt-4o",
        )
    if spec.type == "cost":
        return cls(budget=spec.budget or 0.0)
    if spec.type == "latency":
        return cls(threshold_ms=spec.threshold_ms or 0.0)
    if spec.type == "custom":
        return cls(expression=spec.expression or "")

    return cls()  # type: ignore[call-arg]
