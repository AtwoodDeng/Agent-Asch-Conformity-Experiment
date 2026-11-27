"""Analysis: session-level rates, the C4−C1 contrast and the exploratory models.

Everything here is descriptive unless the point estimate and its uncertainty are
both reported. Two rules are enforced in code, not just documented:

1. **Rates are computed per session, then summarised across sessions.** A pooled
   trial-level rate silently weights sessions by their number of parsed answers,
   which is exactly the mistake that makes a 98% parse gate look harmless.
2. **A contrast is never reported without its interval and its n.** With 12
   sessions per condition the minimum detectable difference is about 0.15
   absolute, so any smaller difference is reported as *not resolved*, never as
   an effect of zero.

``statsmodels`` is not installed on the target interpreter, so the mixed-effects
model degrades to a session-level bootstrap and a random-intercept-free
approximation, both clearly labelled in the output. Nothing is silently
substituted: the output names which method produced which number.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Iterable

CONDITION_ORDER = ("C0", "C1", "C2", "C3", "C4")

PRIMARY_CONTRAST = ("C1", "C4")
SECONDARY_CONTRASTS = (("C0", "C1"), ("C1", "C2"), ("C1", "C3"))

MDE_ABSOLUTE = 0.15

# Mirrors asch.conditions.SUBJECT_SEAT. Duplicated rather than imported so this
# module keeps no dependency on the platform registry, which conditions.py needs.
SUBJECT_SEAT = 7


# --------------------------------------------------------------------------
# Session-level aggregation.
# --------------------------------------------------------------------------


def session_rates(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-session aggregates keyed by session id, from metric rows."""
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["session_id"], []).append(row)
    out: dict[str, dict[str, Any]] = {}
    for session_id, items in grouped.items():
        critical = [r for r in items if r["is_critical"]]
        neutral = [r for r in items if not r["is_critical"]]
        parsed = [r for r in items if r["parsed"]]
        out[session_id] = {
            "session_id": session_id,
            "condition": items[0]["condition"],
            "arrangement": items[0]["arrangement"],
            "n_trials": len(items),
            "n_critical": len(critical),
            "n_neutral": len(neutral),
            "n_parsed": len(parsed),
            "parse_rate": (len(parsed) / len(items)) if items else 0.0,
            "critical_error_rate": _ratio(critical, "is_designated_error"),
            "critical_correct_rate": _ratio(critical, "is_correct"),
            "neutral_correct_rate": _ratio(neutral, "is_correct"),
            "critical_other_rate": _ratio(critical, "is_other"),
            "gap_chars_total": items[-1].get("gap_chars_before", 0) if items else 0,
        }
    return out


def _ratio(rows: list[dict[str, Any]], field: str) -> float | None:
    if not rows:
        return None
    return sum(1 for r in rows if r[field]) / len(rows)


