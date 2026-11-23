"""Analysis must not manufacture a result.

The dangerous failure for a conformity study is a pipeline that reports a
difference when the decision rule is blind. These tests pin the statistics to
the properties the planning document demands: sessions are the resampling unit,
an all-null grid comes back unresolved, and a broken neutral gate is visible.
"""

import pytest

from asch.analysis import (
    MDE_ABSOLUTE,
    bootstrap_diff,
    c4_dose_correlation,
    compare,
    condition_summary,
    dissenter_effect,
    neutral_gate,
    paradigm_recognition,
    parse_gate,
    session_rates,
)
from asch.metrics import classify


def _rows(condition, index, answers, arrangement="A1"):
    """Metric rows shaped like the collector's output."""
    return [
        {
            "session_id": f"{condition}-S{index + 1:02d}",
            "condition": condition,
            "arrangement": arrangement,
            "trial_index": i + 1,
            "is_critical": i < 12,
            "is_correct": answers[i] == "B",
            "is_designated_error": answers[i] == "A",
            "is_other": answers[i] == "C",
            "parsed": answers[i] in ("A", "B", "C"),
            "answer": answers[i],
            "gap_chars_before": 100 * index,
        }
        for i in range(18)
    ]


def _uniform_sessions(condition, rate, *, neutral=1.0, parse=1.0, n=12):
    return {
        f"{condition}-S{i + 1:02d}": {
            "session_id": f"{condition}-S{i + 1:02d}",
            "condition": condition,
            "critical_error_rate": rate,
            "neutral_correct_rate": neutral,
            "parse_rate": parse,
        }
        for i in range(n)
    }


# --------------------------------------------------------------------------
# Session-level aggregation.
# --------------------------------------------------------------------------


def test_session_rates_use_twelve_critical_trials_only():
    rows = _rows("C1", 0, ["A"] * 12 + ["B"] * 6)
    rates = session_rates(rows)
    assert len(rates) == 1
    only = rates["C1-S01"]
    assert only["n_critical"] == 12
    assert only["n_neutral"] == 6
    assert only["critical_error_rate"] == 1.0
    assert only["neutral_correct_rate"] == 1.0


def test_session_rates_count_each_session_separately():
    rows = _rows("C1", 0, ["A"] * 18) + _rows("C1", 1, ["B"] * 18)
    rates = session_rates(rows)
    assert len(rates) == 2
    assert rates["C1-S01"]["critical_error_rate"] == 1.0
    assert rates["C1-S02"]["critical_error_rate"] == 0.0


# --------------------------------------------------------------------------
# Bootstrap: sessions are the unit.
# --------------------------------------------------------------------------


def test_bootstrap_interval_covers_zero_for_identical_conditions():
    a = [0.3] * 12
    b = [0.3] * 12
    result = bootstrap_diff(a, b, n_boot=2000, seed=7)
    assert result["diff"] == 0.0
    assert result["ci"][0] <= 0.0 <= result["ci"][1]
    assert result["excludes_zero"] is False


def test_bootstrap_resamples_sessions_not_trials():
    """Constant input must give a zero-width interval.

    If trials were the resampling unit the interval would pick up trial-level
    noise even though every session holds the same value. Zero width proves the
    unit is the session, which §8 L175 requires because the twelve trials inside
    one session are not independent observations.
    """
    result = bootstrap_diff([0.5] * 12, [0.5] * 12, n_boot=500, seed=3)
    assert result["diff"] == 0.0
    assert result["ci"][0] == 0.0
    assert result["ci"][1] == 0.0


def test_a_large_consistent_difference_is_resolved():
    per_session = {**_uniform_sessions("C1", 0.35), **_uniform_sessions("C4", 0.05)}
    comparison = compare(per_session, "C1", "C4", n_boot=2000, seed=11)
    assert comparison["contrast"] == "C4 - C1"
    assert comparison["excludes_zero"] is True
    assert comparison["mde_absolute"] == MDE_ABSOLUTE
    assert comparison["verdict"] == "resolved difference"


def test_an_all_null_grid_is_reported_as_unresolved():
    """Every condition at the same rate must never be dressed up as an effect."""
    per_session = {}
    for condition in ("C0", "C1", "C2", "C3", "C4"):
        per_session.update(_uniform_sessions(condition, 1 / 3))
    for a, b in (("C1", "C4"), ("C0", "C1"), ("C1", "C2")):
        comparison = compare(per_session, a, b, n_boot=2000, seed=5)
        assert comparison["diff"] == 0.0
        assert "not resolved" in comparison["verdict"]


