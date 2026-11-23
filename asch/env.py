"""Environment provider: the trial loop, the group record and the C4 gaps.

This is the ``EnvironmentProvider`` side of the study (``实验规划.md`` §4, L112):

    load stimulus -> produce scripted answers per condition -> route the visible
    record -> subject answers -> save answer and visible information -> next trial

Three properties matter and are enforced here rather than left to convention:

1. **The public record is real.** Confederate answers are written into
   ``group_record`` before the subject speaks, and the subject's prompt is
   rendered from that stored record -- not from a template that merely claims
   other people answered (§4, L112).
2. **Confederates never react.** ``confederate_speeches`` is a pure function of
   the trial and the condition, so a subject's answer cannot influence a later
   confederate answer. Scripts are regenerated from the frozen table on every
   read.
3. **C4 inserts ambient text, once per gap, after the complete public record of
   the previous trial and before the next trial's image** (§3.4, L96). The gap
   is passive: it never triggers a model call (L98).

The answer key is only touched when scoring, and the score of the current trial
is never part of what the subject sees.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from asch.conditions import (
    CONDITIONS,
    CONFEDERATE_SEATS,
    Session,
    confederate_speeches,
    subject_sees_speeches,
)
from asch.distractors import stream_pieces
from asch.prompts import (
    build_prompt,
    render_gap,
    render_history,
    render_trial,
)
from asch.stimuli import formal_image_relpath

# --------------------------------------------------------------------------
# Observation / action shaping. The provider is written against the platform
# ABCs, but the payloads are plain dicts so the standalone driver can run with
# the local stub and produce a byte-identical record.
# --------------------------------------------------------------------------


@dataclass
class TrialState:
    index: int
    trial_id: str
    kind: str
    correct: str
    error: str | None
    standard_in: float
    lines: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "trial_id": self.trial_id,
            "kind": self.kind,
            "correct": self.correct,
            "error": self.error,
            "standard_in": self.standard_in,
            "lines": dict(self.lines),
        }


@dataclass
class GroupRecord:
    """The public record of one session: confederate speeches and the subject's answers."""

    trials: dict[int, dict[str, Any]] = field(default_factory=dict)
    gaps: dict[int, dict[str, Any]] = field(default_factory=dict)

    def add_speeches(self, index: int, trial_id: str, speeches: list[dict[str, Any]]) -> None:
        entry = self.trials.setdefault(index, {"trial_id": trial_id})
        entry["speeches"] = speeches

    def add_subject_answer(self, index: int, answer: str | None, raw: str | None, source: str) -> None:
        entry = self.trials.setdefault(index, {})
        entry.update({"subject_answer": answer, "subject_raw": raw, "subject_source": source})

    def add_gap(self, index: int, piece: dict[str, Any]) -> None:
        self.gaps[index] = {
            "gap_id": piece["gap_id"],
            "after_trial_id": piece["after_trial_id"],
            "stream_set_id": piece["stream_set_id"],
            "chars": piece["chars"],
            "sha256": piece["sha256"],
            "visible_order": len(self.trials) + len(self.gaps),
        }

    def speeches_of(self, index: int) -> list[dict[str, Any]]:
        return self.trials.get(index, {}).get("speeches", [])

    def to_dict(self) -> dict[str, Any]:
        return {
            "trials": {str(k): v for k, v in sorted(self.trials.items())},
            "gaps": {str(k): v for k, v in sorted(self.gaps.items())},
        }


def _observation_cls():
    """The platform ``Observation`` when available, else the local stub's."""
    from socioverse.schemas import Observation  # imported late: works with the stub too

    return Observation


def _action_cls():
    from socioverse.schemas import Action

    return Action


def _abc():
    from socioverse.abc import EnvironmentProvider

    return EnvironmentProvider


def _register():
    from socioverse.engine import register

    return register


ENV_REF = "asch.env"