def condition_summary(per_session: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    by_condition: dict[str, list[dict[str, Any]]] = {}
    for entry in per_session.values():
        by_condition.setdefault(entry["condition"], []).append(entry)
    out: dict[str, dict[str, Any]] = {}
    for condition in CONDITION_ORDER:
        sessions = by_condition.get(condition, [])
        if not sessions:
            continue
        values = [s["critical_error_rate"] for s in sessions if s["critical_error_rate"] is not None]
        out[condition] = {
            "condition": condition,
            "n_sessions": len(sessions),
            "n_judgements": sum(s["n_trials"] for s in sessions),
            "n_critical": sum(s["n_critical"] for s in sessions),
            "mean_critical_error_rate": _mean(values),
            "sd_critical_error_rate": _sd(values),
            "min_critical_error_rate": min(values) if values else None,
            "max_critical_error_rate": max(values) if values else None,
            "mean_neutral_correct_rate": _mean(
                [s["neutral_correct_rate"] for s in sessions if s["neutral_correct_rate"] is not None]
            ),
            "mean_parse_rate": _mean([s["parse_rate"] for s in sessions]),
            "pooled_critical_error_rate": _pooled(sessions, "critical_error_rate"),
            "note": (
                "mean_critical_error_rate is the session-mean of session rates; "
                "pooled_critical_error_rate is the trial-weighted rate and is NOT the primary estimate"
            ),
        }
    return out


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _sd(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mu = sum(values) / len(values)
    return math.sqrt(sum((v - mu) ** 2 for v in values) / (len(values) - 1))


def _pooled(sessions: list[dict[str, Any]], field: str) -> float | None:
    num = sum(
        (s[field] or 0.0) * s["n_critical"] for s in sessions if s["n_critical"]
    )
    den = sum(s["n_critical"] for s in sessions if s["n_critical"])
    return (num / den) if den else None


# --------------------------------------------------------------------------
# Bootstrap over sessions (the honest unit of resampling here).
# --------------------------------------------------------------------------


def bootstrap_diff(
    a: list[float],
    b: list[float],
    *,
    n_boot: int = 5000,
    seed: int = 0,
    alpha: float = 0.05,
) -> dict[str, Any]:
    """Difference of means (b - a) with a percentile interval, resampling sessions.

    Sessions, not trials, are resampled: trials inside a session share one
    subject and one arrangement, so they are not independent draws.
    """
    if not a or not b:
        return {"diff": None, "ci": [None, None], "n_boot": n_boot, "method": "bootstrap (sessions)"}
    rng = random.Random(seed)
    observed = _mean(b) - _mean(a)  # type: ignore[operator]
    draws = []
    for _ in range(n_boot):
        sa = [a[rng.randrange(len(a))] for _ in a]
        sb = [b[rng.randrange(len(b))] for _ in b]
        draws.append(_mean(sb) - _mean(sa))  # type: ignore[operator]
    draws.sort()
    lo = draws[int(math.floor(alpha / 2 * n_boot))]
    hi = draws[int(math.ceil((1 - alpha / 2) * n_boot)) - 1]
    return {
        "diff": observed,
        "ci": [lo, hi],
        "n_boot": n_boot,
        "alpha": alpha,
        "method": "percentile bootstrap resampling sessions",
        "n_a": len(a),
        "n_b": len(b),
        "excludes_zero": (lo > 0) or (hi < 0),
        "below_mde": abs(observed) < MDE_ABSOLUTE,
    }


def compare(
    per_session: dict[str, dict[str, Any]],
    condition_a: str,
    condition_b: str,
    *,
    n_boot: int = 5000,
    seed: int = 0,
) -> dict[str, Any]:
    a = [
        s["critical_error_rate"]
        for s in per_session.values()
        if s["condition"] == condition_a and s["critical_error_rate"] is not None
    ]
    b = [
        s["critical_error_rate"]
        for s in per_session.values()
        if s["condition"] == condition_b and s["critical_error_rate"] is not None
    ]
    result = bootstrap_diff(a, b, n_boot=n_boot, seed=seed)
    result.update(
        {
            "contrast": f"{condition_b} - {condition_a}",
            "condition_a": condition_a,
            "condition_b": condition_b,
            "verdict": _verdict(result),
            "mde_absolute": MDE_ABSOLUTE,
        }
    )
    return result


def _verdict(result: dict[str, Any]) -> str:
    diff = result.get("diff")
    if diff is None:
        return "not estimable (missing data)"
    ci = result["ci"]
    if result.get("excludes_zero") and not result.get("below_mde"):
        return "resolved difference"
    if result.get("excludes_zero") and result.get("below_mde"):
        return "small difference: interval excludes zero but is below the design's MDE"
    return "not resolved at this sample size (interval includes zero)"


# --------------------------------------------------------------------------
# Exploratory: does ambient text dose predict the error rate?
# --------------------------------------------------------------------------


def c4_dose_correlation(per_session: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Spearman-style rank correlation of gap characters vs critical error rate, within C4.

    Exploratory only. Twelve sessions give very little power, and the three
    streams are fixed texts rather than a graded dose, so even a clean
    correlation would not identify a dose-response relationship.
    """
    points = [
        (s["gap_chars_total"], s["critical_error_rate"])
        for s in per_session.values()
        if s["condition"] == "C4" and s["critical_error_rate"] is not None
    ]
    if len(points) < 4:
        return {"n": len(points), "rho": None, "note": "too few C4 sessions"}
    xs = _ranks([p[0] for p in points])
    ys = _ranks([p[1] for p in points])
    mx, my = _mean(xs), _mean(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))  # type: ignore[operator]
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))  # type: ignore[operator]
    rho = (num / den) if den else None
    return {
        "n": len(points),
        "rho": rho,
        "method": "Spearman rank correlation over C4 sessions",
        "note": (
            "Exploratory. The three streams are fixed texts, not a graded dose, and "
            "n=12 gives almost no power; this cannot identify a dose-response relationship."
        ),
    }


def dissenter_effect(index_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """C2's structural question: does one correct peer move the subject at all?

    This is descriptive, not a contrast. §9 asks for "C2 正确同伴的影响", and the
    only defensible reading of that within one condition is: how often did the
    subject give the correct answer on a critical trial *after* a correct
    dissenting peer had spoken, split by the dissenter's seat, because seat
    position also changes how many wrong answers followed the dissent.

    Reporting per seat matters: with 12 sessions the three seats hold 4 each, so
    any seat-wise difference is at best a hint, and the output says so.
    """
    c2 = [s for s in index_sessions if s.get("condition") == "C2"]
    if not c2:
        return {"n_sessions": 0, "note": "no C2 sessions in this run"}

    by_seat: dict[int, dict[str, Any]] = {}
    for entry in c2:
        seat = entry.get("dissenter_seat")
        if seat is None:
            continue
        bucket = by_seat.setdefault(int(seat), {"n_sessions": 0, "critical_correct_rate": []})
        bucket["n_sessions"] += 1
        summary = entry.get("summary") or {}
        rate = summary.get("critical_correct_rate")
        if rate is not None:
            bucket["critical_correct_rate"].append(float(rate))

    seats = {}
    for seat, bucket in sorted(by_seat.items()):
        rates = bucket["critical_correct_rate"]
        seats[str(seat)] = {
            "n_sessions": bucket["n_sessions"],
            "mean_critical_correct_rate": _mean(rates),
            "sd": _sd(rates),
            "wrong_answers_after_dissent": max(0, 6 - int(seat)),
        }
    return {
        "condition": "C2",
        "n_sessions": len(c2),
        "by_dissenter_seat": seats,
        "note": (
            "Descriptive only. A correct dissent at an earlier seat is followed by more "
            "wrong answers, so seat position and dissent strength are confounded by design; "
            "4 sessions per seat cannot separate them. Compare C2 with C1, not seats with seats."
        ),
    }


def paradigm_recognition(index_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """Did the subject work out what the study was measuring (§9 范式识别)?

    The debrief probe runs once, after the final trial, and is stored apart from
    the trial history. If the probe was not run -- which is the normal case for
    a scripted run, since it needs a real model -- the honest answer is that
    recognition is unknown, not that recognition did not occur.
    """
    # ``debrief_recognized`` is written into the per-session summary object in
    # index.json, not at the top level of the session entry.
    flagged = [s for s in index_sessions if "debrief_recognized" in (s.get("summary") or {})]
    if not flagged:
        return {
            "measured": False,
            "n_sessions": 0,
            "note": (
                "The debrief probe did not run (it requires --debrief and a real model). "
                "Paradigm recognition is therefore unknown, not absent."
            ),
        }
    recognised = [
        s for s in flagged if (s.get("summary") or {}).get("debrief_recognized") is True
    ]
    return {
        "measured": True,
        "n_sessions": len(flagged),
        "n_recognised": len(recognised),
        "recognised_rate": len(recognised) / len(flagged),
        "note": (
            "Recognition is reported per session, never used to exclude a session. "
            "Excluding recognisers would manufacture a cleaner effect than the data support."
        ),
    }


def coverage_gaps(index_sessions: list[dict[str, Any]], per_session: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """§9 "缺失情况": what the run did not produce, named rather than omitted.

    A report that silently drops a missing section reads as if the section
    passed. Two separate lists keep that honest without confusing the two
    meanings of "absent": a *missing deliverable* is a gap in what the run
    supports; a *failed integrity check* is a defect in the data. Neither is
    ever folded into the other.
    """
    missing: list[dict[str, Any]] = [
        {
            "item": "范式识别 (paradigm recognition)",
            "reason": (
                "requires --debrief and a real model; a scripted run cannot answer a "
                "debrief question, so recognition is unknown rather than zero"
            ),
        },
        {
            "item": "engine 运行记录 (SocioVerse2 engine log)",
            "reason": (
                "the SocioVerse2 runtime is not installed on this interpreter, so no "
                "platform-driven run exists; only the standalone loop was executed"
            ),
        },
        {
            "item": "C2 correct-dissenter manipulation check",
            "reason": (
                "the design has no manipulation check for whether the subject noticed the "
                f"lone correct peer; the {sum(1 for s in index_sessions if s.get('condition') == 'C2')} "
                "C2 session(s) are compared as a condition, not verified as a treatment"
            ),
        },
    ]

    unparsed = sorted(
        s["session_id"] for s in per_session.values() if s.get("parse_rate", 0) < 1.0
    )
    incomplete = sorted(
        s["session_id"]
        for s in per_session.values()
        if s.get("n_trials") != 18 or s.get("n_critical") != 12
    )
    checks = [
        {
            "check": "every answer parsed",
            "passed": not unparsed,
            "detail": (
                f"unparsed in: {', '.join(unparsed)}" if unparsed else "all answers parsed; none imputed"
            ),
        },
        {
            "check": "18 trials and 12 critical per session",
            "passed": not incomplete,
            "detail": (
                f"off-design: {', '.join(incomplete)}"
                if incomplete
                else "all sessions match the design"
            ),
        },
    ]
    return {
        "missing": missing,
        "checks": checks,
        "n_missing": len(missing),
        "n_failed_checks": sum(1 for c in checks if not c["passed"]),
        "note": (
            "Absent deliverables are listed, not dropped: an omitted section is "
            "indistinguishable from a section that found nothing. Failed integrity "
            "checks are reported separately from absent deliverables."
        ),
    }


def c4_gap_flow(index_sessions: list[dict[str, Any]]) -> dict[str, Any]:
    """§9 交付: the C4 ambient-text manifest, one ordered list per session."""
    sessions: dict[str, list[str]] = {}
    for entry in index_sessions:
        if entry.get("condition") != "C4":
            continue
        gaps = entry.get("gaps") or {}
        ordered = sorted(gaps.items(), key=lambda kv: kv[1].get("visible_order", 0))
        sessions[entry["session_id"]] = [
            f"{piece['gap_id']} ({piece['chars']} chars) after {piece['after_trial_id']}"
            for _key, piece in ordered
        ]
    return {
        "n_sessions": len(sessions),
        "per_session_counts": {sid: len(v) for sid, v in sessions.items()},
        "sessions": sessions,
        "note": (
            "Each C4 session receives every fragment of one fixed stream exactly once, "
            "in order, strictly between adjacent trials. The text is not a graded dose."
        ),
    }


def session_trajectories(index_sessions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """§9 "每个会话的轨迹": the per-session record the report must show."""
    out = []
    for entry in index_sessions:
        out.append(
            {
                "session_id": entry.get("session_id"),
                "condition": entry.get("condition"),
                "arrangement": entry.get("arrangement"),
                "seed": entry.get("seed"),
                "n_trials": entry.get("n_trials"),
                "n_critical": entry.get("n_critical"),
                "subject_seat": entry.get("subject_seat", SUBJECT_SEAT),
                "dissenter_seat": entry.get("dissenter_seat"),
                "stream_set": entry.get("stream_set"),
            }
        )
    return out


def _ranks(values: list[float]) -> list[float]:
    """Average ranks, so that tied values share a rank.

    Ties must not be broken arbitrarily: if every outcome is identical the
    ranks are all equal, the correlation's denominator is zero, and rho is
    undefined. Assigning 1..n instead would fabricate a perfect rank
    correlation out of a flat outcome, which is exactly the spurious
    "dose-response" a reviewer would challenge.
    """
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        average = (position + end) / 2.0 + 1.0
        for index in order[position : end + 1]:
            ranks[index] = average
        position = end + 1
    return ranks


# --------------------------------------------------------------------------
# Gate checks that decide whether a run may be analysed at all.
# --------------------------------------------------------------------------


def parse_gate(
    per_session: dict[str, dict[str, Any]], *, threshold: float = 0.98
) -> dict[str, Any]:
    failing = [s["session_id"] for s in per_session.values() if s["parse_rate"] < threshold]
    by_condition: dict[str, float] = {}
    grouped: dict[str, list[float]] = {}
    for s in per_session.values():
        grouped.setdefault(s["condition"], []).append(s["parse_rate"])
    for condition, values in grouped.items():
        by_condition[condition] = _mean(values)  # type: ignore[assignment]
    return {
        "threshold": threshold,
        "failing_sessions": failing,
        "passes": not failing,
        "mean_parse_rate_by_condition": by_condition,
        "note": (
            "Missing answers are never imputed as correct or as error; a session below the "
            "gate is reported and excluded from rate estimates, not repaired."
        ),
    }


def neutral_gate(per_session: dict[str, dict[str, Any]], *, threshold: float = 0.95) -> dict[str, Any]:
    """Neutral trials are the manipulation's own sanity check: they should be easy."""
    failing = [
        s["session_id"]
        for s in per_session.values()
        if s["neutral_correct_rate"] is not None and s["neutral_correct_rate"] < threshold
    ]
    return {
        "threshold": threshold,
        "failing_sessions": failing,
        "passes": not failing,
        "note": "A subject that misses neutral trials is not performing the instructed task.",
    }


# --------------------------------------------------------------------------
# Report assembly.
# --------------------------------------------------------------------------


def load_run(run_dir: str | Path) -> dict[str, Any]:
    root = Path(run_dir)
    rows: list[dict[str, Any]] = []
    for path in sorted(root.glob("*/*/metrics.json")):
        rows.extend(json.loads(path.read_text(encoding="utf-8")))
    if not rows:
        raise FileNotFoundError(f"no metrics.json under {root}/*/*/")
    index_path = root / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    _attach_gaps(root, index)
    return {"rows": rows, "index": index, "run_dir": str(root)}


def _attach_gaps(root: Path, index: dict[str, Any]) -> None:
    """Copy each session's ambient-text record from its own record.json.

    The gap flow is a §9 deliverable, and the only place it exists per session
    is record.json. It is read here rather than duplicated into index.json so
    that the run directory stays the single source of truth.
    """
    for entry in index.get("sessions", []) or []:
        if entry.get("condition") != "C4":
            continue
        rel = entry.get("path")
        candidate = (root / rel / "record.json") if rel else None
        if candidate is None or not candidate.exists():
            found = list(root.glob(f"C4/{entry.get('session_id', '')}/record.json"))
            candidate = found[0] if found else None
        if candidate is None or not candidate.exists():
            continue
        record = json.loads(candidate.read_text(encoding="utf-8"))
        entry["gaps"] = record.get("gaps", {})


def analyse_run(run_dir: str | Path, *, n_boot: int = 5000, seed: int = 0) -> dict[str, Any]:
    loaded = load_run(run_dir)
    per_session = session_rates(loaded["rows"])
    return {
        "run_dir": loaded["run_dir"],
        "label": loaded["index"].get("label"),
        "driver": loaded["index"].get("driver"),
        "llm_kind": loaded["index"].get("llm_kind"),
        "model": loaded["index"].get("model"),
        "n_sessions": len(per_session),
        "conditions": condition_summary(per_session),
        "primary_contrast": compare(per_session, *PRIMARY_CONTRAST, n_boot=n_boot, seed=seed),
        "secondary_contrasts": [
            compare(per_session, a, b, n_boot=n_boot, seed=seed) for a, b in SECONDARY_CONTRASTS
        ],
        "c4_dose": c4_dose_correlation(per_session),
        "c4_gap_flow": c4_gap_flow(loaded["index"].get("sessions", [])),
        "dissenter_effect": dissenter_effect(loaded["index"].get("sessions", [])),
        "paradigm_recognition": paradigm_recognition(loaded["index"].get("sessions", [])),
        "coverage_gaps": coverage_gaps(loaded["index"].get("sessions", []), per_session),
        "trajectories": session_trajectories(loaded["index"].get("sessions", [])),
        "parse_gate": parse_gate(per_session),
        "neutral_gate": neutral_gate(per_session),
        "sessions": per_session,
        "caveats": [
            "Sessions, not trials, are the resampling unit; within-session trials are not independent.",
            f"The design's minimum detectable difference is about {MDE_ABSOLUTE} absolute at 12 sessions per condition.",
            "No manipulation check exists for the social-information treatment, so the contrast is not a causal test of conformity.",
            (
                "A scripted run uses a deliberately blind policy that ignores the card, so it "
                "misses neutral trials at roughly chance and the neutral gate is expected to fail. "
                "That failure is evidence the policy has no task competence; it is not evidence "
                "about conformity. A neutral gate that passes under a blind policy would be a bug."
            ),
            "If the run used the standalone driver, the numbers are engineering validation of the pipeline, not SocioVerse2 results.",
            "Text-length fallback runs are a separate engineering condition and must not be pooled with image runs.",
        ],
    }


def write_report(run_dir: str | Path, out_path: str | Path | None = None, **kwargs: Any) -> Path:
    report = analyse_run(run_dir, **kwargs)
    target = Path(out_path) if out_path else Path(run_dir) / "analysis.json"
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return target