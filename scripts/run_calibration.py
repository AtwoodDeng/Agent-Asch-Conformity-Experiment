"""P1: independent calibration -- check the model can actually see the stimuli.

Runs the frozen 20-trial calibration series through a real model (``--llm
openai``) with NO peer answers and NO correctness feedback, and scores the
no-pressure accuracy. ``实验规划.md`` §3.1 / §8 gates the formal run on >= 95%.

    python scripts/run_calibration.py --llm openai --sessions 3 --out runs --run-id calib1

``--llm scripted`` is a blind policy and will (correctly) fail the 95% gate; it is
only useful for checking this runner's own wiring.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PASS_THRESHOLD = 0.95


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--sessions", type=int, default=3, help="independent calibration sessions (20 trials each)")
    p.add_argument("--llm", default="openai", choices=("scripted", "openai"))
    p.add_argument("--model", default=None, help="model id override (default: SV_LLM_MODEL)")
    p.add_argument("--temperature", type=float, default=0.7)
    p.add_argument("--max-tokens", type=int, default=24)
    p.add_argument("--policy", default="random", choices=("random", "first", "last", "peer"))
    p.add_argument("--stimuli", default=str(ROOT), help="repo root holding stimuli/")
    p.add_argument("--out", default=str(ROOT / "runs"))
    p.add_argument("--run-id", default=None)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    from asch.model import AschDecisionModel
    from asch.prompts import build_prompt
    from asch.stimuli import calibration_image_relpath, calibration_trials
    from socioverse.schemas import Observation

    trials = calibration_trials()
    if len(trials) != 20:
        raise SystemExit(f"expected 20 calibration trials, got {len(trials)}")

    stimulus_root = Path(args.stimuli)
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = Path(args.out) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    last_model_name = None
    for session_index in range(1, args.sessions + 1):
        session_id = f"CAL-S{session_index:02d}"
        # Fresh model per session: each session is an independent subject with
        # its own history (calibration has no history, but the seed differs).
        model = AschDecisionModel(
            llm_kind=args.llm,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            policy=args.policy,
            seed=session_index,
        )
        last_model_name = model.model_name

        for trial in trials:
            prompt = build_prompt(
                condition="C0",          # solo: no peer answers
                index=trial.index,
                n_trials=len(trials),
                speeches=[],
                image_hint="[附上线段图像]",
            )
            image_path = str(stimulus_root / calibration_image_relpath(trial.trial_id))
            observation = Observation(
                agent_id="P07",
                step=trial.index,
                macro_physical={},
                macro_information={},
                local_physical={
                    "prompt": prompt,
                    "image_path": image_path,
                    "session_id": session_id,
                    "trial_index": trial.index,
                    "trial_id": trial.trial_id,
                },
            )
            action = model.decide_batch([observation])[0]
            answer = action.payload.get("answer")
            raw = action.payload.get("raw")
            source = getattr(action, "source", None) or action.payload.get("source")
            rows.append(
                {
                    "session_id": session_id,
                    "trial_index": trial.index,
                    "trial_id": trial.trial_id,
                    "correct": trial.correct,
                    "answer": answer,
                    "parsed": answer is not None,
                    "is_correct": (answer == trial.correct) if answer is not None else False,
                    "source": source,
                    "raw": raw,
                }
            )

        session_rows = [r for r in rows if r["session_id"] == session_id]
        print(
            f"{session_id}: {sum(r['is_correct'] for r in session_rows)}/20 correct, "
            f"{sum(not r['parsed'] for r in session_rows)} unparsed, "
            f"fallbacks={model.fallback_count}"
        )

    total = len(rows)
    parsed = [r for r in rows if r["parsed"]]
    correct = [r for r in rows if r["is_correct"]]
    accuracy = (len(correct) / total) if total else 0.0
    parse_rate = (len(parsed) / total) if total else 0.0

    per_session: dict[str, dict] = {}
    for r in rows:
        bucket = per_session.setdefault(r["session_id"], {"n": 0, "correct": 0, "unparsed": 0})
        bucket["n"] += 1
        bucket["correct"] += int(r["is_correct"])
        bucket["unparsed"] += int(not r["parsed"])

    summary = {
        "run_id": run_id,
        "llm": args.llm,
        "model": last_model_name,
        "sessions": args.sessions,
        "trials_per_session": len(trials),
        "n_judgements": total,
        "n_correct": len(correct),
        "n_unparsed": total - len(parsed),
        "accuracy": accuracy,
        "parse_rate": parse_rate,
        "pass_threshold": PASS_THRESHOLD,
        "passes": accuracy >= PASS_THRESHOLD,
        "per_session": per_session,
        "note": (
            "No peer answers, no feedback. Accuracy is scored against stimuli/answer_key.json. "
            "A blind scripted policy fails this gate by design."
        ),
    }

    (out_dir / "calibration.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "trials.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\naccuracy={accuracy:.3f} (threshold {PASS_THRESHOLD})  parse_rate={parse_rate:.3f}  "
          f"-> {'PASS' if summary['passes'] else 'FAIL'}")
    print(f"wrote {out_dir}")
    return 0 if summary["passes"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
