"""Tests for suite_loader module."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml

from driftwatch.core.suite_loader import (
    SuiteSpec,
    load_suite,
    resolve_variables,
    validate_suite,
)


def _write_yaml(tmp_path: Path, data: dict) -> Path:
    p = tmp_path / "suite.yaml"
    p.write_text(yaml.dump(data))
    return p


class TestLoadSuite:
    def test_load_minimal(self, tmp_path: Path) -> None:
        data = {
            "name": "minimal",
            "tests": [
                {
                    "name": "t1",
                    "prompt": "hello",
                    "assertions": [{"type": "max_length", "value": 100}],
                }
            ],
        }
        path = _write_yaml(tmp_path, data)
        suite = load_suite(path)
        assert suite.name == "minimal"
        assert len(suite.tests) == 1
        assert suite.tests[0].model == "gpt-4o"  # default propagated

    def test_file_not_found(self) -> None:
        with pytest.raises(FileNotFoundError):
            load_suite("/nonexistent/path.yaml")

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("::invalid::yaml::[")
        with pytest.raises(ValueError):
            load_suite(p)

    def test_non_mapping_yaml(self, tmp_path: Path) -> None:
        p = tmp_path / "list.yaml"
        p.write_text("- item1\n- item2\n")
        with pytest.raises(ValueError, match="Expected a YAML mapping"):
            load_suite(p)

    def test_model_override(self, tmp_path: Path) -> None:
        data = {
            "name": "override",
            "model_default": "claude-3-opus-20240229",
            "tests": [
                {"name": "t1", "prompt": "hi", "assertions": [{"type": "max_length", "value": 50}]},
                {
                    "name": "t2",
                    "prompt": "hi",
                    "model": "gpt-4o",
                    "assertions": [{"type": "max_length", "value": 50}],
                },
            ],
        }
        path = _write_yaml(tmp_path, data)
        suite = load_suite(path)
        assert suite.tests[0].model == "claude-3-opus-20240229"
        assert suite.tests[1].model == "gpt-4o"


class TestResolveVariables:
    def test_suite_level_variables(self) -> None:
        suite = SuiteSpec(
            name="vars",
            variables={"topic": "AI"},
            tests=[
                {
                    "name": "t1",
                    "prompt": "Tell me about {topic}",
                    "assertions": [{"type": "max_length", "value": 100}],
                }
            ],
        )
        suite = resolve_variables(suite)
        assert suite.tests[0].prompt == "Tell me about AI"

    def test_test_level_override(self) -> None:
        suite = SuiteSpec(
            name="vars",
            variables={"topic": "AI"},
            tests=[
                {
                    "name": "t1",
                    "prompt": "Tell me about {topic}",
                    "variables": {"topic": "ML"},
                    "assertions": [{"type": "max_length", "value": 100}],
                }
            ],
        )
        suite = resolve_variables(suite)
        assert suite.tests[0].prompt == "Tell me about ML"

    def test_unresolved_variables_left_as_is(self) -> None:
        suite = SuiteSpec(
            name="vars",
            tests=[
                {
                    "name": "t1",
                    "prompt": "Hello {unknown}",
                    "assertions": [{"type": "max_length", "value": 100}],
                }
            ],
        )
        suite = resolve_variables(suite)
        assert "{unknown}" in suite.tests[0].prompt


class TestValidateSuite:
    def test_empty_suite(self) -> None:
        suite = SuiteSpec(name="empty")
        errors = validate_suite(suite)
        assert any("no tests" in e.lower() for e in errors)

    def test_duplicate_names(self) -> None:
        suite = SuiteSpec(
            name="dupes",
            tests=[
                {"name": "dup", "prompt": "a", "assertions": [{"type": "max_length", "value": 1}]},
                {"name": "dup", "prompt": "b", "assertions": [{"type": "max_length", "value": 1}]},
            ],
        )
        errors = validate_suite(suite)
        assert any("duplicate" in e.lower() for e in errors)

    def test_unknown_assertion_type(self) -> None:
        suite = SuiteSpec(
            name="unknown",
            tests=[
                {"name": "t", "prompt": "p", "assertions": [{"type": "bogus"}]},
            ],
        )
        errors = validate_suite(suite)
        assert any("unknown type" in e.lower() for e in errors)

    def test_valid_suite_no_errors(self) -> None:
        suite = SuiteSpec(
            name="ok",
            tests=[
                {
                    "name": "t1",
                    "prompt": "hello",
                    "assertions": [{"type": "contains", "value": ["hello"]}],
                }
            ],
        )
        errors = validate_suite(suite)
        assert errors == []
