"""Design invariants: the frozen contract of the plan, asserted.

These tests encode what must not drift. Each one names the plan clause it
protects, so a failure points at the design decision rather than at a line of
code.
"""

import json

import pytest

from asch.conditions import (
    CONDITIONS,
    CONDITION_ORDER,
    CONFEDERATE_SEATS,
    SUBJECT_SEAT,
    all_sessions,
    build_sessions,
    check_conditions,
    confederate_speeches,
    expected_speech_count,
    subject_sees_speeches,
)
from asch.stimuli import (
    CRITICAL_COUNT,
    NEUTRAL_COUNT,
    TRIAL_COUNT,
    build_trials,
    check_design,
)


def test_trial_structure_is_18_with_12_critical():
    """§2: 18 trials, 12 critical (6 neutral)."""
    trials = build_trials("A1")
    assert len(trials) == TRIAL_COUNT == 18
    assert sum(1 for t in trials if t.is_critical) == CRITICAL_COUNT == 12
    assert sum(1 for t in trials if not t.is_critical) == NEUTRAL_COUNT == 6


def test_first_two_trials_are_neutral():
    """§2 L29: trials 1-2 are always neutral, in every arrangement."""
    for arrangement in ("A1", "A2", "A3"):
        trials = build_trials(arrangement)
        assert not trials[0].is_critical and not trials[1].is_critical


def test_design_balances_slots_and_error_direction():
    """§3.1: correct slot 6x overall / 4x per critical, error direction balanced."""
    design = check_design()
    assert design["correct_slot_counts"] == {"A": 6, "B": 6, "C": 6}
    assert design["critical_correct_slot_counts"] == {"A": 4, "B": 4, "C": 4}
    assert design["critical_error_slot_counts"] == {"A": 4, "B": 4, "C": 4}
    assert design["error_direction_counts"] == {"longer": 6, "shorter": 6}


def test_every_trial_has_exactly_one_line_equal_to_the_standard():
    for arrangement in ("A1", "A2", "A3"):
        for trial in build_trials(arrangement):
            matches = [slot for slot, _role, length in trial.lines if abs(length - trial.standard_in) < 1e-9]
            assert len(matches) == 1, f"{arrangement} {trial.trial_id}"


def test_correct_answer_agrees_with_the_equal_line():
    """The correct slot must be the one whose line equals the standard."""
    for arrangement in ("A1", "A2", "A3"):
        for trial in build_trials(arrangement):
            equal = next(s for s, _r, length in trial.lines if abs(length - trial.standard_in) < 1e-9)
            assert trial.correct == equal


def test_critical_trials_have_an_error_option_and_neutral_ones_do_not():
    for trial in build_trials("A1"):
        if trial.is_critical:
            assert trial.error in ("A", "B", "C")
            assert trial.error != trial.correct
        else:
            assert trial.error is None


def test_sixty_sessions_and_one_thousand_eighty_judgements():
    """§2 L17: 12 sessions x 5 conditions x 18 trials = 1,080."""
    sessions = all_sessions()
    assert len(sessions) == 60
    assert sum(len(s.trials) for s in sessions) == 1080


def test_condition_order_and_labels():
    assert CONDITION_ORDER == ("C0", "C1", "C2", "C3", "C4")
    assert list(CONDITIONS) == list(CONDITION_ORDER)
    for key, condition in CONDITIONS.items():
        assert condition.key == key


def test_peer_visibility_matches_the_condition_table():
    """§2 L27: C0 shows no peer answers; C1-C4 all do."""
    assert subject_sees_speeches(build_sessions("C0")[0]) is False
    for condition in ("C1", "C2", "C3", "C4"):
        assert subject_sees_speeches(build_sessions(condition)[0]) is True


def test_speech_counts_are_six_everywhere():
    """Six confederates speak on every trial in C1-C4; C0 shows none at all."""
    for condition in CONDITION_ORDER:
        expected = 0 if condition == "C0" else 6
        for session in build_sessions(condition):
            for trial in session.trials:
                assert expected_speech_count(condition, trial) == expected
                assert len(confederate_speeches(session, trial)) == expected


def test_neutral_trials_are_unanimously_correct_in_every_condition():
    """§2 L27: on neutral trials every confederate answers correctly."""
    for condition in CONDITION_ORDER:
        if condition == "C0":
            continue  # no public record at all
        for session in build_sessions(condition):
            for trial in session.trials:
                if trial.is_critical:
                    continue
                speeches = confederate_speeches(session, trial)
                assert {s.answer for s in speeches} == {trial.correct}


