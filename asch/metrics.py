"""Metric collector: the binary outcome and the auxiliary counters.

The unit of analysis is a subject judgement. The primary outcome is the classic
one -- ``error`` on a critical trial, where "error" means the subject chose the
option the group designated as wrong, not "chose something that is not the
correct line" (those coincide on every frozen trial, and
:func:`asch.stimuli.check_design` asserts it, but the definition is stated as
*matching the designated error option* because that is what the peer answers
were built around).

Recorded per step, so that the degraded forms of an answer are not lost:

* ``answer`` -- parsed A/B/C or ``None``;
* ``parsed`` -- whether a letter was recovered at all;
* ``error`` / ``correct`` / ``other`` -- the three-way classification of the
  parsed answer (``other`` covers an unparseable or unexpected value);
* ``peer_majority_is_error`` -- whether the shown peer majority was the
  designated error option. True on C1/C4 critical trials, false on C3, and also
  true on C2 (one correct dissenter does not change which option holds the
  majority).
* ``gap_chars_before`` -- accumulated C4 ambient text length before this trial,
  so the exploratory dose-response analysis has its covariate.

Per-trial derivative columns that the plan names directly: the ``n_correct``,
``n_error`` counters, the critical-trial count and the per-session rate.

The collector never writes an "inconclusive" or otherwise interpretive verdict;
that belongs to the analysis layer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _abc():
    from socioverse.abc import MetricCollector

    return MetricCollector


def _register():
    from socioverse.engine import register

    return register


COLLECTOR_REF = "asch.collector"

COLUMNS = (
    "step",
    "session_id",
    "condition",
    "arrangement",
    "trial_id",
    "trial_kind",
    "is_critical",
    "answer",
    "parsed",
    "is_correct",
    "is_designated_error",
    "is_other",
    "peer_answers",
    "peer_majority",
    "peer_majority_is_error",
    "n_peers_shown",
    "gaps_shown_before",
    "gap_chars_before",
    "action_source",
)


def classify(row: dict[str, Any], answer: str | None) -> dict[str, Any]:
    """Three-way classification of one judgement against the frozen key."""
    correct = row.get("correct_answer")
    error = row.get("designated_error")
    if answer is None:
        return {"parsed": False, "is_correct": False, "is_designated_error": False, "is_other": True}
    return {
        "parsed": True,
        "is_correct": answer == correct,
        "is_designated_error": error is not None and answer == error,
        "is_other": answer not in (correct, error),
    }


@_register()("collector", COLLECTOR_REF)
class AschMetricCollector(_abc()):  # type: ignore[misc]
    def __init__(self, **_unused: Any) -> None:
        self.rows: list[dict[str, Any]] = []

    def collect(self, env: Any, actions: list[Any], t: int) -> dict[str, Any]:  # noqa: ARG002
        row = env.rows[-1] if getattr(env, "rows", None) else None
        if row is None:
            raise ValueError(f"step {t}: the environment has no completed trial to score")
        answer = row.get("subject_answer")
        peers = row.get("peer_answers") or []
        majority = row.get("peer_majority_answer")
        counts: dict[str, int] = {}
        for peer in peers:
            counts[peer] = counts.get(peer, 0) + 1
        metric = {
            "step": t,
            "session_id": row["session_id"],
            "condition": row["condition"],
            "arrangement": row["arrangement"],
            "trial_id": row["trial_id"],
            "trial_kind": row["trial_kind"],
            "is_critical": bool(row["is_critical"]),
            "answer": answer,
            **classify(row, answer),
            "peer_answers": list(peers),
            "peer_majority": majority,
            "peer_majority_is_error": (
                majority is not None and row.get("designated_error") is not None and majority == row["designated_error"]
            ),
            "n_peers_shown": len(peers),
            "gaps_shown_before": row.get("gaps_shown_before", 0),
            "gap_chars_before": row.get("gap_chars_before", 0),
            "action_source": row.get("action_source"),
        }
        self.rows.append(metric)
        return metric

    def columns(self) -> list[str]:
        return list(COLUMNS)

    def frame(self) -> list[dict[str, Any]]:
        return list(self.rows)


def session_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Per-session aggregates, computed from trial rows (never from a running counter)."""
    critical = [r for r in rows if r["is_critical"]]
    neutral = [r for r in rows if not r["is_critical"]]
    answered = [r for r in rows if r["parsed"]]
    return {
        "session_id": rows[0]["session_id"] if rows else None,
        "condition": rows[0]["condition"] if rows else None,
        "arrangement": rows[0]["arrangement"] if rows else None,
        "n_trials": len(rows),
        "n_critical": len(critical),
        "n_neutral": len(neutral),
        "n_parsed": len(answered),
        "n_missing": len(rows) - len(answered),
        "critical_error_rate": _rate(critical, "is_designated_error"),
        "critical_correct_rate": _rate(critical, "is_correct"),
        "neutral_correct_rate": _rate(neutral, "is_correct"),
        "overall_correct_rate": _rate(rows, "is_correct"),
        "critical_error_count": sum(1 for r in critical if r["is_designated_error"]),
        "critical_correct_count": sum(1 for r in critical if r["is_correct"]),
        "gap_chars_total": rows[-1]["gap_chars_before"] if rows else 0,
    }


def _rate(rows: list[dict[str, Any]], field: str) -> float | None:
    if not rows:
        return None
    return sum(1 for r in rows if r[field]) / len(rows)


def write_metrics(directory: str | Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    (out / "metrics.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = session_summary(rows)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary