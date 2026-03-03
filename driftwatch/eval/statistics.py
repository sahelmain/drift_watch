"""Statistical drift detection between historical and current evaluation runs."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import stats


@dataclass
class DriftReport:
    """Summary of drift analysis between historical and current results."""

    psi_score: float
    kl_divergence: float
    trend_direction: str  # "improving" | "degrading" | "stable"
    confidence_interval: tuple[float, float]
    is_drifting: bool
    details: dict[str, float] = field(default_factory=dict)


def compute_psi(expected: np.ndarray, actual: np.ndarray, buckets: int = 10) -> float:
    """Population Stability Index between two distributions.

    Both arrays are histogrammed into *buckets* bins and the PSI is
    computed across those bins.  Values below 0.1 indicate no
    significant shift; above 0.25 indicates major shift.
    """
    eps = 1e-6
    min_val = min(expected.min(), actual.min())
    max_val = max(expected.max(), actual.max())
    breakpoints = np.linspace(min_val - eps, max_val + eps, buckets + 1)

    expected_counts = np.histogram(expected, bins=breakpoints)[0].astype(float)
    actual_counts = np.histogram(actual, bins=breakpoints)[0].astype(float)

    expected_pct = (expected_counts + eps) / (expected_counts.sum() + eps * buckets)
    actual_pct = (actual_counts + eps) / (actual_counts.sum() + eps * buckets)

    psi = float(np.sum((actual_pct - expected_pct) * np.log(actual_pct / expected_pct)))
    return psi


def compute_kl_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Kullback-Leibler divergence KL(p || q) with smoothing."""
    eps = 1e-10
    p_safe = np.clip(p, eps, None)
    q_safe = np.clip(q, eps, None)
    p_norm = p_safe / p_safe.sum()
    q_norm = q_safe / q_safe.sum()
    return float(np.sum(p_norm * np.log(p_norm / q_norm)))


def _moving_average(values: list[float], window: int = 3) -> list[float]:
    if len(values) < window:
        return values
    out: list[float] = []
    for i in range(len(values) - window + 1):
        out.append(sum(values[i : i + window]) / window)
    return out


def _trend_direction(values: list[float]) -> str:
    """Determine if a time series is improving, degrading, or stable."""
    if len(values) < 2:
        return "stable"
    ma = _moving_average(values)
    if len(ma) < 2:
        return "stable"
    slope = ma[-1] - ma[0]
    if abs(slope) < 0.02:
        return "stable"
    return "improving" if slope > 0 else "degrading"


def _chi_squared_pass_rate(
    hist_passed: int,
    hist_total: int,
    curr_passed: int,
    curr_total: int,
) -> float:
    """Return the p-value of a chi-squared test comparing two pass rates."""
    observed = np.array(
        [
            [curr_passed, curr_total - curr_passed],
            [hist_passed, hist_total - hist_passed],
        ]
    )
    if observed.min() < 0:
        return 1.0
    try:
        _, p_value, _, _ = stats.chi2_contingency(observed)
        return float(p_value)
    except ValueError:
        return 1.0


def compute_drift_score(
    historical_results: list[dict[str, float]],
    current_results: list[dict[str, float]],
    threshold: float = 0.2,
) -> DriftReport:
    """Compare current evaluation run against historical runs.

    Each entry in *historical_results* / *current_results* is expected to
    contain at least ``{"pass_rate": float, "latency_ms": float}``.

    Returns a ``DriftReport`` summarising the statistical shift.
    """
    hist_rates = np.array([r.get("pass_rate", 0.0) for r in historical_results], dtype=float)
    curr_rates = np.array([r.get("pass_rate", 0.0) for r in current_results], dtype=float)

    if len(hist_rates) < 2 or len(curr_rates) < 1:
        return DriftReport(
            psi_score=0.0,
            kl_divergence=0.0,
            trend_direction="stable",
            confidence_interval=(0.0, 0.0),
            is_drifting=False,
            details={"note": "insufficient data"},
        )

    psi = compute_psi(hist_rates, curr_rates)

    eps = 1e-10
    hist_bins = np.histogram(hist_rates, bins=5)[0].astype(float) + eps
    curr_bins = np.histogram(curr_rates, bins=5)[0].astype(float) + eps
    kl = compute_kl_divergence(hist_bins, curr_bins)

    all_rates = list(hist_rates) + list(curr_rates)
    direction = _trend_direction(all_rates)

    hist_passed = int(np.round(hist_rates.mean() * len(historical_results)))
    hist_total = len(historical_results)
    curr_passed = int(np.round(curr_rates.mean() * len(current_results)))
    curr_total = len(current_results)
    p_value = _chi_squared_pass_rate(hist_passed, hist_total, curr_passed, curr_total)

    mean = float(curr_rates.mean())
    se = float(curr_rates.std() / np.sqrt(len(curr_rates))) if len(curr_rates) > 1 else 0.0
    ci = (round(mean - 1.96 * se, 4), round(mean + 1.96 * se, 4))

    is_drifting = psi > threshold

    return DriftReport(
        psi_score=round(psi, 6),
        kl_divergence=round(kl, 6),
        trend_direction=direction,
        confidence_interval=ci,
        is_drifting=is_drifting,
        details={
            "p_value": round(p_value, 6),
            "historical_mean_pass_rate": round(float(hist_rates.mean()), 4),
            "current_mean_pass_rate": round(mean, 4),
        },
    )
