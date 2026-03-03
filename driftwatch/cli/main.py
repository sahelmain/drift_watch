"""DriftWatch CLI — powered by Typer."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from driftwatch import __version__
from driftwatch.core.suite_loader import load_suite, validate_suite
from driftwatch.eval.engine import EvaluationEngine, SuiteRunResult

app = typer.Typer(
    name="driftwatch",
    help="LLM output evaluation and drift monitoring CLI.",
    add_completion=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"driftwatch {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-v", callback=_version_callback, is_eager=True
    ),
) -> None:
    """DriftWatch — LLM output evaluation & drift monitoring."""


def _render_table(result: SuiteRunResult) -> None:
    table = Table(title=f"Suite: {result.suite_name}", show_lines=True)
    table.add_column("Test", style="bold")
    table.add_column("Model")
    table.add_column("Pass?", justify="center")
    table.add_column("Assertions")
    table.add_column("Latency (ms)", justify="right")

    for tr in result.results:
        status = "[green]PASS[/green]" if tr.passed else "[red]FAIL[/red]"
        assertion_details = []
        for ar in tr.assertion_results:
            mark = "[green]✓[/green]" if ar.passed else "[red]✗[/red]"
            detail = f"{mark} {ar.message or 'OK'}" if ar.message else f"{mark}"
            assertion_details.append(detail)
        table.add_row(
            tr.test_name,
            tr.model,
            status,
            "\n".join(assertion_details) or "—",
            f"{tr.latency_ms:.0f}",
        )

    totals = f"{result.passed_tests}/{result.total_tests} passed ({result.pass_rate:.0%})"
    table.add_row("", "", "", "", "")
    table.add_row("[bold]Total[/bold]", "", totals, "", "")
    console.print(table)


def _render_json(result: SuiteRunResult) -> None:
    data = {
        "suite_name": result.suite_name,
        "started_at": result.started_at.isoformat(),
        "completed_at": result.completed_at.isoformat(),
        "total_tests": result.total_tests,
        "passed_tests": result.passed_tests,
        "pass_rate": result.pass_rate,
        "results": [
            {
                "test_name": tr.test_name,
                "model": tr.model,
                "passed": tr.passed,
                "latency_ms": tr.latency_ms,
                "token_count": tr.token_count,
                "assertions": [
                    {
                        "passed": ar.passed,
                        "expected": str(ar.expected),
                        "actual": str(ar.actual),
                        "score": ar.score,
                        "message": ar.message,
                    }
                    for ar in tr.assertion_results
                ],
            }
            for tr in result.results
        ],
    }
    console.print_json(json.dumps(data, indent=2, default=str))


@app.command()
def run(
    suite_file: str = typer.Argument(..., help="Path to the YAML test suite file"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Override model for all tests"),
    verbose: bool = typer.Option(False, "--verbose", help="Show detailed output"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table or json"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and show plan without calling LLMs"),
) -> None:
    """Load a YAML suite, run all tests, and display results."""
    try:
        suite = load_suite(suite_file)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    errors = validate_suite(suite)
    if errors:
        console.print("[red]Suite validation errors:[/red]")
        for err in errors:
            console.print(f"  • {err}")
        raise typer.Exit(code=1)

    if model:
        for test in suite.tests:
            test.model = model

    if dry_run:
        console.print(f"[bold]Suite:[/bold] {suite.name} ({len(suite.tests)} tests)")
        for test in suite.tests:
            console.print(f"  • {test.name} → model={test.model}, assertions={len(test.assertions)}")
        console.print("\n[yellow]Dry-run mode — no LLM calls made.[/yellow]")
        return

    if verbose:
        console.print(f"[bold]Running suite:[/bold] {suite.name}")

    engine = EvaluationEngine()
    result = asyncio.run(engine.run_suite(suite))

    if output == "json":
        _render_json(result)
    else:
        _render_table(result)

    if result.passed_tests < result.total_tests:
        raise typer.Exit(code=1)


@app.command()
def validate(
    suite_file: str = typer.Argument(..., help="Path to the YAML test suite file"),
) -> None:
    """Validate a YAML suite file without running tests."""
    try:
        suite = load_suite(suite_file)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    errors = validate_suite(suite)
    if errors:
        console.print("[red]Validation errors:[/red]")
        for err in errors:
            console.print(f"  • {err}")
        raise typer.Exit(code=1)

    console.print(
        f"[green]✓[/green] Suite [bold]{suite.name}[/bold] is valid "
        f"({len(suite.tests)} tests, "
        f"{sum(len(t.assertions) for t in suite.tests)} assertions)"
    )


@app.command()
def drift(
    suite_file: str = typer.Argument(..., help="Path to the YAML test suite file"),
    history_dir: str = typer.Option(..., "--history-dir", help="Directory with historical JSON results"),
) -> None:
    """Compare a current run against historical results to detect drift."""
    from driftwatch.eval.statistics import compute_drift_score

    try:
        suite = load_suite(suite_file)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1)

    hist_path = Path(history_dir)
    if not hist_path.is_dir():
        console.print(f"[red]History directory not found:[/red] {history_dir}")
        raise typer.Exit(code=1)

    historical: list[dict[str, float]] = []
    for f in sorted(hist_path.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            historical.append({
                "pass_rate": data.get("pass_rate", 0.0),
                "latency_ms": data.get("latency_ms", 0.0),
            })
        except (json.JSONDecodeError, KeyError):
            console.print(f"[yellow]Skipping invalid file:[/yellow] {f.name}")

    if not historical:
        console.print("[yellow]No valid historical data found.[/yellow]")
        raise typer.Exit(code=1)

    engine = EvaluationEngine()
    result = asyncio.run(engine.run_suite(suite))

    current = [{"pass_rate": result.pass_rate, "latency_ms": 0.0}]
    report = compute_drift_score(historical, current)

    table = Table(title="Drift Report", show_lines=True)
    table.add_column("Metric", style="bold")
    table.add_column("Value")

    table.add_row("PSI Score", f"{report.psi_score:.6f}")
    table.add_row("KL Divergence", f"{report.kl_divergence:.6f}")
    table.add_row("Trend", report.trend_direction)
    table.add_row("95% CI", f"({report.confidence_interval[0]:.4f}, {report.confidence_interval[1]:.4f})")
    drift_style = "[red]YES[/red]" if report.is_drifting else "[green]NO[/green]"
    table.add_row("Drifting?", drift_style)

    for key, val in report.details.items():
        table.add_row(key, str(val))

    console.print(table)

    if report.is_drifting:
        raise typer.Exit(code=1)


_EXAMPLE_SUITE = """\
name: "example_suite"
description: "Example DriftWatch test suite"
model_default: "gpt-4o"
variables:
  article: "The quick brown fox jumps over the lazy dog."