@_register()("environment", ENV_REF)
class AschEnvironment(_abc()):  # type: ignore[misc]
    """Runs one session of 18 trials, with 17 ambient gaps in C4."""

    def __init__(
        self,
        *,
        session: Session,
        stimulus_root: str | Path,
        agent_id: str = "P07",
        max_history_trials: int | None = None,
        **_unused: Any,
    ) -> None:
        self.session = session
        self.meta = CONDITIONS[session.condition]
        self.stimulus_root = Path(stimulus_root)
        self.agent_id = agent_id
        self.trial_list = list(session.trials)
        self.n_trials = len(self.trial_list)
        if max_history_trials is not None and max_history_trials < self.n_trials:
            # The plan forbids silently truncating old trials when C4 text grows
            # the history (§3.4, L98); a smaller window is a different design and
            # must be recorded explicitly, never quietly applied.
            raise ValueError(
                f"max_history_trials={max_history_trials} would truncate history below {self.n_trials} trials"
            )
        self.max_history_trials = max_history_trials
        self.gap_pieces = (
            stream_pieces(session.stream_set) if self.meta.adds_gaps and session.stream_set else []
        )
        if self.meta.adds_gaps and len(self.gap_pieces) != self.n_trials - 1:
            raise AssertionError(
                f"{session.session_id}: C4 needs {self.n_trials - 1} gaps, got {len(self.gap_pieces)}"
            )
        self.reset()

    # -- lifecycle ---------------------------------------------------------

    def reset(self, seed: int | None = None) -> None:
        self.t = 0
        self.record = GroupRecord()
        self.history: list[tuple[str, str]] = []
        self.rows: list[dict[str, Any]] = []
        self.gaps_shown = 0
        self.gap_chars = 0
        self.seed = self.session.seed if seed is None else seed

    def advance_to(self, t: int) -> None:
        if not 1 <= t <= self.n_trials:
            raise ValueError(f"step {t} outside 1..{self.n_trials}")
        self.t = t

    def _current(self) -> TrialState:
        # Guard the index explicitly: t=0 would silently wrap to the last trial
        # via Python's negative indexing, presenting the final stimulus as if it
        # were the first. A wrong trial is far worse than a raised error.
        if not 1 <= self.t <= self.n_trials:
            raise IndexError(
                f"no current trial: step {self.t} outside 1..{self.n_trials}"
            )
        trial = self.trial_list[self.t - 1]
        return TrialState(
            index=self.t,
            trial_id=trial.trial_id,
            kind=trial.kind,
            correct=trial.correct,
            error=trial.error,
            standard_in=trial.standard_in,
            lines={slot: length for slot, _role, length in trial.lines},
        )

    def _speeches(self) -> list[dict[str, Any]]:
        trial = self.trial_list[self.t - 1]
        return [s.to_dict() for s in confederate_speeches(self.session, trial)]

    def _ensure_script(self) -> list[dict[str, Any]]:
        """Write this trial's confederate answers into the public record once."""
        if self.t not in self.record.trials or "speeches" not in self.record.trials[self.t]:
            speeches = self._speeches() if subject_sees_speeches(self.session) else []
            trial = self.trial_list[self.t - 1]
            self.record.add_speeches(self.t, trial.trial_id, speeches)
        return self.record.speeches_of(self.t)

    # -- provider API ------------------------------------------------------

    def observe_batch(self, agent_ids: list[str], t: int, round_idx: int = 0) -> list[Any]:
        Observation = _observation_cls()
        if t != self.t:
            self.advance_to(t)
        speeches = self._ensure_script()
        trial = self._current()
        show_peers = subject_sees_speeches(self.session)
        prompt = build_prompt(
            condition=self.session.condition,
            index=self.t,
            n_trials=self.n_trials,
            speeches=[(s["seat"], s["answer"]) for s in speeches] if show_peers else [],
            history=self.history,
        )
        image_path = str(self.stimulus_root / formal_image_relpath(self.session.arrangement, trial.trial_id))
        observations = []
        for agent_id in agent_ids:
            local = {
                "condition": self.session.condition,
                "session_id": self.session.session_id,
                "trial_index": self.t,
                "trial_id": trial.trial_id,
                "n_trials": self.n_trials,
                "prompt": prompt,
                "image_path": image_path,
                "speeches": speeches,
                "shows_peer_answers": show_peers,
                "arrangement": self.session.arrangement,
                "seat": self.session.subject_seat,
                "n_seats": len(CONFEDERATE_SEATS) + 1,
                "gap_count_shown": self.gaps_shown,
            }
            observations.append(
                Observation(
                    agent_id=agent_id,
                    step=t,
                    macro_physical={"study": "asch1956-line-judgment", "condition": self.session.condition},
                    macro_information={"protocol": self.meta.note},
                    local_physical=local,
                )
            )
        return observations

    def apply(self, actions: list[Any]) -> None:
        """Store the subject's answer, then append the completed material to history."""
        if not 1 <= self.t <= self.n_trials:
            raise IndexError(f"no current trial: step {self.t} outside 1..{self.n_trials}")
        if not actions:
            raise ValueError(f"trial {self.t}: no action submitted")
        if len(actions) > 1:
            raise ValueError(f"trial {self.t}: {len(actions)} actions for a single subject")
        action = actions[0]
        payload = getattr(action, "payload", None)
        if payload is None and isinstance(action, dict):
            payload = action.get("payload", {})
        payload = payload or {}
        answer = payload.get("answer")
        raw = payload.get("raw")
        source = getattr(action, "source", None) or payload.get("source") or "unknown"

        trial = self.trial_list[self.t - 1]
        self.record.add_subject_answer(self.t, answer, raw, source)

        speeches = self.record.speeches_of(self.t)
        trial_block = render_trial(
            self.t,
            [(s["seat"], s["answer"]) for s in speeches],
            show_peers=subject_sees_speeches(self.session),
        )
        shown = answer if answer is not None else "未记录（回答无法解析）"
        self.history.append(("trial", f"{trial_block}\n你的回答：{shown}"))

        self.rows.append(
            {
                "session_id": self.session.session_id,
                "condition": self.session.condition,
                "arrangement": self.session.arrangement,
                "trial_index": self.t,
                "trial_id": trial.trial_id,
                "trial_kind": trial.kind,
                "basic_comparison": trial.basic,
                "size": trial.size,
                "standard_in": trial.standard_in,
                "lines": {slot: length for slot, _role, length in trial.lines},
                "correct_answer": trial.correct,
                "designated_error": trial.error,
                "peer_answers": [s["answer"] for s in speeches],
                "peer_majority_answer": _majority([s["answer"] for s in speeches]),
                "subject_answer": answer,
                "subject_raw": raw,
                "action_source": source,
                "is_critical": trial.is_critical,
                "is_correct": (answer == trial.correct) if answer is not None else None,
                "is_designated_error": (answer == trial.error) if answer is not None else None,
                "parsed": answer is not None,
                "gaps_shown_before": self.gaps_shown,
                "gap_chars_before": self.gap_chars,
                "seed": self.seed,
            }
        )

        # C4: ambient text goes into the gap after the complete public record of
        # this trial and before the next trial's image. No model call.
        if self.meta.adds_gaps and self.t < self.n_trials:
            piece = self.gap_pieces[self.t - 1]
            self.record.add_gap(self.t, piece)
            self.history.append(("gap", render_gap(piece["text"])))
            self.gaps_shown += 1
            self.gap_chars += piece["chars"]

        self.t += 1

    def agent_state(self, agent_id: str | None = None) -> dict[str, Any]:
        return {
            self.agent_id: {
                "condition": self.session.condition,
                "session_id": self.session.session_id,
                "trials_completed": len(self.rows),
                "answers": [row["subject_answer"] for row in self.rows],
            }
        }

    # -- inspection -------------------------------------------------------

    def snapshot(self) -> dict[str, Any]:
        return {
            "session": self.session.to_dict(),
            "steps_completed": len(self.rows),
            "gaps_shown": self.gaps_shown,
            "record": self.record.to_dict(),
            "history_entries": len(self.history),
            "history_chars": sum(len(text) for _, text in self.history),
        }

    def prompt_transcript(self) -> str:
        return render_history(self.history)


def _majority(answers: list[str]) -> str | None:
    if not answers:
        return None
    counts: dict[str, int] = {}
    for answer in answers:
        counts[answer] = counts.get(answer, 0) + 1
    best = max(counts.values())
    winners = [answer for answer, count in counts.items() if count == best]
    return winners[0] if len(winners) == 1 else None


def dump_session(directory: str | Path, environment: AschEnvironment) -> dict[str, Any]:
    """Persist one finished session: rows, record, transcript, snapshot."""
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    (out / "trials.json").write_text(
        json.dumps(environment.rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "record.json").write_text(
        json.dumps(environment.record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "snapshot.json").write_text(
        json.dumps(environment.snapshot(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "transcript.txt").write_text(environment.prompt_transcript(), encoding="utf-8")
    return {
        "session_id": environment.session.session_id,
        "rows": len(environment.rows),
        "dir": str(out),
    }