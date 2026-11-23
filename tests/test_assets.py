"""Asset integrity: images, distractor streams, and the frozen hash record.

These are the artefacts a reviewer would check by hand. Automating them means a
regenerated stimulus set or edited prompt cannot slip into a run unnoticed.
"""

import json

import pytest

from asch.distractors import (
    MAX_CHARS,
    MIN_CHARS,
    STREAMS,
    check_fragment,
    check_streams,
    stream_pieces,
)
from asch.stimuli import (
    ARRANGEMENTS,
    CALIBRATION_COUNT,
    calibration_trials,
    formal_image_relpath,
    verify_stimulus_set,
)


def test_manifest_matches_the_images_on_disk(root):
    path = root / "stimuli" / "manifest.json"
    if not path.exists():
        pytest.skip("stimuli not generated yet")
    result = verify_stimulus_set(root)
    assert result["verified"] is True
    assert result["images"] == 74  # 3 arrangements x 18 + 20 calibration
    assert result["version"] == "v1"


def test_calibration_set_is_present_and_complete(root):
    directory = root / "stimuli" / "calibration"
    if not directory.exists():
        pytest.skip("stimuli not generated yet")
    images = sorted(p.name for p in directory.glob("*.png"))
    assert len(images) == CALIBRATION_COUNT == 20
    trials = calibration_trials()
    assert len(trials) == CALIBRATION_COUNT
    # every calibration trial has a line equal to its standard
    for trial in trials:
        equal = [slot for slot, _r, length in trial.lines if abs(length - trial.standard_in) < 1e-9]
        assert len(equal) == 1


def test_each_arrangement_has_eighteen_distinct_images(root):
    """18 files per arrangement; repeats are legitimate re-presentations.

    §2 L29 and the 12 = 3 comparisons x 4 presentations structure mean the same
    physical card is shown more than once in a session: a basic comparison
    appears as a neutral trial and again as a critical trial with an identical
    picture. So a session cannot have 18 unique images. What must hold is that
    image bytes are a pure function of the stimulus geometry -- two different
    stimuli may never produce the same file, which would make the code unable to
    tell them apart.
    """
    base = root / "stimuli" / "formal"
    if not base.exists():
        pytest.skip("stimuli not generated yet")
    from asch.stimuli import _sha256, build_trials

    for arrangement in ARRANGEMENTS:
        directory = base / arrangement
        names = sorted(p.name for p in directory.glob("*.png"))
        assert len(names) == 18, f"{arrangement} has {len(names)} images"
        assert len(set(names)) == 18

        # signature -> hash must be one-to-one in both directions
        by_sig = {}
        by_hash = {}
        for trial in build_trials(arrangement):
            sig = (
                round(trial.standard_in, 4),
                tuple(sorted((slot, round(length, 4)) for slot, _role, length in trial.lines)),
            )
            digest = _sha256(directory / f"{trial.trial_id}.png")
            by_sig.setdefault(sig, set()).add(digest)
            by_hash.setdefault(digest, set()).add(sig)
        for sig, digests in by_sig.items():
            assert len(digests) == 1, f"{arrangement}: one stimulus rendered {len(digests)} ways"
        for digest, sigs in by_hash.items():
            assert len(sigs) == 1, f"{arrangement}: two different stimuli share an image"


def test_repeated_trials_really_are_the_same_stimulus(root):
    """A trial that repeats a comparison must repeat its geometry exactly."""
    from asch.stimuli import build_trials

    for arrangement in ARRANGEMENTS:
        seen = {}
        for trial in build_trials(arrangement):
            sig = (
                round(trial.standard_in, 4),
                tuple(sorted((slot, round(length, 4)) for slot, _role, length in trial.lines)),
            )
            seen.setdefault(sig, []).append(trial)
        for sig, trials in seen.items():
            kinds = {t.kind for t in trials}
            correct = {t.correct for t in trials}
            # a repeated card must keep its correct answer; only the peer script differs
            assert len(correct) == 1, f"repeated stimulus changed its correct slot: {sig}"


def test_the_three_arrangements_differ_only_in_slot_assignment():
    """Same trials, same lengths: the arrangements permute labels, not geometry."""
    from asch.stimuli import build_trials

    for index in range(18):
        rows = [build_trials(a)[index] for a in ARRANGEMENTS]
        assert len({r.trial_id for r in rows}) == 1
        assert len({r.standard_in for r in rows}) == 1
        assert len({tuple(sorted(round(l, 3) for _s, _r, l in r.lines)) for r in rows}) == 1


