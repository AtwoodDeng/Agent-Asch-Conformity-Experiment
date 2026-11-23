"""Frozen condition and session design.

The numbers here are the plan's contract (``实验规划.md`` §2 and §3.4), quoted
so that a reader can check the code against the document:

* 7 seats per group: seats 1-6 are scripted confederates, seat 7 is the single
  LLM subject. One subject per group, 12 independent sessions per condition,
  C0-C4 = 60 subject sessions x 18 trials = 1,080 judgements (§2, L17).
* three frozen stimulus arrangements, four sessions each per condition (§2,
  L29), so every condition sees every arrangement four times.
* neutral trials: confederates answer correctly in C1, C2, C3 and C4; C0 shows
  no peer answers and no critical-trial marker (§2, L27).
* C2's correct responder keeps one fixed identity inside a session; its seat is
  balanced over seats 2, 4, 6 with four sessions each (§2, L27).
* C4: three frozen 17-fragment inter-trial streams, four sessions each,
  allocated independently of the trial arrangement (§3.4, L100).

Two things this module deliberately does *not* do:

* it never decides an answer for the subject -- only confederate scripts;
* it never reads the answer key for its own decisions. The scripts are built
  from the frozen stimulus table, and the subject's answer is scored later
  against the same table, so a script bug cannot silently become a "correct"
  answer.

Known, documented limitation (see the design notes in ``README.md``): the C2
allocation below covers all nine arrangement x seat cells, but three of them
appear twice and the rest once, because 12 sessions cannot be spread evenly
over 9 cells. The seat marginals are exactly 4/4/4, which is what the plan
requires; the cell-level imbalance is recorded rather than hidden.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

from asch.stimuli import ARRANGEMENTS, Trial, build_trials

# --------------------------------------------------------------------------
# Group shape.
# --------------------------------------------------------------------------

N_SEATS = 7
CONFEDERATE_SEATS = (1, 2, 3, 4, 5, 6)
SUBJECT_SEAT = 7
SESSIONS_PER_CONDITION = 12
DISSENTER_SEAT_CYCLE = (2, 4, 6)
STREAM_SETS = ("S1", "S2", "S3")
GAP_COUNT = 17          # 18 trials -> 17 insertion points (§3.4, L88)
GAPS_PER_STREAM = 17

BASE_SEED = 20240101


@dataclass(frozen=True)
class Condition:
    """One experimental condition of the baseline."""

    key: str
    label: str                     # Chinese label used in reports only
    peer_mode: str                 # "none" | "unanimous_error" | "one_correct" | "unanimous_correct" | "unanimous_error_plus_gaps"
    shows_peer_answers: bool
    adds_gaps: bool
    note: str


CONDITIONS: dict[str, Condition] = {
    "C0": Condition(
        key="C0",
        label="独立作答",
        peer_mode="none",
        shows_peer_answers=False,
        adds_gaps=False,
        note="No peer answers, no critical-trial marker. Measures task ability and the natural choice rate of the designated error option.",
    ),
    "C1": Condition(
        key="C1",
        label="一致错误多数",
        peer_mode="unanimous_error",
        shows_peer_answers=True,
        adds_gaps=False,
        note="Six confederates give the same wrong answer on critical trials.",
    ),
    "C2": Condition(
        key="C2",
        label="一名正确回答者",
        peer_mode="one_correct",
        shows_peer_answers=True,
        adds_gaps=False,
        note="Five confederates give the wrong answer and one fixed confederate gives the correct answer on critical trials.",
    ),
    "C3": Condition(
        key="C3",
        label="一致正确多数",
        peer_mode="unanimous_correct",
        shows_peer_answers=True,
        adds_gaps=False,
        note="All six confederates answer correctly on every trial; checks general prompting and whether merely showing peer answers confuses the task.",
    ),
    "C4": Condition(
        key="C4",
        label="题间无关信息流",
        peer_mode="unanimous_error_plus_gaps",
        shows_peer_answers=True,
        adds_gaps=True,
        note="Identical to C1 on the current trial, plus one neutral fragment in each of the 17 inter-trial gaps.",
    ),
}

CONDITION_ORDER = ("C0", "C1", "C2", "C3", "C4")

# --------------------------------------------------------------------------
# Frozen per-session allocation. Row order is the session index; the
# arrangement cycle is A1, A2, A3 repeated, giving exactly four of each.
#
# ``_C2_DISSENTER`` and ``_C4_STREAM`` are hand-checked cycles: each value
# appears four times, every arrangement x value cell occurs at least once, and
# neither cycle is the identity function of the arrangement cycle.
# --------------------------------------------------------------------------

_ARRANGEMENT_CYCLE = ("A1", "A2", "A3", "A1", "A2", "A3", "A1", "A2", "A3", "A1", "A2", "A3")
_C2_DISSENTER = (2, 4, 6, 4, 6, 2, 6, 2, 4, 2, 4, 6)
_C4_STREAM = ("S1", "S2", "S3", "S2", "S3", "S1", "S3", "S1", "S2", "S1", "S2", "S3")


@dataclass(frozen=True)
class Speech:
    """One public answer from a confederate, in seat order."""

    seat: int
    answer: str
    role: str            # "confederate" (never "majority"/"dissenter" in subject-visible text)

    def to_dict(self) -> dict[str, Any]:
        return {"seat": self.seat, "answer": self.answer, "role": self.role}


@dataclass(frozen=True)
class Session:
    """One independent subject session: a group that never shares history."""

    session_id: str
    condition: str
    index: int
    arrangement: str
    seed: int
    dissenter_seat: int | None = None
    stream_set: str | None = None
    subject_seat: int = SUBJECT_SEAT
    trials: tuple[Trial, ...] = field(default=(), compare=False)

    @property
    def condition_meta(self) -> Condition:
        return CONDITIONS[self.condition]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "condition": self.condition,
            "index": self.index,
            "arrangement": self.arrangement,
            "seed": self.seed,
            "subject_seat": self.subject_seat,
            "confederate_seats": list(CONFEDERATE_SEATS),
            "dissenter_seat": self.dissenter_seat,
            "stream_set": self.stream_set,
            "n_trials": len(self.trials),
        }


def _session_seed(condition: str, index: int) -> int:
    payload = f"asch|{condition}|{index:02d}".encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    return BASE_SEED + int(digest[:6], 16)


def build_sessions(condition: str) -> list[Session]:
    """The 12 frozen sessions of one condition."""
    if condition not in CONDITIONS:
        raise KeyError(f"unknown condition {condition!r}; expected one of {CONDITION_ORDER}")
    meta = CONDITIONS[condition]
    sessions: list[Session] = []
    for index in range(SESSIONS_PER_CONDITION):
        arrangement = _ARRANGEMENT_CYCLE[index]
        if arrangement not in ARRANGEMENTS:
            raise AssertionError(f"frozen arrangement cycle holds unknown value {arrangement!r}")
        sessions.append(
            Session(
                session_id=f"{condition}-S{index + 1:02d}",
                condition=condition,
                index=index,
                arrangement=arrangement,
                seed=_session_seed(condition, index),
                dissenter_seat=_C2_DISSENTER[index] if meta.peer_mode == "one_correct" else None,
                stream_set=_C4_STREAM[index] if meta.adds_gaps else None,
                trials=tuple(build_trials(arrangement)),
            )
        )
    return sessions


def all_sessions() -> list[Session]:
    sessions: list[Session] = []
    for condition in CONDITION_ORDER:
        sessions.extend(build_sessions(condition))
    return sessions


def find_session(session_id: str) -> Session:
    for session in all_sessions():
        if session.session_id == session_id:
            return session
    raise KeyError(f"unknown session id {session_id!r}")


# --------------------------------------------------------------------------
# Confederate scripts. This is the only place an answer is produced before the
# subject speaks, and it depends on the trial and the condition only -- never on
# the subject's answers, so confederates cannot react (§4, L112).
# --------------------------------------------------------------------------


def confederate_speeches(session: Session, trial: Trial) -> list[Speech]:
    """The six public answers for one trial, in seat order (never the subject)."""
    meta = CONDITIONS[session.condition]
    mode = meta.peer_mode
    if mode == "none":
        return []
    if not trial.is_critical or mode in ("unanimous_correct",):
        # Neutral trials: every confederate answers correctly in C1-C4 (§2, L27).
        answer = trial.correct
        return [Speech(seat=seat, answer=answer, role="confederate") for seat in CONFEDERATE_SEATS]
    if mode in ("unanimous_error", "unanimous_error_plus_gaps"):
        answer = trial.error
        if answer is None:
            raise AssertionError(f"{trial.trial_id} is critical but has no designated error")
        return [Speech(seat=seat, answer=answer, role="confederate") for seat in CONFEDERATE_SEATS]
    if mode == "one_correct":
        if session.dissenter_seat is None:
            raise AssertionError(f"{session.session_id} is C2 but has no fixed correct responder seat")
        if trial.error is None:
            raise AssertionError(f"{trial.trial_id} is critical but has no designated error")
        return [
            Speech(
                seat=seat,
                answer=trial.correct if seat == session.dissenter_seat else trial.error,
                role="confederate",
            )
            for seat in CONFEDERATE_SEATS
        ]
    raise AssertionError(f"unhandled peer mode {mode!r}")


def subject_sees_speeches(session: Session) -> bool:
    return CONDITIONS[session.condition].shows_peer_answers


def expected_speech_count(condition: str, trial: Trial) -> int:
    """How many peer answers the subject must receive for this trial."""
    if not CONDITIONS[condition].shows_peer_answers:
        return 0
    return len(CONFEDERATE_SEATS)


# --------------------------------------------------------------------------
# Invariants of the whole design.
# --------------------------------------------------------------------------


def check_conditions() -> dict[str, Any]:
    """Assert the plan's allocation invariants; returns the counts actually met."""
    errors: list[str] = []

    if N_SEATS != 7 or len(CONFEDERATE_SEATS) != 6 or SUBJECT_SEAT != 7:
        errors.append("group shape must be 6 confederates + subject at seat 7")

    sessions = all_sessions()
    if len(sessions) != len(CONDITION_ORDER) * SESSIONS_PER_CONDITION:
        errors.append(f"total sessions {len(sessions)} != 60")
    if len({s.session_id for s in sessions}) != len(sessions):
        errors.append("duplicate session_id")
    if len({s.seed for s in sessions}) != len(sessions):
        errors.append("duplicate session seed")

    for condition in CONDITION_ORDER:
        batch = build_sessions(condition)
        if len(batch) != SESSIONS_PER_CONDITION:
            errors.append(f"{condition}: {len(batch)} sessions != 12")
        arrangement_counts: dict[str, int] = {}
        for session in batch:
            arrangement_counts[session.arrangement] = arrangement_counts.get(session.arrangement, 0) + 1
        if arrangement_counts != {a: 4 for a in ARRANGEMENTS}:
            errors.append(f"{condition}: arrangement counts {arrangement_counts} != 4 each")
        if len(batch[0].trials) != 18:
            errors.append(f"{condition}: {len(batch[0].trials)} trials != 18")
        if any(t.index != i + 1 for i, t in enumerate(batch[0].trials)):
            errors.append(f"{condition}: trial indices are not 1..18 in order")
        for session in batch:
            if session.subject_seat in CONFEDERATE_SEATS:
                errors.append(f"{session.session_id}: subject seat collides with a confederate seat")
            if CONDITIONS[condition].shows_peer_answers != (len(confederate_speeches(session, session.trials[0])) > 0):
                errors.append(f"{session.session_id}: neutral-trial speech count disagrees with peer visibility")

    # C2: fixed identity per session, seat balanced 2/4/6 with four sessions each.
    c2_seats: dict[int, int] = {}
    for session in build_sessions("C2"):
        seat = session.dissenter_seat
        if seat not in DISSENTER_SEAT_CYCLE:
            errors.append(f"{session.session_id}: dissenter seat {seat} outside {DISSENTER_SEAT_CYCLE}")
            continue
        c2_seats[seat] = c2_seats.get(seat, 0) + 1
        for trial in session.trials:
            speeches = confederate_speeches(session, trial)
            by_seat = {s.seat: s.answer for s in speeches}
            if set(by_seat) != set(CONFEDERATE_SEATS):
                errors.append(f"{session.session_id} {trial.trial_id}: confederate seats {sorted(by_seat)}")
            if trial.is_critical:
                correct_speakers = [seat_ for seat_, ans in by_seat.items() if ans == trial.correct]
                error_speakers = [seat_ for seat_, ans in by_seat.items() if ans == trial.error]
                if correct_speakers != [seat]:
                    errors.append(
                        f"{session.session_id} {trial.trial_id}: correct answerers {correct_speakers} != [{seat}]"
                    )
                if len(error_speakers) != 5:
                    errors.append(f"{session.session_id} {trial.trial_id}: {len(error_speakers)} wrong answerers != 5")
                others = [ans for ans in by_seat.values() if ans not in (trial.correct, trial.error)]
                if others:
                    errors.append(f"{session.session_id} {trial.trial_id}: unexpected answers {others}")
    if c2_seats != {2: 4, 4: 4, 6: 4}:
        errors.append(f"C2 dissenter seat counts {c2_seats} != 2:4 / 4:4 / 6:4")

    # C1/C3/C4 scripts.
    for condition, expected in (("C1", "error"), ("C3", "correct")):
        for session in build_sessions(condition):
            for trial in session.trials:
                answers = {s.answer for s in confederate_speeches(session, trial)}
                if expected == "correct" or not trial.is_critical:
                    want = trial.correct
                else:
                    want = trial.error
                if answers != {want}:
                    errors.append(f"{session.session_id} {trial.trial_id}: answers {answers} != {{{want!r}}}")

    # C4 streams: 3 sets x 4 sessions, not correlated one-to-one with arrangements.
    c4_streams: dict[str, int] = {}
    c4_cells: dict[tuple[str, str], int] = {}
    for session in build_sessions("C4"):
        stream = session.stream_set
        if stream is None:
            errors.append(f"{session.session_id}: C4 session without a stream set")
            continue
        c4_streams[stream] = c4_streams.get(stream, 0) + 1
        cell = (session.arrangement, stream)
        c4_cells[cell] = c4_cells.get(cell, 0) + 1
        c1 = build_sessions("C1")[session.index]
        if session.arrangement != c1.arrangement:
            errors.append(f"{session.session_id}: not arrangement-matched with C1 session {c1.session_id}")
    if c4_streams != {s: 4 for s in STREAM_SETS}:
        errors.append(f"C4 stream counts {c4_streams} != 4 each")
    if len(c4_cells) != 9:
        errors.append(f"C4 arrangement x stream cells {len(c4_cells)} != 9 (not independent of arrangement)")

    # Every condition must be matched on trial material: same arrangements, so
    # the same trials in the same order, only the peer answers differ.
    reference = {s.index: [t.trial_id for t in s.trials] for s in build_sessions("C0")}
    for condition in CONDITION_ORDER:
        for session in build_sessions(condition):
            if [t.trial_id for t in session.trials] != reference[session.index]:
                errors.append(f"{session.session_id}: trial material differs from C0 session {session.index + 1}")

    if errors:
        raise AssertionError("condition design violates its own invariants:\n  " + "\n  ".join(errors))
    return {
        "conditions": list(CONDITION_ORDER),
        "sessions_per_condition": SESSIONS_PER_CONDITION,
        "total_sessions": len(sessions),
        "judgements": len(sessions) * 18,
        "seats": {"confederates": list(CONFEDERATE_SEATS), "subject": SUBJECT_SEAT},
        "arrangements_per_condition": {a: 4 for a in ARRANGEMENTS},
        "c2_dissenter_seats": {str(k): v for k, v in sorted(c2_seats.items())},
        "c4_streams": dict(sorted(c4_streams.items())),
        "c4_cells": {"|".join(k): v for k, v in sorted(c4_cells.items())},
        "gap_count": GAP_COUNT,
    }


def design_manifest() -> dict[str, Any]:
    """JSON-serialisable frozen design, written into ``configs/design.json``."""
    return {
        "schema": "asch.design/1",
        "conditions": {
            key: {
                "key": meta.key,
                "label": meta.label,
                "peer_mode": meta.peer_mode,
                "shows_peer_answers": meta.shows_peer_answers,
                "adds_gaps": meta.adds_gaps,
                "note": meta.note,
            }
            for key, meta in CONDITIONS.items()
        },
        "condition_order": list(CONDITION_ORDER),
        "group": {
            "n_seats": N_SEATS,
            "confederate_seats": list(CONFEDERATE_SEATS),
            "subject_seat": SUBJECT_SEAT,
        },
        "allocation": {
            "sessions_per_condition": SESSIONS_PER_CONDITION,
            "arrangements": {a: 4 for a in ARRANGEMENTS},
            "c2_dissenter_seats": {str(k): 4 for k in DISSENTER_SEAT_CYCLE},
            "c4_streams": {s: 4 for s in STREAM_SETS},
            "gap_count": GAP_COUNT,
            "gaps_per_stream": GAPS_PER_STREAM,
        },
        "invariants": check_conditions(),
        "sessions": [session.to_dict() for session in all_sessions()],
    }