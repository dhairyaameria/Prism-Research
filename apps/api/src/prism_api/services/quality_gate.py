"""Post-run quality gate (supervisor-lite): structured checks before marking a run complete."""

from __future__ import annotations

from typing import Any


def evaluate_thesis_quality(
    *,
    thesis: dict[str, Any],
    contradiction_count: int,
    claim_count: int | None = None,
) -> tuple[bool, dict[str, Any]]:
    """Return (passed, report). Fail on empty narrative; fail on empty matrix only if claims were expected."""
    reasons: list[str] = []
    narrative = (thesis.get("narrative") or "").strip()
    if not narrative:
        reasons.append("missing_narrative")
    rows = thesis.get("matrix_rows") or []
    expect_matrix = claim_count is None or claim_count > 0
    if expect_matrix and (not isinstance(rows, list) or len(rows) == 0):
        reasons.append("empty_matrix_rows")
    warnings: list[str] = []
    if contradiction_count == 0:
        warnings.append("no_contradictions_recorded")
    if claim_count == 0:
        warnings.append("no_claims_from_analysis")

    passed = len(reasons) == 0
    report: dict[str, Any] = {
        "passed": passed,
        "reasons": reasons,
        "warnings": warnings,
        "contradiction_count": contradiction_count,
        "claim_count": claim_count,
    }
    return passed, report
