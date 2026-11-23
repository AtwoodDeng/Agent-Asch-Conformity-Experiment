"""Study/bundle construction: one session becomes one registered study run.

Everything the SocioVerse2 runtime needs to execute a session is assembled
here, and nothing about the design is decided here -- the condition tables come
from :mod:`asch.conditions`, the stimuli from :mod:`asch.stimuli`, the ambient
streams from :mod:`asch.distractors`.

``interaction_rounds`` is 1. The subject speaks once per trial, there is no
second round and no revision, which is what keeps the run replayable and the
branch record meaningful (§4, L110: in-trial interaction and revision belong to
the extension experiments, not the baseline).
"""

from __future__ import annotations

from typing import Any

from asch.conditions import Session


def _schemas():
    from socioverse import schemas

    return schemas


def _register():
    from socioverse.engine import register

    return register


def _layers() -> Any:
    schemas = _schemas()
    return schemas


STUDY_PREFIX = "asch"


def study_id_for(session: Session) -> str:
    return f"asch-{session.condition.lower()}-{session.index + 1:02d}"


def make_study(session: Session, *, maintainer: str = "dsh") -> Any:
    StudySpec = _schemas().StudySpec
    return StudySpec(
        study_id=study_id_for(session),
        title=f"Line-length judgement, {session.condition} session {session.index + 1:02d}",
        description=(
            f"Condition {session.condition} ({session.condition_meta.label}); "
            f"arrangement {session.arrangement}; 18 trials, "
            f"{'with' if session.condition_meta.adds_gaps else 'without'} inter-trial ambient text."
        ),
        status="draft",
        maintainer=maintainer,
        tags=["asch1956", "line-judgment", session.condition.lower()],
    )


def make_environment_bundle(session: Session, *, stimulus_root: str) -> Any:
    """The environment bundle: a single session, no scheduled events, no broadcasts.

    The peer answers are *not* broadcasts. They are part of the group record
    that the environment hands to the subject inside the observation, because
    they are produced by scripted seats and never travel between agents on their
    own (§4, L109/L112).
    """
    schemas = _schemas()
    bundle = schemas.EnvironmentBundle(
        study_id=study_id_for(session),
        provider_ref="asch.env",
        provider_args={
            "session_id": session.session_id,
            "stimulus_root": stimulus_root,
            "agent_id": "P07",
        },
        layers=[
            schemas.EnvironmentLayer(
                kind="scheduled_events",
                payload=[],
                note="No scheduled events: trials advance one at a time via the driver.",
            ),
            schemas.EnvironmentLayer(
                kind="information_program",
                payload=schemas.InformationProgram(broadcasts=[]),
                note="No broadcasts: peer answers are written into the group record, not broadcast.",
            ),
            schemas.EnvironmentLayer(
                kind="interaction_structure",
                payload=schemas.InteractionStructure(kind="sequential_scripted"),
                note="Six scripted seats answer in seat order; the subject answers seventh.",
            ),
        ],
        n_steps=len(session.trials),
    )
    return bundle


def make_population_bundle(session: Session) -> Any:  # noqa: ARG001
    schemas = _schemas()
    return schemas.PopulationBundle(
        study_id=study_id_for(session) if session else None,
        provider_ref="asch.pop",
        provider_args={"n_agents": 7},
        interaction={"kind": "none"},
    )


def make_simulation_config(
    session: Session,
    *,
    llm_kind: str,
    model: str | None,
    temperature: float,
    max_tokens: int,
    policy: str,
    decision_args_extra: dict[str, Any] | None = None,
) -> Any:
    schemas = _schemas()
    decision_args: dict[str, Any] = {
        "llm_kind": llm_kind,
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "policy": policy,
        "prompt_lang": "zh",
        "seed": session.seed,
    }
    if decision_args_extra:
        decision_args.update(decision_args_extra)
    return schemas.SimulationConfig(
        study_id=study_id_for(session),
        n_steps=len(session.trials),
        seed=session.seed,
        decision_ref="asch.decision",
        decision_args=decision_args,
        collector_ref="asch.collector",
        interaction_rounds=1,
        engine_args={
            # History is complete text only: past images are never re-sent (§3.3,
            # L80) and old trials are never truncated when C4 lengthens the
            # history (§3.4, L98).
            "memory_window": len(session.trials),
            "retain_full_history": True,
            "resend_past_images": False,
        },
    )


def make_asch_bundles(
    session: Session,
    *,
    stimulus_root: str,
    llm_kind: str = "scripted",
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 24,
    policy: str = "random",
) -> tuple[Any, Any, Any, Any]:
    """(study, environment_bundle, population_bundle, simulation_config)."""
    return (
        make_study(session),
        make_environment_bundle(session, stimulus_root=stimulus_root),
        make_population_bundle(session),
        make_simulation_config(
            session,
            llm_kind=llm_kind,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            policy=policy,
        ),
    )