def test_a_tiny_consistent_gap_is_flagged_as_below_mde():
    """A 2-point gap excludes zero at n=12 only when it is perfectly consistent."""
    per_session = {**_uniform_sessions("C1", 0.32), **_uniform_sessions("C4", 0.30)}
    comparison = compare(per_session, "C1", "C4", n_boot=2000, seed=2)
    if comparison["excludes_zero"]:
        assert comparison["below_mde"] is True
        assert "below the design's MDE" in comparison["verdict"]


def test_bootstrap_reports_its_own_uncertainty_settings():
    result = bootstrap_diff([0.1] * 12, [0.4] * 12, n_boot=1000, seed=1, alpha=0.05)
    assert result["n_boot"] == 1000
    assert result["alpha"] == 0.05
    assert result["n_a"] == 12 and result["n_b"] == 12
    assert "session" in result["method"]


# --------------------------------------------------------------------------
# Reporting honesty.
# --------------------------------------------------------------------------


def test_condition_summary_reports_the_session_mean_as_primary():
    per_session = {
        f"C1-S{i + 1:02d}": {
            "session_id": f"C1-S{i + 1:02d}",
            "condition": "C1",
            "n_trials": 18,
            "n_critical": 12,
            "critical_error_rate": 0.0 if i == 0 else 1.0,
            "neutral_correct_rate": 1.0,
            "parse_rate": 1.0,
        }
        for i in range(12)
    }
    summary = condition_summary(per_session)["C1"]
    assert abs(summary["mean_critical_error_rate"] - 11 / 12) < 1e-9
    assert summary["n_judgements"] == 216
    assert "pooled_critical_error_rate" in summary
    assert "NOT the primary estimate" in summary["note"]


def test_session_mean_and_pooled_rate_can_differ():
    """Two sessions with different trial counts must not silently coincide."""
    rows = []
    rows += [
        {
            "session_id": "C1-S01",
            "condition": "C1",
            "arrangement": "A1",
            "is_critical": True,
            "is_correct": False,
            "is_designated_error": True,
            "is_other": False,
            "parsed": True,
            "gap_chars_before": 0,
        }
    ]
    rows += [
        {
            "session_id": "C1-S02",
            "condition": "C1",
            "arrangement": "A1",
            "is_critical": True,
            "is_correct": True,
            "is_designated_error": False,
            "is_other": False,
            "parsed": True,
            "gap_chars_before": 0,
        }
    ] * 3
    summary = condition_summary(session_rates(rows))["C1"]
    assert summary["mean_critical_error_rate"] == 0.5
    assert abs(summary["pooled_critical_error_rate"] - 0.25) < 1e-9
    assert summary["mean_critical_error_rate"] != summary["pooled_critical_error_rate"]


# --------------------------------------------------------------------------
# Gates.
# --------------------------------------------------------------------------


def test_parse_gate_fails_when_answers_do_not_parse():
    bad = _uniform_sessions("C1", 0.3, parse=0.5)
    gate = parse_gate(bad)
    assert gate["passes"] is False
    assert len(gate["failing_sessions"]) == 12
    assert parse_gate(_uniform_sessions("C1", 0.3))["passes"] is True


def test_parse_gate_does_not_repair_missing_data():
    gate = parse_gate(_uniform_sessions("C1", 0.3, parse=0.5))
    assert "never imputed" in gate["note"]


def test_neutral_gate_catches_a_blind_policy():
    """A policy ignoring the stimulus answers neutral trials at chance (§7 L181)."""
    blind = _uniform_sessions("C1", 0.6, neutral=1 / 3)
    gate = neutral_gate(blind)
    assert gate["passes"] is False
    assert neutral_gate(_uniform_sessions("C1", 0.6))["passes"] is True


def test_gates_are_independent_of_each_other():
    """High parse rate with broken neutral trials must still fail the neutral gate."""
    per_session = _uniform_sessions("C1", 0.6, neutral=0.2, parse=1.0)
    assert parse_gate(per_session)["passes"] is True
    assert neutral_gate(per_session)["passes"] is False


# --------------------------------------------------------------------------
# The exploratory C4 dose check.
# --------------------------------------------------------------------------


def test_c4_dose_correlation_is_labelled_exploratory():
    sessions = {
        f"C4-S{i + 1:02d}": {
            "session_id": f"C4-S{i + 1:02d}",
            "condition": "C4",
            "gap_chars_total": 100 + i,
            "critical_error_rate": 0.2 + i / 100,
        }
        for i in range(12)
    }
    result = c4_dose_correlation(sessions)
    assert "Exploratory" in result["note"]
    assert result["n"] == 12


def test_c4_dose_correlation_ignores_other_conditions():
    sessions = {
        f"C1-S{i + 1:02d}": {
            "session_id": f"C1-S{i + 1:02d}",
            "condition": "C1",
            "gap_chars_total": 0,
            "critical_error_rate": 0.3,
        }
        for i in range(12)
    }
    result = c4_dose_correlation(sessions)
    assert result["n"] == 0
    assert result["rho"] is None


