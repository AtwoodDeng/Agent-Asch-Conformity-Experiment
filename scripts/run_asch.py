"""Driver: run sessions of one condition through the real providers.

Two drivers exist, and the difference matters for how the output may be labelled:

``standalone``
    This script's own loop: build the environment and the decision model for a
    session, step trial by trial, collect metrics. Exercises exactly the same
    ``asch/`` code the engine would call. Use it offline, and report its output
    as engineering validation only (``实验规划.md`` §6).

``engine``
    Hands the bundles from :mod:`asch.bundles` to
    ``socioverse.engine.build_simulator`` and lets the platform drive. Requires a
    real ``socioverse`` install.

Both drivers write the same per-session layout, so the exporter and the tests do
not care which one produced a run::

    runs/<run_id>/<condition>/<session_id>/trials.json
                                              /record.json
                                              /snapshot.json
                                              /transcript.txt
                                              /metrics.json
                                              /summary.json
    runs/<run_id>/index.json
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ENV_REF = "asch.env"
DECISION_REF = "asch.decision"
COLLECTOR_REF = "asch.collector"
POP_REF = "asch.pop"


def _strip_local_stub(argv: list[str]) -> tuple[bool, list[str]]:
    stub = "--local-stub" in argv
    return stub, [a for a in argv if a != "--local-stub"]


def parse_seeds(spec: str) -> list[int]:
    seeds: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            lo, hi = part.split("-", 1)
            seeds.extend(range(int(lo), int(hi) + 1))
        else:
            seeds.append(int(part))
    return seeds


def build_index_entry(
    *,
    session: Any,
    summary: dict[str, Any],
    counters: dict[str, Any],
    driver: str,
    run_id: str,
    out_relpath: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "driver": driver,
        "session_id": session.session_id,
        "condition": session.condition,
        "arrangement": session.arrangement,
        "seed": session.seed,
        "dissenter_seat": session.dissenter_seat,
        "stream_set": session.stream_set,
        "n_trials": len(session.trials),
        "summary": summary,
        "model": counters,
        "path": out_relpath,
    }


# --------------------------------------------------------------------------
# Standalone driver.
# --------------------------------------------------------------------------


def run_standalone(
    session: Any,
    *,
    out_dir: Path,
    stimulus_root: Path,
    llm_kind: str,
    model: str | None,
    temperature: float,
    max_tokens: int,
    policy: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from asch.env import AschEnvironment
    from asch.metrics import AschMetricCollector, write_metrics
    from asch.model import AschDecisionModel
    from asch.population import SUBJECT_ID, confederate_agent_ids

    environment = AschEnvironment(session=session, stimulus_root=stimulus_root, agent_id=SUBJECT_ID)
    decision = AschDecisionModel(
        llm_kind=llm_kind,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        policy=policy,
        seed=session.seed,
    )
    collector = AschMetricCollector()
    scripted = [a for a in confederate_agent_ids()]

    for t in range(1, len(session.trials) + 1):
        observations = environment.observe_batch([SUBJECT_ID], t)
        actions = decision.decide_batch(observations, memories=None)
        environment.apply(actions)
        collector.collect(environment, actions, t)

    # The scripted seats never speak through the model, but the record must show
    # that they were present and silent, not absent.
    snapshot = environment.snapshot()
    snapshot["scripted_seats"] = scripted
    snapshot["model"] = decision.counters()

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "trials.json").write_text(
        json.dumps(environment.rows, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "record.json").write_text(
        json.dumps(environment.record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "snapshot.json").write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "transcript.txt").write_text(environment.prompt_transcript(), encoding="utf-8")
    summary = write_metrics(out_dir, collector.frame())

    debrief = run_debrief(environment, decision)
    if debrief is not None:
        (out_dir / "debrief.json").write_text(
            json.dumps(debrief, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        summary["debrief_recognized"] = debrief["recognized_paradigm"]
    return summary, decision.counters()


def run_debrief(environment: Any, decision: Any) -> dict[str, Any] | None:
    """The one post-task probe, stored apart and never written back (§3.3, L82)."""
    from asch.prompts import build_debrief_prompt, parse_debrief

    if decision.llm is None:
        return None
    prompt = build_debrief_prompt(history=environment.history)
    try:
        reply = decision.llm.complete([{"role": "user", "content": prompt}])
    except Exception as exc:  # a failed probe is recorded, not retried silently
        return {"answer": None, "recognized_paradigm": None, "missing": True, "error": str(exc)[:240]}
    record = parse_debrief(reply)
    record["prompt"] = prompt
    record["note"] = "Debrief probe, asked once after the final trial; not written back into trial history."
    return record


# --------------------------------------------------------------------------
# Engine driver.
# --------------------------------------------------------------------------


def run_via_engine(
    session: Any,
    *,
    out_dir: Path,
    stimulus_root: Path,
    llm_kind: str,
    model: str | None,
    temperature: float,
    max_tokens: int,
    policy: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    from socioverse.engine import build_simulator

    from asch.bundles import make_asch_bundles

    study, env_bundle, pop_bundle, sim_config = make_asch_bundles(
        session,
        stimulus_root=str(stimulus_root),
        llm_kind=llm_kind,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        policy=policy,
    )
    simulator = build_simulator(
        study=study,
        environment=env_bundle,
        population=pop_bundle,
        simulation=sim_config,
    )
    result = simulator.run()
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "engine_result.json").write_text(
        json.dumps(result if isinstance(result, dict) else str(result), ensure_ascii=False, indent=2),
        encoding="utf-8",
        default=str,
    )
    rows = getattr(getattr(simulator, "collector", None), "rows", None) or []
    summary = {}
    if rows:
        from asch.metrics import write_metrics

        summary = write_metrics(out_dir, rows)
    return summary, {"llm_kind": llm_kind, "model": model or "default", "calls": None, "fallbacks": None}


# --------------------------------------------------------------------------
# CLI.
# --------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Asch line-judgement sessions.")
    parser.add_argument("--condition", default="C1", help="C0|C1|C2|C3|C4|all")
    parser.add_argument("--session", default=None, help="single session id, e.g. C1-S03")
    parser.add_argument("--sessions", default="1-3", help="session indices within the condition, e.g. 1-12")
    parser.add_argument("--arrangement", default=None, help="restrict to A1|A2|A3")
    parser.add_argument("--llm", default="scripted", choices=("scripted", "openai"))
    parser.add_argument("--model", default=None)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--max-tokens", type=int, default=24)
    parser.add_argument("--policy", default="random", choices=("random", "first", "last", "peer"))
    parser.add_argument("--driver", default="standalone", choices=("standalone", "engine"))
    parser.add_argument("--out", default=str(ROOT / "runs"))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--stimuli", default=str(ROOT))
    parser.add_argument("--force", action="store_true", help="overwrite an existing session directory")
    parser.add_argument("--debrief", action="store_true", help="ask the post-task probe once (needs a real model)")
    return parser


def select_sessions(args: argparse.Namespace) -> list[Any]:
    from asch.conditions import CONDITION_ORDER, all_sessions, build_sessions, find_session

    if args.session:
        return [find_session(args.session)]
    indices = set(parse_seeds(args.sessions))
    conditions = CONDITION_ORDER if args.condition == "all" else (args.condition,)
    chosen = []
    for condition in conditions:
        for session in build_sessions(condition):
            if session.index + 1 in indices and (args.arrangement is None or session.arrangement == args.arrangement):
                chosen.append(session)
    if not chosen:
        raise SystemExit(f"no session matched condition={args.condition} sessions={args.sessions}")
    return chosen


def main(argv: list[str] | None = None) -> int:
    stub, cleaned = _strip_local_stub(list(sys.argv[1:] if argv is None else argv))
    if stub:
        from commshim import install

        install()
    args = build_parser().parse_args(cleaned)

    stimulus_root = Path(args.stimuli)
    from asch.stimuli import verify_stimulus_set

    try:
        verify_stimulus_set(stimulus_root)
    except FileNotFoundError:
        raise SystemExit(
            f"stimulus set missing under {stimulus_root}; run: python scripts/make_stimuli.py"
        )

    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_root = Path(args.out) / run_id
    out_root.mkdir(parents=True, exist_ok=True)

    sessions = select_sessions(args)
    driver = run_standalone if args.driver == "standalone" else run_via_engine
    entries: list[dict[str, Any]] = []
    failures = 0

    for session in sessions:
        session_dir = out_root / session.condition / session.session_id
        if session_dir.exists() and not args.force:
            print(f"skip {session.session_id}: {session_dir} exists (use --force)")
            continue
        try:
            summary, counters = driver(
                session,
                out_dir=session_dir,
                stimulus_root=stimulus_root,
                llm_kind=args.llm,
                model=args.model,
                temperature=args.temperature,
                max_tokens=args.max_tokens,
                policy=args.policy,
            )
        except Exception:
            failures += 1
            print(f"FAILED {session.session_id}")
            traceback.print_exc()
            continue
        entries.append(
            build_index_entry(
                session=session,
                summary=summary,
                counters=counters,
                driver=args.driver,
                run_id=run_id,
                out_relpath=str(session_dir.relative_to(out_root)),
            )
        )
        print(
            f"{session.session_id} {session.condition} {session.arrangement} "
            f"critical_error={summary.get('critical_error_rate')} "
            f"neutral_correct={summary.get('neutral_correct_rate')}"
        )

    index_path = out_root / "index.json"
    payload = {
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "driver": driver.__name__,
        "llm_kind": args.llm,
        "model": args.model,
        "policy": args.policy if args.llm == "scripted" else None,
        "label": (
            "engineering validation only (standalone loop, no SocioVerse2 engine run)"
            if args.driver == "standalone"
            else "engine run"
        ),
        "sessions": entries,
    }
    if index_path.exists():
        try:
            previous = json.loads(index_path.read_text(encoding="utf-8"))
            payload["sessions"] = previous.get("sessions", []) + entries
        except Exception:
            pass
    index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nwrote {index_path} ({len(entries)} session(s), {failures} failure(s))")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())