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
    schemas = _schemas()
    return schemas.StudySpec(
        study_id=study_id_for(session),
        title=f"Line-length judgement, {session.condition} session {session.index + 1:02d}",
        research_question=(
            "Does a unanimous wrong majority shift a multimodal LLM's public "
            "line-length judgement, and does one correct dissenter weaken that shift?"
        ),
        hypothesis=(
            "H1: a unanimous wrong majority raises the designated-error rate vs C0. "
            "H2: one correct dissenter (C2) lowers it vs C1. "
            "C3 is a reverse control; C4 is an exploratory inter-trial gap condition."
        ),
        study_type="longitudinal",
        n_steps=len(session.trials),
        seed=session.seed,
        time_unit="abstract",
        step_meaning="one line-judgement trial (18 per session)",
        metrics=["critical_error_rate", "critical_correct_rate", "neutral_correct_rate", "parse_rate"],
        display_metrics=["critical_error_rate", "neutral_correct_rate"],
        domain="social-psychology",
        tags=["asch1956", "line-judgment", "from-scratch", session.condition.lower()],
        legacy_simulator="from_scratch",
        provider_refs=["asch.env", "asch.pop", "asch.decision", "asch.collector"],
        status="draft",
        maintainer=maintainer,
    )


def make_environment_bundle(session: Session, *, stimulus_root: str) -> Any:
    """The environment bundle: a single session, no scheduled events, no broadcasts.

    The peer answers are *not* broadcasts. They are part of the group record
    that the environment hands to the subject inside the observation, because
    they are produced by scripted seats and never travel between agents on their
    own (§4, L109/L112).
    """
    schemas = _schemas()
    return schemas.EnvironmentBundle(
        study_id=study_id_for(session),
        provider_ref="asch.env",
        provider_args={
            "session_id": session.session_id,
            "stimulus_root": stimulus_root,
            "agent_id": "P07",
        },
        layers=[
            schemas.EnvironmentLayer(
                name="stimulus",
                modality="physical",
                scope="macro",
                dynamics="static",
                description="the current trial's standard + comparison line card",
            ),
            schemas.EnvironmentLayer(
                name="peer_answers",
                modality="information",
                scope="local",
                dynamics="endogenous",
                description="scripted confederate answers written into the group record before the subject speaks",
            ),
            schemas.EnvironmentLayer(
                name="protocol",
                modality="information",
                scope="macro",
                dynamics="static",
                description="condition protocol note (never the answer key)",
            ),
        ],
        scheduled_events=[],
        information_program=schemas.InformationProgram(broadcasts=[]),
    )


def make_population_bundle(session: Session) -> Any:
    schemas = _schemas()
    return schemas.PopulationBundle(
        study_id=study_id_for(session),
        provider_ref="asch.pop",
        provider_args={"n_agents": 1},
        interaction=schemas.InteractionStructure(kind="none"),
        propagation=schemas.PropagationMode.INDEPENDENT,
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
        collector_args={},
        interaction_rounds=1,
        engine_args={
            # History is complete text only: past images are never re-sent (§3.3,
            # L80) and old trials are never truncated when C4 lengthens the
            # history (§3.4, L98).
            "memory_window": len(session.trials),
            "retain_full_history": True,
            "resend_past_images": False,
        },
        store_ref="duckdb",
        store_args={},
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