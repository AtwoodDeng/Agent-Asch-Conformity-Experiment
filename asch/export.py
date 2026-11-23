"""Export: flat tables for inspection, and a markdown summary of one run.

The export deliberately does not compute a headline number. It emits the
per-trial table, the per-session table and a markdown digest that restates the
label of the run (engine vs standalone) on the same page as any rate it quotes,
because the plan's rule is that a standalone run's numbers can never be read as
SocioVerse2 results (§6).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from asch.analysis import (
    MDE_ABSOLUTE,
    analyse_run,
    condition_summary,
    session_rates,
)


TRIAL_COLUMNS = (
    "session_id",
    "condition",
    "arrangement",
    "step",
    "trial_id",
    "trial_kind",
    "is_critical",
    "answer",
    "parsed",
    "is_correct",
    "is_designated_error",
    "is_other",
    "peer_majority",
    "peer_majority_is_error",
    "n_peers_shown",
    "gaps_shown_before",
    "gap_chars_before",
    "action_source",
)

SESSION_COLUMNS = (
    "session_id",
    "condition",
    "arrangement",
    "n_trials",
    "n_critical",
    "n_parsed",
    "parse_rate",
    "critical_error_rate",
    "critical_correct_rate",
    "neutral_correct_rate",
    "critical_other_rate",
    "gap_chars_total",
)


def write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def render_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Asch run summary")
    lines.append("")
    lines.append(f"- run: `{report['run_dir']}`")
    lines.append(f"- driver: `{report['driver']}`")
    lines.append(f"- llm_kind: `{report['llm_kind']}` (model: `{report['model']}`)")
    lines.append(f"- sessions: {report['n_sessions']}")
    lines.append(f"- label: **{report['label']}**")
    lines.append("")

    if report.get("driver") == "standalone":
        lines.append(
            "> These numbers come from the standalone loop. They validate the pipeline "
            "(routing, prompts, metrics, export); they are **not** SocioVerse2 engine "
            "results and must not be reported as conformity findings."
        )
        lines.append("")

    lines.append("## Condition summary")
    lines.append("")
    lines.append(
        "| condition | sessions | critical judgements | mean critical error rate | sd | neutral correct | parse rate |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for condition, entry in report["conditions"].items():
        lines.append(
            "| {c} | {n} | {k} | {m} | {sd} | {nu} | {p} |".format(
                c=condition,
                n=entry["n_sessions"],
                k=entry["n_critical"],
                m=_fmt(entry["mean_critical_error_rate"]),
                sd=_fmt(entry["sd_critical_error_rate"]),
                nu=_fmt(entry["mean_neutral_correct_rate"]),
                p=_fmt(entry["mean_parse_rate"]),
            )
        )
    lines.append("")

    primary = report["primary_contrast"]
    lines.append("## Primary contrast (C4 − C1)")
    lines.append("")
    lo, hi = primary["ci"]
    lines.append(
        f"- difference: {_fmt(primary['diff'])} "
        f"(95% bootstrap interval {_fmt(lo)} to {_fmt(hi)}, {primary['n_boot']} resamples)"
    )
    lines.append(f"- verdict: {primary['verdict']}")
    lines.append(f"- design MDE: about {MDE_ABSOLUTE} absolute")
    lines.append("")

    lines.append("## Secondary contrasts")
    lines.append("")
    for entry in report["secondary_contrasts"]:
        lo, hi = entry["ci"]
        lines.append(
            f"- {entry['contrast']}: {_fmt(entry['diff'])} "
            f"[{_fmt(lo)}, {_fmt(hi)}] — {entry['verdict']}"
        )
    lines.append("")

    dose = report["c4_dose"]
    lines.append("## C4 ambient-text dose (exploratory)")
    lines.append("")
    lines.append(f"- n = {dose.get('n')}, rho = {_fmt(dose.get('rho'))}")
    lines.append(f"- {dose.get('note')}")
    lines.append("")

    for gate_key, title in (("parse_gate", "Parse gate"), ("neutral_gate", "Neutral-trial gate")):
        gate = report[gate_key]
        lines.append(f"## {title}")
        lines.append("")
        lines.append(f"- passes: **{gate['passes']}**")
        if gate["failing_sessions"]:
            failing = gate["failing_sessions"]
            shown = ", ".join(failing[:8])
            suffix = "" if len(failing) <= 8 else f" … (+{len(failing) - 8} more)"
            lines.append(f"- failing sessions ({len(failing)}): {shown}{suffix}")
        lines.append(f"- {gate['note']}")
        lines.append("")

    dissenter = report.get("dissenter_effect") or {}
    lines.append("## C2 correct-dissenter breakdown")
    lines.append("")
    if dissenter.get("by_dissenter_seat"):
        lines.append("| dissenter seat | sessions | mean critical correct rate | sd | wrong answers after dissent |")
        lines.append("|---|---|---|---|---|")
        for seat, entry in dissenter["by_dissenter_seat"].items():
            lines.append(
                "| {s} | {n} | {m} | {sd} | {w} |".format(
                    s=seat,
                    n=entry["n_sessions"],
                    m=_fmt(entry["mean_critical_correct_rate"]),
                    sd=_fmt(entry["sd"]),
                    w=entry["wrong_answers_after_dissent"],
                )
            )
        lines.append("")
    lines.append(f"- {dissenter.get('note')}")
    lines.append("")

    recognition = report.get("paradigm_recognition") or {}
    lines.append("## Paradigm recognition")
    lines.append("")
    if recognition.get("measured"):
        lines.append(
            f"- sessions with a debrief record: {recognition['n_sessions']}, "
            f"recognised the paradigm: {recognition['n_recognised']} "
            f"({_fmt(recognition['recognised_rate'])})"
        )
    else:
        lines.append("- not measured")
    lines.append(f"- {recognition.get('note')}")
    lines.append("")

    flow = report.get("c4_gap_flow") or {}
    lines.append("## C4 ambient-text flow (§9 信息流清单)")
    lines.append("")
    if flow.get("per_session_counts"):
        lines.append(f"- sessions: {flow['n_sessions']}, pieces per session: "
                     f"{sorted(set(flow['per_session_counts'].values()))}")
        first_id = sorted(flow["sessions"])[0]
        lines.append("")
        lines.append(f"Ordered flow for {first_id} (one stream, every piece once):")
        lines.append("")
        for rank, piece in enumerate(flow["sessions"][first_id], start=1):
            lines.append(f"{rank}. {piece}")
    else:
        lines.append("- no C4 sessions in this run")
    lines.append("")
    lines.append(f"- {flow.get('note')}")
    lines.append("")

    gaps = report.get("coverage_gaps") or {}
    lines.append("## Missing material (§9 缺失情况)")
    lines.append("")
    lines.append("Not produced by this run:")
    lines.append("")
    for item in gaps.get("missing", []):
        lines.append(f"- **ABSENT** {item['item']} — {item['reason']}")
    lines.append("")
    lines.append("Integrity checks:")
    lines.append("")
    for check in gaps.get("checks", []):
        mark = "passed" if check["passed"] else "**FAILED**"
        lines.append(f"- {check['check']}: {mark} — {check['detail']}")
    lines.append(f"- {gaps.get('note')}")
    lines.append("")

    trajectories = report.get("trajectories") or []
    lines.append("## Session trajectories")
    lines.append("")
    if trajectories:
        lines.append("| session | condition | arrangement | seed | subject seat | dissenter | stream |")
        lines.append("|---|---|---|---|---|---|---|")
        for row in trajectories:
            lines.append(
                "| {sid} | {c} | {a} | {seed} | {ss} | {ds} | {st} |".format(
                    sid=row["session_id"],
                    c=row["condition"],
                    a=row["arrangement"],
                    seed=row["seed"],
                    ss=row["subject_seat"],
                    ds=row["dissenter_seat"] if row["dissenter_seat"] is not None else "—",
                    st=row["stream_set"] if row["stream_set"] is not None else "—",
                )
            )
    lines.append("")
    lines.append(
        "Per-trial trajectories are in trials.csv; this table identifies which "
        "session is which so a row can be traced back to its condition record."
    )
    lines.append("")

    lines.append("## Caveats")
    lines.append("")
    for caveat in report["caveats"]:
        lines.append(f"- {caveat}")
    lines.append("")
    return "\n".join(lines)


def export_run(run_dir: str | Path, out_dir: str | Path | None = None, **kwargs: Any) -> dict[str, Any]:
    from asch.analysis import load_run

    loaded = load_run(run_dir)
    root = Path(out_dir) if out_dir else Path(run_dir) / "export"
    root.mkdir(parents=True, exist_ok=True)

    rows = loaded["rows"]
    per_session = session_rates(rows)
    n_trials = write_csv(root / "trials.csv", TRIAL_COLUMNS, rows)
    n_sessions = write_csv(root / "sessions.csv", SESSION_COLUMNS, list(per_session.values()))

    report = analyse_run(run_dir, **kwargs)
    (root / "analysis.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = render_markdown(report)
    (root / "SUMMARY.md").write_text(markdown, encoding="utf-8")
    return {
        "dir": str(root),
        "trials": n_trials,
        "sessions": n_sessions,
        "markdown": str(root / "SUMMARY.md"),
    }