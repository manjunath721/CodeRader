"""
Knowledge drift detection — methodology.md §6.

Given a time series of a developer's knowledge share (%) on a module across
monthly checkpoints, flags a rising-concentration trend.
"""
from dataclasses import dataclass


@dataclass
class DriftPoint:
    period_label: str  # e.g. "2026-01"
    share_pct: float


@dataclass
class DriftResult:
    module_id: str
    developer_id: str
    increasing: bool
    trend: list[DriftPoint]
    message: str | None


def detect_drift(
    module_id: str, developer_id: str, series: list[DriftPoint], threshold_pp: float = 10.0, min_consecutive: int = 3
) -> DriftResult:
    """
    Flags "increasing concentration" when share rises by >= threshold_pp
    percentage points over `min_consecutive` consecutive checkpoints.
    """
    if len(series) < min_consecutive:
        return DriftResult(module_id, developer_id, False, series, None)

    window = series[-min_consecutive:]
    rising = all(window[i].share_pct <= window[i + 1].share_pct for i in range(len(window) - 1))
    delta = window[-1].share_pct - window[0].share_pct
    increasing = rising and delta >= threshold_pp

    message = None
    if increasing:
        message = (
            f"Knowledge concentration for this module is increasing: "
            f"{window[0].period_label} {window[0].share_pct:.0f}% -> "
            f"{window[-1].period_label} {window[-1].share_pct:.0f}%."
        )
    return DriftResult(module_id, developer_id, increasing, series, message)
