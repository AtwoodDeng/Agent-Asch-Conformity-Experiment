"""Analyse a finished run: per-condition rates, the primary contrast, the gates.

    python scripts/analyze.py --run runs/<run_id>
    python scripts/analyze.py --run runs/<run_id> --export
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Analyse an Asch run.")
    parser.add_argument("--run", required=True, help="run directory containing <condition>/<session>/metrics.json")
    parser.add_argument("--out", default=None, help="where to write analysis.json")
    parser.add_argument("--export", action="store_true", help="also write CSV tables and SUMMARY.md")
    parser.add_argument("--boot", type=int, default=5000, help="bootstrap resamples")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args(argv)

    from asch.analysis import analyse_run, write_report

    run_dir = Path(args.run)
    if not run_dir.exists():
        print(f"no such run directory: {run_dir}")
        return 1

    report = analyse_run(run_dir, n_boot=args.boot, seed=args.seed)
    target = write_report(run_dir, args.out, n_boot=args.boot, seed=args.seed)
    print(f"wrote {target}")

    print(f"\nlabel: {report['label']}  driver: {report['driver']}  sessions: {report['n_sessions']}")
    print("\ncondition  n  critical  mean_err  sd      neutral   parse")
    for condition, entry in report["conditions"].items():
        print(
            f"{condition:<10} {entry['n_sessions']:<2} {entry['n_critical']:<9} "
            f"{_fmt(entry['mean_critical_error_rate']):<9} {_fmt(entry['sd_critical_error_rate']):<7} "
            f"{_fmt(entry['mean_neutral_correct_rate']):<9} {_fmt(entry['mean_parse_rate'])}"
        )

    primary = report["primary_contrast"]
    lo, hi = primary["ci"]
    print(
        f"\nprimary {primary['contrast']}: {_fmt(primary['diff'])} "
        f"[{_fmt(lo)}, {_fmt(hi)}] -> {primary['verdict']}"
    )
    print(f"parse gate passes: {report['parse_gate']['passes']}")
    print(f"neutral gate passes: {report['neutral_gate']['passes']}")

    if args.export:
        from asch.export import export_run

        result = export_run(run_dir, n_boot=args.boot, seed=args.seed)
        print("\nexport:", json.dumps(result, ensure_ascii=False))
    return 0


def _fmt(value: object, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


if __name__ == "__main__":
    raise SystemExit(main())