tests:
  - name: "summarization_quality"
    prompt: "Summarize this article: {article}"
    model: "gpt-4o"
    assertions:
      - type: "max_length"
        value: 200
      - type: "contains"
        value: ["fox", "dog"]

  - name: "json_output"
    prompt: "Return a JSON object with keys 'name' and 'age' for a person named Alice who is 30."
    assertions:
      - type: "json_schema"
        schema:
          type: "object"
          properties:
            name: {type: "string"}
            age: {type: "integer"}
          required: ["name", "age"]

  - name: "safety_check"
    prompt: "What is 2+2?"
    assertions:
      - type: "contains"
        value: ["4"]
      - type: "not_contains"
        value: ["I cannot", "I'm sorry"]
      - type: "max_length"
        value: 100
"""


@app.command()
def init(
    output_path: str = typer.Option("suite.yaml", "--output", "-o", help="Output file path"),
) -> None:
    """Generate an example test suite YAML file."""
    path = Path(output_path)
    if path.exists():
        overwrite = typer.confirm(f"{path} already exists. Overwrite?")
        if not overwrite:
            raise typer.Abort()

    path.write_text(_EXAMPLE_SUITE)
    console.print(f"[green]✓[/green] Example suite written to [bold]{path}[/bold]")


if __name__ == "__main__":
    app()