def test_answer_key_never_appears_in_the_manifest_paths():
    """The key is a separate file; image paths carry no design hints."""
    for arrangement in ARRANGEMENTS:
        for index in range(1, 19):
            rel = formal_image_relpath(arrangement, index)
            assert rel.endswith(".png")
            assert "critical" not in rel and "error" not in rel and "correct" not in rel


def test_answer_key_file_is_consistently_shaped(root):
    path = root / "stimuli" / "answer_key.json"
    if not path.exists():
        pytest.skip("stimuli not generated yet")
    key = json.loads(path.read_text(encoding="utf-8"))
    assert key["schema"] == "asch.stimuli.answer_key/1"
    assert key["version"] == "v1"
    trials = key["trials"]
    # 3 arrangements x 18 formal trials + 20 calibration trials
    assert len(trials) == 74
    per_arrangement = {}
    kinds = {}
    for entry in trials:
        assert entry["correct"] in ("A", "B", "C")
        if entry["kind"] == "critical":
            assert entry["designated_error"] in ("A", "B", "C")
            assert entry["designated_error"] != entry["correct"]
            assert isinstance(entry["error_is_longer"], bool)
        else:
            assert entry["designated_error"] is None
        if entry["kind"] == "calibration":
            kinds["calibration"] = kinds.get("calibration", 0) + 1
        else:
            per_arrangement[entry["arrangement"]] = per_arrangement.get(entry["arrangement"], 0) + 1
    assert per_arrangement == {"A1": 18, "A2": 18, "A3": 18}
    assert kinds == {"calibration": 20}
    # trial ids are only unique within an arrangement: T01 exists in A1, A2, A3
    assert len({(e["arrangement"], e["trial_id"]) for e in trials}) == 74


# --------------------------------------------------------------------------
# Distractors.
# --------------------------------------------------------------------------


def test_streams_pass_their_own_content_rules():
    report = check_streams()
    assert report["total_pieces"] == 51
    assert report["streams"] == {"S1": 17, "S2": 17, "S3": 17}
    assert report["gap_count_per_stream"] == 17
    assert report["char_range"][0] >= MIN_CHARS
    assert report["char_range"][1] <= MAX_CHARS


def test_every_fragment_is_within_the_length_window():
    for stream_id in STREAMS:
        for piece in stream_pieces(stream_id):
            assert MIN_CHARS <= piece["chars"] <= MAX_CHARS, (stream_id, piece["gap_id"], piece["chars"])


def test_fragments_avoid_the_subjects_task_vocabulary():
    """A fragment that mentions lines or judging is a hint, not a distractor."""
    for stream_id in STREAMS:
        for piece in stream_pieces(stream_id):
            assert check_fragment(piece["text"]) == [], (stream_id, piece["gap_id"])


def test_fragment_checker_actually_rejects_bad_input():
    """Guard against a checker that passes everything."""
    assert check_fragment("比较哪条线更长？") != []
    assert check_fragment("答案：A") != []
    assert check_fragment("A 和 B 都不一样") != []


def test_stream_manifest_matches_the_streams(root):
    path = root / "distractors" / "streams.json"
    if not path.exists():
        pytest.skip("streams not generated yet")
    frozen = json.loads(path.read_text(encoding="utf-8"))
    from asch.distractors import distribution_manifest

    live = distribution_manifest()
    assert frozen["schema"] == live["schema"] == "asch.distractors/1"
    assert frozen["streams"] == live["streams"]
    assert frozen["gaps_per_stream"] == live["gaps_per_stream"] == 17
    assert frozen["invariants"] == live["invariants"]


# --------------------------------------------------------------------------
# The frozen hash record.
# --------------------------------------------------------------------------


def test_frozen_hashes_still_match_the_sources(root):
    path = root / "configs" / "hashes.json"
    if not path.exists():
        pytest.skip("hashes not frozen yet")
    import hashlib

    recorded = json.loads(path.read_text(encoding="utf-8"))
    assert recorded["schema"] == "asch.hashes/1"
    drifted = []
    for group in ("sources", "artifacts"):
        for rel, digest in recorded[group].items():
            target = root / rel
            if not target.exists():
                drifted.append(f"{rel}: missing")
                continue
            actual = hashlib.sha256(target.read_bytes()).hexdigest()
            if actual != digest:
                drifted.append(f"{rel}: changed since freeze")
    assert not drifted, (
        "frozen artefact changed without a version bump: "
        + "; ".join(drifted)
        + " (re-run scripts/freeze_hashes.py --version <new> if intentional)"
    )


def test_prompts_pass_their_own_forbidden_fragment_check():
    from asch.prompts import check_prompts

    report = check_prompts()
    assert report["forbidden_fragment_count"] >= 30
    for key, value in report.items():
        if isinstance(value, str):
            assert "从众" not in value
            assert "同盟" not in value