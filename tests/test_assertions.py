"""Tests for assertion types — no real API calls."""

from __future__ import annotations

import json

import pytest

from driftwatch.eval.assertions import (
    ContainsAssertion,
    CostAssertion,
    CustomAssertion,
    ExactMatchAssertion,
    JsonSchemaAssertion,
    LatencyAssertion,
    MaxLengthAssertion,
    MinLengthAssertion,
    NotContainsAssertion,
    RegexAssertion,
)


class TestMaxLength:
    def test_within_limit(self) -> None:
        a = MaxLengthAssertion(value=100)
        result = a.evaluate("short text")
        assert result.passed is True

    def test_exceeds_limit(self) -> None:
        a = MaxLengthAssertion(value=5)
        result = a.evaluate("this is longer than five")
        assert result.passed is False
        assert "exceeds" in result.message.lower()


class TestMinLength:
    def test_meets_minimum(self) -> None:
        a = MinLengthAssertion(value=3)
        result = a.evaluate("hello")
        assert result.passed is True

    def test_below_minimum(self) -> None:
        a = MinLengthAssertion(value=100)
        result = a.evaluate("hi")
        assert result.passed is False


class TestContains:
    def test_all_present(self) -> None:
        a = ContainsAssertion(value=["fox", "dog"])
        result = a.evaluate("The fox and the dog")
        assert result.passed is True

    def test_missing_substring(self) -> None:
        a = ContainsAssertion(value=["fox", "cat"])
        result = a.evaluate("The fox and the dog")
        assert result.passed is False
        assert "cat" in str(result.actual)

    def test_case_insensitive(self) -> None:
        a = ContainsAssertion(value=["FOX"], case_insensitive=True)
        result = a.evaluate("the fox is here")
        assert result.passed is True


class TestNotContains:
    def test_none_present(self) -> None:
        a = NotContainsAssertion(value=["error", "fail"])
        result = a.evaluate("All good")
        assert result.passed is True

    def test_unwanted_present(self) -> None:
        a = NotContainsAssertion(value=["error", "fail"])
        result = a.evaluate("There was an error")
        assert result.passed is False


class TestRegex:
    def test_matches(self) -> None:
        a = RegexAssertion(value=r"\d{3}-\d{4}")
        result = a.evaluate("Call 555-1234 now")
        assert result.passed is True

    def test_no_match(self) -> None:
        a = RegexAssertion(value=r"^\d+$")
        result = a.evaluate("not a number")
        assert result.passed is False


class TestExactMatch:
    def test_exact(self) -> None:
        a = ExactMatchAssertion(value="hello world")
        result = a.evaluate("hello world")
        assert result.passed is True

    def test_not_exact(self) -> None:
        a = ExactMatchAssertion(value="hello")
        result = a.evaluate("hello world")
        assert result.passed is False

    def test_strips_whitespace(self) -> None:
        a = ExactMatchAssertion(value="hello")
        result = a.evaluate("  hello  ")
        assert result.passed is True


class TestJsonSchema:
    def test_valid_json(self) -> None:
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
            "required": ["name", "age"],
        }
        a = JsonSchemaAssertion(schema=schema)
        result = a.evaluate(json.dumps({"name": "Alice", "age": 30}))
        assert result.passed is True

    def test_invalid_json_string(self) -> None:
        a = JsonSchemaAssertion(schema={"type": "object"})
        result = a.evaluate("not json at all")
        assert result.passed is False
        assert "not valid JSON" in result.message

    def test_schema_mismatch(self) -> None:
        schema = {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        }
        a = JsonSchemaAssertion(schema=schema)
        result = a.evaluate(json.dumps({"age": 30}))
        assert result.passed is False


class TestCost:
    def test_within_budget(self) -> None:
        a = CostAssertion(budget=1.0)
        result = a.evaluate("output", context={"cost": 0.5})
        assert result.passed is True

    def test_over_budget(self) -> None:
        a = CostAssertion(budget=0.1)
        result = a.evaluate("output", context={"cost": 0.5})
        assert result.passed is False


class TestLatency:
    def test_within_threshold(self) -> None:
        a = LatencyAssertion(threshold_ms=1000)
        result = a.evaluate("output", context={"latency_ms": 500})
        assert result.passed is True

    def test_exceeds_threshold(self) -> None:
        a = LatencyAssertion(threshold_ms=100)
        result = a.evaluate("output", context={"latency_ms": 500})
        assert result.passed is False


class TestCustom:
    def test_truthy_expression(self) -> None:
        a = CustomAssertion(expression="len(output) > 0")
        result = a.evaluate("hello")
        assert result.passed is True

    def test_falsy_expression(self) -> None:
        a = CustomAssertion(expression="len(output) > 100")
        result = a.evaluate("hello")
        assert result.passed is False

    def test_invalid_expression(self) -> None:
        a = CustomAssertion(expression="undefined_func()")
        result = a.evaluate("hello")
        assert result.passed is False
        assert "raised" in result.message.lower()