def test_c4_dose_correlation_detects_a_planted_monotone_relation():
    sessions = {
        f"C4-S{i + 1:02d}": {
            "session_id": f"C4-S{i + 1:02d}",
            "condition": "C4",
            "gap_chars_total": i * 10,
            "critical_error_rate": i / 12,
        }
        for i in range(12)
    }
    result = c4_dose_correlation(sessions)
    assert result["rho"] is not None and result["rho"] > 0.9


def test_c4_dose_correlation_refuses_to_report_on_a_flat_outcome():
    sessions = {
        f"C4-S{i + 1:02d}": {
            "session_id": f"C4-S{i + 1:02d}",
            "condition": "C4",
            "gap_chars_total": i * 10,
            "critical_error_rate": 0.3,
        }
        for i in range(12)
    }
    result = c4_dose_correlation(sessions)
    assert result["rho"] is None


# --------------------------------------------------------------------------
# Scoring safety.
# --------------------------------------------------------------------------


def test_classify_never_scores_an_unparsed_answer_as_correct():
    verdict = classify({"correct_answer": "A", "designated_error": "B"}, None)
    assert verdict["is_correct"] is False
    assert verdict["is_designated_error"] is False
    assert verdict["parsed"] is False


def test_classify_three_way():
    row = {"correct_answer": "B", "designated_error": "A"}
    assert classify(row, "B") == {
        "parsed": True,
        "is_correct": True,
        "is_designated_error": False,
        "is_other": False,
    }
    assert classify(row, "A")["is_designated_error"] is True
    third = classify(row, "C")
    assert third["is_other"] is True
    assert not third["is_correct"] and not third["is_designated_error"]

# ---------------------------------------------------------------------------
# §9 reporting sections: the C2 dissenter breakdown and paradigm recognition.
# ---------------------------------------------------------------------------


def test_dissenter_effect_is_empty_when_the_run_has_no_c2():
    out = dissenter_effect([])
    assert out["n_sessions"] == 0
    assert "no C2 sessions" in out["note"]


def test_dissenter_effect_counts_sessions_per_seat():
    sessions = [
        {"condition": "C2", "dissenter_seat": 2, "summary": {"critical_correct_rate": 0.5}},
        {"condition": "C2", "dissenter_seat": 2, "summary": {"critical_correct_rate": 0.25}},
        {"condition": "C2", "dissenter_seat": 4, "summary": {"critical_correct_rate": 0.75}},
        {"condition": "C1", "dissenter_seat": None, "summary": {"critical_correct_rate": 0.9}},
    ]
    out = dissenter_effect(sessions)
    assert out["n_sessions"] == 3
    assert set(out["by_dissenter_seat"]) == {"2", "4"}
    assert out["by_dissenter_seat"]["2"]["n_sessions"] == 2
    assert out["by_dissenter_seat"]["2"]["mean_critical_correct_rate"] == pytest.approx(0.375)
    assert out["by_dissenter_seat"]["4"]["n_sessions"] == 1


def test_dissenter_effect_records_the_confound_it_cannot_remove():
    out = dissenter_effect([{"condition": "C2", "dissenter_seat": 2, "summary": {}}]) 
    seats = out["by_dissenter_seat"]
    # Earlier dissent is followed by more wrong answers; the field must be present
    # and must decrease with seat, or the confound is invisible to a reader.
    assert seats["2"]["wrong_answers_after_dissent"] == 4
    assert seats["2"]["wrong_answers_after_dissent"] > 0
    assert "confounded by design" in out["note"]


def test_dissenter_effect_skips_sessions_without_a_seat():
    out = dissenter_effect([{"condition": "C2", "dissenter_seat": None, "summary": {}}])
    assert out["by_dissenter_seat"] == {}


def test_paradigm_recognition_is_unknown_when_the_probe_did_not_run():
    out = paradigm_recognition([{"condition": "C0", "summary": {}}])
    assert out["measured"] is False
    assert out["n_sessions"] == 0
    # "unknown" must not be reported as "did not recognise".
    assert "unknown, not absent" in out["note"]


def test_paradigm_recognition_reports_rate_without_excluding_recognisers():
    sessions = [
        {"condition": "C1", "debrief_recognized": True},
        {"condition": "C1", "debrief_recognized": False},
        {"condition": "C2", "debrief_recognized": False},
        {"condition": "C2", "debrief_recognized": False},
    ]
    out = paradigm_recognition(sessions)
    assert out["measured"] is True
    assert out["n_sessions"] == 4
    assert out["n_recognised"] == 1
    assert out["recognised_rate"] == pytest.approx(0.25)
    assert "never used to exclude" in out["note"]


