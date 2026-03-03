"""Suite loader: Pydantic models and YAML parsing for test suites."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, model_validator


class AssertionSpec(BaseModel):
    """Specification for a single assertion on LLM output."""

    type: str
    value: Any = None
    threshold: float | None = None
    reference: str | None = None
    schema_: dict[str, Any] | None = Field(default=None, alias="schema")
    case_insensitive: bool = False
    expression: str | None = None
    rubric: str | None = None
    judge_model: str | None = None
    budget: float | None = None
    threshold_ms: float | None = None

    model_config = {"populate_by_name": True}


class TestSpec(BaseModel):
    """Specification for a single test case."""

    name: str
    prompt: str
    model: str | None = None
    assertions: list[AssertionSpec] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)


class SuiteSpec(BaseModel):
    """Top-level specification for a test suite."""

    name: str
    description: str = ""
    model_default: str = "gpt-4o"
    tests: list[TestSpec] = Field(default_factory=list)
    variables: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def propagate_defaults(self) -> "SuiteSpec":
        """Fill per-test model from suite default when not specified."""
        for test in self.tests:
            if test.model is None:
                test.model = self.model_default
        return self


_VAR_PATTERN = re.compile(r"\{(\w+)\}")


def _interpolate(template: str, variables: dict[str, Any]) -> str:
    """Replace ``{variable_name}`` placeholders in *template*."""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in variables:
            return str(variables[key])
        return match.group(0)

    return _VAR_PATTERN.sub(_replace, template)


def resolve_variables(suite: SuiteSpec) -> SuiteSpec:
    """Interpolate suite- and test-level variables into prompts."""
    for test in suite.tests:
        merged = {**suite.variables, **test.variables}
        test.prompt = _interpolate(test.prompt, merged)
    return suite


def load_suite(path: str | Path) -> SuiteSpec:
    """Parse a YAML file and return a validated ``SuiteSpec``.

    Raises ``FileNotFoundError`` when *path* does not exist and
    ``ValueError`` on schema violations.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Suite file not found: {file_path}")

    raw = file_path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in {file_path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping at top level in {file_path}")

    suite = SuiteSpec.model_validate(data)
    suite = resolve_variables(suite)
    return suite


def validate_suite(suite: SuiteSpec) -> list[str]:
    """Return a list of human-readable validation errors (empty if valid)."""
    errors: list[str] = []

    if not suite.tests:
        errors.append("Suite has no tests defined.")

    seen_names: set[str] = set()
    for idx, test in enumerate(suite.tests):
        if test.name in seen_names:
            errors.append(f"Duplicate test name '{test.name}' at index {idx}.")
        seen_names.add(test.name)

        if not test.prompt.strip():
            errors.append(f"Test '{test.name}' has an empty prompt.")

        if not test.assertions:
            errors.append(f"Test '{test.name}' has no assertions.")

        for a_idx, assertion in enumerate(test.assertions):
            valid_types = {
                "max_length",
                "min_length",
                "contains",
                "not_contains",
                "regex",
                "exact_match",
                "semantic_similarity",
                "json_schema",
                "llm_judge",
                "cost",
                "latency",
                "custom",
            }
            if assertion.type not in valid_types:
                errors.append(
                    f"Test '{test.name}', assertion {a_idx}: "
                    f"unknown type '{assertion.type}'. "
                    f"Valid types: {sorted(valid_types)}"
                )

    return errors