def test_c1_and_c4_are_unanimously_wrong_on_critical_trials():
    for condition in ("C1", "C4"):
        for session in build_sessions(condition):
            for trial in session.trials:
                if not trial.is_critical:
                    continue
                speeches = confederate_speeches(session, trial)
                assert {s.answer for s in speeches} == {trial.error}


def test_c3_is_unanimously_correct_on_critical_trials():
    for session in build_sessions("C3"):
        for trial in session.trials:
            if not trial.is_critical:
                continue
            assert {s.answer for s in confederate_speeches(session, trial)} == {trial.correct}


def test_c2_has_exactly_one_correct_dissenter_after_the_majority():
    """§2 L27: one fixed dissenter per session, seated at 2, 4 or 6."""
    for session in build_sessions("C2"):
        assert session.dissenter_seat in (2, 4, 6)
        for trial in session.trials:
            if not trial.is_critical:
                continue
            speeches = confederate_speeches(session, trial)
            correct = [s for s in speeches if s.answer == trial.correct]
            assert len(correct) == 1
            assert correct[0].seat == session.dissenter_seat
            assert sum(1 for s in speeches if s.answer == trial.error) == 5


def test_c2_dissenter_breaks_a_unanimous_run():
    """The dissenter must interrupt the majority, not trail it.

    Asch's unfilmed design puts the correct responder ahead of the last
    confederate so the subject cannot read a completed majority before the
    dissent lands. With the dissenter at seat 2, 4 or 6 the six-seat record
    cannot always achieve this: at seat 6 the dissent is the final answer, so
    the run of five agreeing wrong answers is unbroken. This test pins the
    arrangement the design actually produces, and documents the difference
    instead of claiming an Asch-identical ordering.
    """
    for session in build_sessions("C2"):
        for trial in session.trials:
            if not trial.is_critical:
                continue
            speeches = confederate_speeches(session, trial)
            after = [s.seat for s in speeches if s.answer != trial.correct and s.seat > session.dissenter_seat]
            if session.dissenter_seat == 6:
                assert after == [], "at seat 6 the dissenter speaks last"
            else:
                assert after, "before seat 6 the dissent is followed by more majority answers"


def test_c2_dissenter_seats_are_balanced():
    """Three seats x 4 sessions each = 12."""
    counts = {}
    for session in build_sessions("C2"):
        counts[session.dissenter_seat] = counts.get(session.dissenter_seat, 0) + 1
    assert counts == {2: 4, 4: 4, 6: 4}


def test_arrangements_are_balanced_four_each():
    """§2 L29: three arrangements x 4 sessions."""
    for condition in CONDITION_ORDER:
        counts = {}
        for session in build_sessions(condition):
            counts[session.arrangement] = counts.get(session.arrangement, 0) + 1
        assert counts == {"A1": 4, "A2": 4, "A3": 4}


def test_seat_seven_is_the_subject():
    assert SUBJECT_SEAT == 7
    assert CONFEDERATE_SEATS == (1, 2, 3, 4, 5, 6)
    for session in all_sessions():
        assert session.subject_seat == 7


def test_session_ids_are_unique_and_seeds_differ():
    sessions = all_sessions()
    ids = [s.session_id for s in sessions]
    assert len(ids) == len(set(ids))
    assert len({s.seed for s in sessions}) == len(sessions)


def test_confederate_speeches_are_a_pure_function_of_the_trial():
    """Confederates cannot react: the same trial always yields the same scripts."""
    session = build_sessions("C1")[0]
    trial = session.trials[2]
    first = [s.to_dict() for s in confederate_speeches(session, trial)]
    second = [s.to_dict() for s in confederate_speeches(session, trial)]
    assert first == second


def test_check_conditions_reports_the_expected_shape():
    report = check_conditions()
    assert report["total_sessions"] == 60
    assert report["judgements"] == 1080
    assert report["sessions_per_condition"] == 12
    assert report["arrangements_per_condition"] == {"A1": 4, "A2": 4, "A3": 4}
    assert report["c2_dissenter_seats"] == {"2": 4, "4": 4, "6": 4}
    assert report["c4_streams"] == {"S1": 4, "S2": 4, "S3": 4}
    assert len(report["c4_cells"]) == 9


def test_frozen_design_matches_the_generated_configs(root):
    """The committed manifest must equal the code's manifest: no silent drift."""
    path = root / "configs" / "design.json"
    if not path.exists():
        pytest.skip("configs/design.json not generated yet")
    frozen = json.loads(path.read_text(encoding="utf-8"))
    from asch.conditions import design_manifest

    live = design_manifest()
    for key in ("conditions", "sessions", "totals"):
        if key in live:
            assert frozen[key] == live[key], f"drift in design.json field {key!r}"