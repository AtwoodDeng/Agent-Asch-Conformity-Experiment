"""Freeze the design into ``configs/`` and record content hashes.

The plan requires that configs and prompts are frozen artefacts with hashes, and
that any change bumps a version (§3.2, §7). This script writes:
``configs/design.json``, one file per condition, and ``configs/hashes.json``.

Re-run it only when a design table deliberately changes: the hash file's
``version`` must be bumped at the same time, and the diff in ``design.json`` is
what an auditor reads to see what moved.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

HASHED_SOURCES = (
    "asch/stimuli.py",
    "asch/conditions.py",
    "asch/prompts.py",
    "asch/distractors.py",
)

FROZEN_ARTIFACTS = (
    "stimuli/manifest.json",
    "stimuli/answer_key.json",
    "distractors/streams.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_design() -> dict[str, Any]:
    from asch.conditions import design_manifest
    from asch.distractors import distribution_manifest

    design = design_manifest()
    design["distractors"] = distribution_manifest()
    return design


def build_condition_files() -> dict[str, list[dict[str, Any]]]:
    from asch.conditions import CONDITION_ORDER, build_sessions

    out: dict[str, list[dict[str, Any]]] = {}
    for condition in CONDITION_ORDER:
        out[condition] = [session.to_dict() for session in build_sessions(condition)]
    return out


def ensure_importable() -> None:
    """Make the runtime modules importable for their constants.

    ``asch/model.py`` registers its class at import time, so reading its
    constants requires ``socioverse`` (or the local stub). The stub changes
    nothing about the constants read here.
    """
    try:
        import socioverse  # noqa: F401
    except ModuleNotFoundError:
        sys.path.insert(0, str(ROOT / "scripts"))
        from commshim import install

        install()


def build_model_config() -> dict[str, Any]:
    ensure_importable()
    from asch.model import DEFAULT_SCRIPTED_POLICY, LLM_KINDS, LLM_PROVIDERS, SCRIPTED_POLICIES

    return {
        "llm_kinds": list(LLM_KINDS),
        "default_llm_kind": "scripted",
        "llm_providers": {key: dict(cfg) for key, cfg in LLM_PROVIDERS.items()},
        "scripted_policies": list(SCRIPTED_POLICIES),
        "default_scripted_policy": DEFAULT_SCRIPTED_POLICY,
        "sampling": {
            "temperature": 0.7,
            "max_tokens": 24,
            "max_workers": 4,
            "prompt_lang": "zh",
            "note": (
                "max_tokens=24 allows a letter plus a short reason; the parser accepts a "
                "bare letter and rejects replies naming more than one slot."
            ),
        },
        "answer_key_visibility": "never in observation; used only by the collector and the analysis",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Freeze design configs and hashes.")
    parser.add_argument("--version", default="v1")
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--check", action="store_true", help="verify existing hashes instead of writing")
    args = parser.parse_args(argv)

    root = Path(args.root)
    configs = root / "configs"

    sources = {rel: sha256_file(root / rel) for rel in HASHED_SOURCES if (root / rel).exists()}
    artifacts = {rel: sha256_file(root / rel) for rel in FROZEN_ARTIFACTS if (root / rel).exists()}
    missing = [rel for rel in HASHED_SOURCES + FROZEN_ARTIFACTS if not (root / rel).exists()]

    hashes: dict[str, Any] = {
        "schema": "asch.hashes/1",
        "version": args.version,
        "sources": sources,
        "artifacts": artifacts,
    }

    if args.check:
        path = configs / "hashes.json"
        if not path.exists():
            print(f"missing {path}; run without --check first")
            return 1
        recorded = json.loads(path.read_text(encoding="utf-8"))
        problems = []
        for group in ("sources", "artifacts"):
            for rel, digest in recorded.get(group, {}).items():
                actual = sources.get(rel) or artifacts.get(rel)
                if actual is None:
                    problems.append(f"{rel}: recorded but missing on disk")
                elif actual != digest:
                    problems.append(f"{rel}: hash changed (recorded {digest[:12]}, now {actual[:12]})")
        if problems:
            print("HASH DRIFT:")
            for problem in problems:
                print("  -", problem)
            return 1
        print(f"hashes ok (version {recorded.get('version')}, {len(sources)} sources, {len(artifacts)} artifacts)")
        return 0

    configs.mkdir(parents=True, exist_ok=True)
    design = build_design()
    (configs / "design.json").write_text(json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8")

    conditions = build_condition_files()
    for condition, sessions in conditions.items():
        (configs / f"condition_{condition}.json").write_text(
            json.dumps(
                {
                    "condition": condition,
                    "description": design["conditions"][condition],
                    "sessions": sessions,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    (configs / "model.json").write_text(
        json.dumps(build_model_config(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (configs / "hashes.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"wrote configs/ (version {args.version})")
    print(f"  design.json: {len(design.get('sessions', []))} sessions, {len(design.get('conditions', {}))} conditions")
    print(f"  {len(conditions)} condition files")
    print(f"  hashes: {len(sources)} sources, {len(artifacts)} artifacts")
    if missing:
        print("  NOTE missing on disk:", ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())