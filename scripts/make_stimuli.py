"""Generate the stimulus set and freeze its hashes.

Run once before any session, and again only if the design changes::

    python scripts/make_stimuli.py
    python scripts/freeze_hashes.py

The plan requires frozen designs and prompts with hashes, and a version bump on
any change (§3.2, §7). Regenerating stimuli without bumping the version is a
design change with no audit trail, so this script refuses to overwrite an
existing frozen set unless ``--force`` is passed.
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
    parser = argparse.ArgumentParser(description="Render the stimulus images.")
    parser.add_argument("--force", action="store_true", help="overwrite an existing stimulus set")
    parser.add_argument("--version", default="v1")
    parser.add_argument("--root", default=str(ROOT))
    args = parser.parse_args(argv)

    from asch.stimuli import check_design, verify_stimulus_set, write_stimulus_set

    design = check_design()
    print("design check: ok")
    print(json.dumps(design, ensure_ascii=False, indent=2))

    root = Path(args.root)
    try:
        result = write_stimulus_set(root, force=args.force, version=args.version)
    except FileExistsError as exc:
        print(f"refusing to overwrite: {exc}\nuse --force and bump --version if this is intentional")
        return 1
    print("written:", json.dumps(result, ensure_ascii=False))
    print("verified:", json.dumps(verify_stimulus_set(root), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())