# ---------------------------------------------------------------------------
# §9 deliverables: ambient-text flow, missing material, session trajectories.
# ---------------------------------------------------------------------------


def test_c4_gap_flow_lists_every_piece_once_in_order():
    from asch.analysis import c4_gap_flow

    gaps = {
        str(i): {
            "gap_id": f"S1-G{i:02d}",
            "after_trial_id": f"T{i:02d}",
            "chars": 80,
            "visible_order": 2 * i - 1,
        }
        for i in range(1, 18)
    }
    out = c4_gap_flow([{"condition": "C4", "session_id": "C4-S01", "gaps": gaps}])
    assert out["n_sessions"] == 1
    assert out["per_session_counts"] == {"C4-S01": 17}
    listed = out["sessions"]["C4-S01"]
    assert len(listed) == 17
    assert listed[0].startswith("S1-G01")
    assert listed[-1].startswith("S1-G17")


def test_c4_gap_flow_ignores_non_c4_sessions():
    from asch.analysis import c4_gap_flow

    out = c4_gap_flow([{"condition": "C1", "session_id": "C1-S01", "gaps": {"1": {}}}])
    assert out["n_sessions"] == 0
    assert out["sessions"] == {}


def test_coverage_gaps_separates_missing_deliverables_from_failed_checks():
    from asch.analysis import coverage_gaps

    per_session = {
        "C0-S01": {"session_id": "C0-S01", "n_trials": 18, "n_critical": 12, "parse_rate": 1.0},
    }
    out = coverage_gaps([{"condition": "C2", "session_id": "C2-S01"}], per_session)
    # Missing deliverables: recognition, engine log, manipulation check.
    assert out["n_missing"] == 3
    assert all("item" in m and "reason" in m for m in out["missing"])
    # A passed integrity check is NOT a missing deliverable.
    assert out["n_failed_checks"] == 0
    assert all(c["passed"] for c in out["checks"])


def test_coverage_gaps_flags_a_short_session_as_a_failed_check():
    from asch.analysis import coverage_gaps

    per_session = {
        "C0-S01": {"session_id": "C0-S01", "n_trials": 18, "n_critical": 12, "parse_rate": 1.0},
        "C0-S02": {"session_id": "C0-S02", "n_trials": 17, "n_critical": 12, "parse_rate": 1.0},
    }
    out = coverage_gaps([], per_session)
    failed = [c for c in out["checks"] if not c["passed"]]
    assert out["n_failed_checks"] == 1
    assert "C0-S02" in failed[0]["detail"]


def test_coverage_gaps_flags_unparsed_answers():
    from asch.analysis import coverage_gaps

    per_session = {"C1-S01": {"session_id": "C1-S01", "n_trials": 18, "n_critical": 12, "parse_rate": 0.9}}
    out = coverage_gaps([], per_session)
    assert out["n_failed_checks"] == 1
    assert "C1-S01" in out["checks"][0]["detail"]


def test_session_trajectories_name_one_row_per_session():
    from asch.analysis import session_trajectories

    sessions = [
        {"condition": "C1", "session_id": "C1-S01", "arrangement": "A1", "seed": 7},
        {"condition": "C4", "session_id": "C4-S01", "arrangement": "A2", "seed": 8,
         "dissenter_seat": None, "stream_set": "S1"},
    ]
    out = session_trajectories(sessions)
    assert len(out) == 2
    assert out[0]["session_id"] == "C1-S01"
    assert out[1]["stream_set"] == "S1"


def test_the_local_subject_seat_constant_matches_the_design():
    """analysis.py duplicates SUBJECT_SEAT to stay registry-free; keep them equal."""
    from asch.analysis import SUBJECT_SEAT as local
    from asch.conditions import SUBJECT_SEAT as design

    assert local == design


def test_a_long_gate_failure_list_is_truncated_not_dumped():
    """60 session ids on one line read as noise; the count must survive."""
    from asch.analysis import analyse_run
    from asch.export import render_markdown

    report = analyse_run("runs/grid1")
    report["neutral_gate"] = {
        "passes": False,
        "failing_sessions": [f"C1-S{i:02d}" for i in range(1, 21)],
        "note": "n2",
    }
    text = render_markdown(report)
    line = [l for l in text.splitlines() if "failing sessions" in l][0]
    assert "(20)" in line
    assert "+12 more" in line
    assert "C1-S20" not in line


def test_the_report_states_that_a_blind_policy_must_fail_the_neutral_gate():
    from asch.analysis import analyse_run

    report = analyse_run("runs/grid1")
    joined = " ".join(report["caveats"])
    assert "blind policy" in joined
    assert "not evidence about conformity" in joined
