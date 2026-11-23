"""Line-judgement stimuli: frozen design table plus deterministic renderer.

What is mirrored from Asch (1956), checked against the local scan
(``Docs/people-will-conform.pdf``, OCR in ``..\\..\\tmp\\pdfs\\asch1956.txt``):

* vertical black strips pasted on white cards, strips **3/8 inch** wide;
* all strips share a common lower end, positioned **1/2 inch** above the lower
  edge of the card, so lengths differ only at the top;
* the comparison strips are separated by **1 3/4 inches** (centre to centre);
* the comparison strips are numbered from left to right -- here the labels are
  ``A``, ``B``, ``C`` rather than ``1``, ``2``, ``3`` so that a single-letter
  answer is never confused with a line length;
* one standard strip on its own card, centered; three comparison strips on a
  second card; exactly one comparison strip equals the standard;
* 18 trials = 6 neutral + 12 critical; the 12 critical trials are
  **3 basic comparisons x 2 discrepancy sizes x 2 halves** of the series.

What is *this project's own design* (the plan says so explicitly: the concrete
stimuli, seats and trial order are local design, not a claim of item-by-item
replication):

* the exact standard lengths and discrepancies (frozen in ``BASIC_COMPARISONS``
  below) -- chosen to keep every designated-error shape inside the canvas and
  to balance longer/shorter designated errors 6/6 over the critical trials;
* the position of the neutral trials (1, 2, 5 in the first half; 10, 11, 14 in
  the second half, i.e. Asch's a, b, c and d, e, f pattern shifted by the half);
* the A/B/C label assignment per trial, held to exact balance: each letter is
  the correct answer 6 times over 18 trials and 4 times over the 12 critical
  trials, and is the designated error 4 times over the critical trials;
* the light card frames and the label band below the comparison card (added so
  the image is legible to a vision model; the 1956 figures sat in a 1/2 inch
  band, which is too small at a sane resolution);
* three frozen numeralisations ("arrangements", A1-A3) that rotate the A/B/C
  labels; rotating labels leaves every balance invariant intact and lets the
  four sessions of each condition cover all three arrangements.

Nothing numeric, no answer marker and no critical/neutral marker is drawn into
an image: an image contains black strips, light card frames and the letters
A/B/C only. The answer key lives in a separate JSON file that is never part of
a subject-visible payload.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

# --------------------------------------------------------------------------
# Canvas geometry. One inch is ``PPI`` pixels; every dimension below is inches.
# --------------------------------------------------------------------------

PPI = 100
CARD_W_IN = 6.0
CARD_H_IN = 9.0
STRIP_W_IN = 0.375          # 3/8 inch black strip
BOTTOM_MARGIN_IN = 0.5      # lower ends 1/2 inch above the lower card edge
COMP_SPACING_IN = 1.75      # comparison strips 1 3/4 inch apart
CARD_GAP_IN = 1.0
MARGIN_IN = 0.15            # blank border so the card frames are not clipped
LABEL_BAND_IN = 0.65
LABEL_FONT_IN = 0.5
FRAME_GREY = (216, 216, 216)
INK = (0, 0, 0)
PAPER = (255, 255, 255)

IMAGE_W_PX = int(round((2 * CARD_W_IN + CARD_GAP_IN + 2 * MARGIN_IN) * PPI))
IMAGE_H_PX = int(round((CARD_H_IN + LABEL_BAND_IN + 2 * MARGIN_IN) * PPI))

SLOTS = ("A", "B", "C")

# --------------------------------------------------------------------------
# Frozen stimulus parameters.
#
# Each basic comparison has a standard length and, for the moderate and the
# extreme presentation, the offset of the *designated error* line (``err``) and
# of the remaining distractor (``other``), in inches relative to the standard.
# The extreme offset is strictly larger in magnitude than the moderate one, so
# "moderate"/"extreme" mean what they say. Signs alternate so that over the 12
# critical trials the designated error is the longer line 6 times and the
# shorter line 6 times.
# --------------------------------------------------------------------------

BASIC_COMPARISONS: list[dict[str, Any]] = [
    {
        "id": "B1",
        "standard_in": 3.75,
        "moderate": {"err": +0.75, "other": -1.25},
        "extreme": {"err": +1.25, "other": -1.75},
    },
    {
        "id": "B2",
        "standard_in": 5.00,
        "moderate": {"err": -1.00, "other": +1.50},
        "extreme": {"err": -1.50, "other": +2.00},
    },
    {
        "id": "B3",
        "standard_in": 6.25,
        "moderate": {"err": -0.75, "other": +1.25},
        "extreme": {"err": +1.00, "other": -1.50},
    },
]

SIZES = ("moderate", "extreme")

# --------------------------------------------------------------------------
# The 18-trial series. ``pos`` is 1-based; ``correct``/``error`` are slot
# letters *before* the arrangement rotation. ``error`` is ``None`` for neutral
# trials (they carry no designated error; both distractors are simply wrong).
# --------------------------------------------------------------------------

TRIAL_DESIGN: list[dict[str, Any]] = [
    {"pos": 1, "kind": "neutral", "basic": "B1", "size": "moderate", "correct": "A", "error": None},
    {"pos": 2, "kind": "neutral", "basic": "B2", "size": "moderate", "correct": "B", "error": None},
    {"pos": 3, "kind": "critical", "basic": "B1", "size": "moderate", "correct": "A", "error": "B"},
    {"pos": 4, "kind": "critical", "basic": "B2", "size": "moderate", "correct": "B", "error": "A"},
    {"pos": 5, "kind": "neutral", "basic": "B3", "size": "moderate", "correct": "C", "error": None},
    {"pos": 6, "kind": "critical", "basic": "B3", "size": "moderate", "correct": "C", "error": "A"},
    {"pos": 7, "kind": "critical", "basic": "B1", "size": "extreme", "correct": "A", "error": "C"},
    {"pos": 8, "kind": "critical", "basic": "B2", "size": "extreme", "correct": "B", "error": "C"},
    {"pos": 9, "kind": "critical", "basic": "B3", "size": "extreme", "correct": "C", "error": "B"},
    {"pos": 10, "kind": "neutral", "basic": "B1", "size": "moderate", "correct": "A", "error": None},
    {"pos": 11, "kind": "neutral", "basic": "B2", "size": "moderate", "correct": "B", "error": None},
    {"pos": 12, "kind": "critical", "basic": "B1", "size": "extreme", "correct": "A", "error": "B"},
    {"pos": 13, "kind": "critical", "basic": "B2", "size": "extreme", "correct": "B", "error": "A"},
    {"pos": 14, "kind": "neutral", "basic": "B3", "size": "moderate", "correct": "C", "error": None},
    {"pos": 15, "kind": "critical", "basic": "B3", "size": "extreme", "correct": "C", "error": "B"},
    {"pos": 16, "kind": "critical", "basic": "B1", "size": "moderate", "correct": "A", "error": "C"},
    {"pos": 17, "kind": "critical", "basic": "B2", "size": "moderate", "correct": "B", "error": "C"},
    {"pos": 18, "kind": "critical", "basic": "B3", "size": "moderate", "correct": "C", "error": "A"},
]

TRIAL_COUNT = len(TRIAL_DESIGN)
CRITICAL_COUNT = sum(1 for t in TRIAL_DESIGN if t["kind"] == "critical")
NEUTRAL_COUNT = TRIAL_COUNT - CRITICAL_COUNT

# Three frozen numeralisations; only the A/B/C labels rotate.
ARRANGEMENTS: dict[str, int] = {"A1": 0, "A2": 1, "A3": 2}

# Neutral trials per Asch's a, b, c (trials 1, 2, 5) and d, e, f (trials 7, 8,
# 11 of his series). Our second half starts at position 10, so the second
# neutral block sits at 10, 11, 14.
NEUTRAL_POSITIONS = (1, 2, 5, 10, 11, 14)
CRITICAL_POSITIONS = (3, 4, 6, 7, 8, 9, 12, 13, 15, 16, 17, 18)

# The independent calibration series (20 trials, no social information).
CALIBRATION_STANDARDS = (2.5, 3.5, 4.5, 5.5, 6.5)
CALIBRATION_DELTAS = {"err": +0.50, "other": -0.75}
CALIBRATION_COUNT = 20


# --------------------------------------------------------------------------
# Derived values and the small data model.
# --------------------------------------------------------------------------


def rotate_slot(slot: str, steps: int) -> str:
    """Rotate a slot letter by ``steps`` positions (A->B->C->A)."""
    return SLOTS[(SLOTS.index(slot) + steps) % len(SLOTS)]


def basic_by_id(basic_id: str) -> dict[str, Any]:
    for basic in BASIC_COMPARISONS:
        if basic["id"] == basic_id:
            return basic
    raise KeyError(f"unknown basic comparison {basic_id!r}")


def comparison_lengths(basic_id: str, size: str) -> dict[str, float]:
    """Standard length plus the two distractor lengths, in inches."""
    basic = basic_by_id(basic_id)
    deltas = basic[size]
    standard = float(basic["standard_in"])
    return {
        "standard": standard,
        "error": round(standard + float(deltas["err"]), 4),
        "other": round(standard + float(deltas["other"]), 4),
    }


@dataclass(frozen=True)
class Trial:
    """One rendered judgement: a standard line and three comparison lines."""

    trial_id: str
    index: int                      # 1-based position in the series
    kind: str                       # "neutral" | "critical"
    basic: str
    size: str
    arrangement: str
    standard_in: float
    lines: tuple[tuple[str, str, float], ...]   # (slot, role, length_in)
    correct: str
    error: str | None
    other: str
    meta: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def is_critical(self) -> bool:
        return self.kind == "critical"

    def length_of(self, role: str) -> float:
        for slot, r, length in self.lines:
            if r == role:
                return length
        raise KeyError(role)

    def slot_of(self, role: str) -> str:
        for slot, r, _length in self.lines:
            if r == role:
                return slot
        raise KeyError(role)

    def to_dict(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "index": self.index,
            "kind": self.kind,
            "basic": self.basic,
            "size": self.size,
            "arrangement": self.arrangement,
            "standard_in": self.standard_in,
            "lines": [
                {"slot": slot, "role": role, "length_in": length}
                for slot, role, length in self.lines
            ],
            "correct": self.correct,
            "error": self.error,
            "other": self.other,
        }

    def answer_key(self) -> dict[str, Any]:
        return {
            "trial_id": self.trial_id,
            "index": self.index,
            "kind": self.kind,
            "arrangement": self.arrangement,
            "correct": self.correct,
            "designated_error": self.error,
            "other_wrong": self.other,
            "standard_in": self.standard_in,
            "error_is_longer": (
                None
                if self.error is None
                else self.length_of("error") > self.standard_in
            ),
        }


def _build_trial(row: dict[str, Any], arrangement: str) -> Trial:
    steps = ARRANGEMENTS[arrangement]
    lengths = comparison_lengths(row["basic"], row["size"])
    correct = rotate_slot(row["correct"], steps)
    error = rotate_slot(row["error"], steps) if row["error"] else None

    assigned: dict[str, tuple[str, float]] = {correct: ("correct", lengths["standard"])}
    if error is not None:
        assigned[error] = ("error", lengths["error"])
        free = [s for s in SLOTS if s not in assigned]
        assigned[free[0]] = ("other", lengths["other"])
        other = free[0]
    else:
        # Neutral trial: no designated error, one longer and one shorter
        # distractor. The shorter one keeps the "other" role so that
        # ``other`` always names a real single slot.
        longer, shorter = max(lengths["error"], lengths["other"]), min(lengths["error"], lengths["other"])
        free = [s for s in SLOTS if s not in assigned]
        assigned[free[0]] = ("other", shorter)
        assigned[free[1]] = ("distractor", longer)
        other = free[0]

    lines = tuple((slot, assigned[slot][0], assigned[slot][1]) for slot in SLOTS)
    return Trial(
        trial_id=f"T{row['pos']:02d}",
        index=int(row["pos"]),
        kind=str(row["kind"]),
        basic=str(row["basic"]),
        size=str(row["size"]),
        arrangement=arrangement,
        standard_in=float(lengths["standard"]),
        lines=lines,
        correct=correct,
        error=error,
        other=other,
        meta={"rotation_steps": steps},
    )


def build_trials(arrangement: str = "A1") -> list[Trial]:
    """The 18 trials of one arrangement, in presentation order."""
    if arrangement not in ARRANGEMENTS:
        raise KeyError(f"unknown arrangement {arrangement!r}; expected one of {sorted(ARRANGEMENTS)}")
    return [_build_trial(row, arrangement) for row in TRIAL_DESIGN]


def calibration_trials() -> list[Trial]:
    """20 independent calibration trials: no social information, one equal line.

    Five standard lengths, each with four label rotations, so every standard
    appears four times. Letters are assigned by rotation, hence the split is
    A 7 / B 7 / C 6 rather than exactly 7/7/7 for 20 trials; calibration only
    needs a pass rate, not a balanced design.
    """
    trials: list[Trial] = []
    for i in range(CALIBRATION_COUNT):
        standard = CALIBRATION_STANDARDS[i % len(CALIBRATION_STANDARDS)]
        steps = i % len(SLOTS)
        correct_slot = rotate_slot("A", steps)
        longer_slot = rotate_slot("B", steps)
        shorter_slot = rotate_slot("C", steps)
        lengths = {
            "correct": standard,
            "longer": round(standard + CALIBRATION_DELTAS["err"], 4),
            "shorter": round(standard + CALIBRATION_DELTAS["other"], 4),
        }
        assigned = {
            correct_slot: ("correct", lengths["correct"]),
            longer_slot: ("other", lengths["longer"]),
            shorter_slot: ("distractor", lengths["shorter"]),
        }
        lines = tuple((slot, assigned[slot][0], assigned[slot][1]) for slot in SLOTS)
        trials.append(
            Trial(
                trial_id=f"K{i + 1:02d}",
                index=i + 1,
                kind="calibration",
                basic="CAL",
                size="calibration",
                arrangement="A1",
                standard_in=standard,
                lines=lines,
                correct=correct_slot,
                error=None,
                other=shorter_slot,
                meta={"rotation_steps": steps},
            )
        )
    return trials


# --------------------------------------------------------------------------
# Rendering.
# --------------------------------------------------------------------------


def _font(px: int) -> ImageFont.ImageFont:
    for name in ("arialbd.ttf", "Arial Bold.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, px)
        except Exception:  # noqa: BLE001 - font availability is environment specific
            continue
    try:
        return ImageFont.load_default(size=px)
    except TypeError:                                   # Pillow < 10.1
        return ImageFont.load_default()


def _margin_px() -> int:
    return int(round(MARGIN_IN * PPI))


def _card_origin(which: str) -> int:
    left = 0 if which == "standard" else CARD_W_IN + CARD_GAP_IN
    return int(round(MARGIN_IN * PPI + left * PPI))


def _strip_box(x_center_px: float, length_in: float) -> tuple[int, int, int, int]:
    """Pixel box of a vertical strip: common lower end, length upward."""
    bottom = int(round(MARGIN_IN * PPI + CARD_H_IN * PPI - BOTTOM_MARGIN_IN * PPI))
    top = int(round(bottom - length_in * PPI))
    half = STRIP_W_IN * PPI / 2.0
    left = int(round(x_center_px - half))
    right = int(round(x_center_px + half))
    return left, top, right, bottom


def render(trial: Trial) -> Image.Image:
    """Render one trial to a white PNG image (no numbers, no markers)."""
    image = Image.new("RGB", (IMAGE_W_PX, IMAGE_H_PX), PAPER)
    draw = ImageDraw.Draw(image)

    # Faint card frames keep the two cards distinguishable at low resolution.
    card_px = int(CARD_W_IN * PPI)
    card_py = int(CARD_H_IN * PPI)
    for which in ("standard", "comparison"):
        x0 = _card_origin(which)
        y0 = _margin_px()
        draw.rectangle([x0, y0, x0 + card_px - 1, y0 + card_py - 1], outline=FRAME_GREY, width=2)

    # Standard line, centered on its own card.
    std_center = _card_origin("standard") + card_px / 2.0
    left, top, right, bottom = _strip_box(std_center, trial.standard_in)
    draw.rectangle([left, top, right, bottom], fill=INK)

    # Three comparison lines on the second card, evenly spaced around its centre.
    comp_center = _card_origin("comparison") + card_px / 2.0
    spacing_px = COMP_SPACING_IN * PPI
    centers = [comp_center - spacing_px, comp_center, comp_center + spacing_px]
    font = _font(int(LABEL_FONT_IN * PPI))
    label_y = int(round(_margin_px() + card_py + LABEL_BAND_IN * PPI / 2.0))
    for slot, idx in zip(SLOTS, range(len(SLOTS))):
        length = next(length for s, _role, length in trial.lines if s == slot)
        left, top, right, bottom = _strip_box(centers[idx], length)
        draw.rectangle([left, top, right, bottom], fill=INK)
        draw.text(
            (centers[idx], label_y),
            slot,
            fill=INK,
            font=font,
            anchor="mm",
        )
    return image


# --------------------------------------------------------------------------
# Writing the frozen set, the manifest and the answer key.
# --------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def formal_image_relpath(arrangement: str, trial_id: str) -> str:
    return f"stimuli/formal/{arrangement}/{trial_id}.png"


def calibration_image_relpath(trial_id: str) -> str:
    return f"stimuli/calibration/{trial_id}.png"


def check_design() -> dict[str, Any]:
    """Assert every frozen balance invariant; returns the counts actually met."""
    errors: list[str] = []

    kinds = [row["kind"] for row in TRIAL_DESIGN]
    if len(TRIAL_DESIGN) != 18:
        errors.append(f"expected 18 trials, found {len(TRIAL_DESIGN)}")
    if kinds[:2] != ["neutral", "neutral"]:
        errors.append(f"the first two trials must be neutral, found {kinds[:2]}")
    neutral_pos = tuple(row["pos"] for row in TRIAL_DESIGN if row["kind"] == "neutral")
    critical_pos = tuple(row["pos"] for row in TRIAL_DESIGN if row["kind"] == "critical")
    if neutral_pos != NEUTRAL_POSITIONS:
        errors.append(f"neutral positions {neutral_pos} != frozen {NEUTRAL_POSITIONS}")
    if critical_pos != CRITICAL_POSITIONS:
        errors.append(f"critical positions {critical_pos} != frozen {CRITICAL_POSITIONS}")
    if sorted(neutral_pos + critical_pos) != list(range(1, 19)):
        errors.append("trial positions do not cover 1..18 exactly once")

    # Each half holds every basic comparison twice: once moderate, once extreme.
    for half, positions in (("first", range(1, 10)), ("second", range(10, 19))):
        cells = [
            (row["basic"], row["size"])
            for row in TRIAL_DESIGN
            if row["kind"] == "critical" and row["pos"] in positions
        ]
        expected = [(b["id"], s) for b in BASIC_COMPARISONS for s in SIZES]
        if sorted(cells) != sorted(expected):
            errors.append(f"{half} half critical cells {sorted(cells)} != {sorted(expected)}")

    for arrangement in ARRANGEMENTS:
        trials = build_trials(arrangement)
        overall = {slot: 0 for slot in SLOTS}
        critical = {slot: 0 for slot in SLOTS}
        errorslots = {slot: 0 for slot in SLOTS}
        longer = shorter = 0
        for trial in trials:
            overall[trial.correct] += 1
            if trial.is_critical:
                critical[trial.correct] += 1
                assert trial.error is not None
                errorslots[trial.error] += 1
                if trial.error == trial.correct:
                    errors.append(f"{arrangement} {trial.trial_id}: error == correct")
                if trial.length_of("error") > trial.standard_in:
                    longer += 1
                else:
                    shorter += 1
            # Exactly one comparison line matches the standard.
            matches = [slot for slot, _role, length in trial.lines if abs(length - trial.standard_in) < 1e-9]
            if len(matches) != 1:
                errors.append(f"{arrangement} {trial.trial_id}: {len(matches)} equal lines")
            if matches and matches[0] != trial.correct:
                errors.append(f"{arrangement} {trial.trial_id}: equal line is {matches[0]} not {trial.correct}")
            lengths = [length for _slot, _role, length in trial.lines]
            if len(set(lengths)) != 3:
                errors.append(f"{arrangement} {trial.trial_id}: duplicate comparison lengths {lengths}")
            if min(lengths) <= 0:
                errors.append(f"{arrangement} {trial.trial_id}: non-positive length")
            if max(lengths) > CARD_H_IN - BOTTOM_MARGIN_IN - 0.25:
                errors.append(f"{arrangement} {trial.trial_id}: line too long for the card")
        if overall != {slot: TRIAL_COUNT // 3 for slot in SLOTS}:
            errors.append(f"{arrangement} correct-slot counts {overall} != 6 each")
        if critical != {slot: CRITICAL_COUNT // 3 for slot in SLOTS}:
            errors.append(f"{arrangement} critical correct-slot counts {critical} != 4 each")
        if errorslots != {slot: CRITICAL_COUNT // 3 for slot in SLOTS}:
            errors.append(f"{arrangement} designated-error slot counts {errorSlots} != 4 each")
        if (longer, shorter) != (6, 6):
            errors.append(f"{arrangement} designated-error direction {longer}/{shorter} != 6/6")

    if errors:
        raise AssertionError("stimulus design violates its own invariants:\n  " + "\n  ".join(errors))
    return {
        "trials": TRIAL_COUNT,
        "critical": CRITICAL_COUNT,
        "neutral": NEUTRAL_COUNT,
        "neutral_positions": list(NEUTRAL_POSITIONS),
        "critical_positions": list(CRITICAL_POSITIONS),
        "arrangements": list(ARRANGEMENTS),
        "correct_slot_counts": {slot: TRIAL_COUNT // 3 for slot in SLOTS},
        "critical_correct_slot_counts": {slot: CRITICAL_COUNT // 3 for slot in SLOTS},
        "critical_error_slot_counts": {slot: CRITICAL_COUNT // 3 for slot in SLOTS},
        "error_direction_counts": {"longer": 6, "shorter": 6},
    }


def geometry() -> dict[str, Any]:
    return {
        "ppi": PPI,
        "image_px": [IMAGE_W_PX, IMAGE_H_PX],
        "card_in": [CARD_W_IN, CARD_H_IN],
        "strip_width_in": STRIP_W_IN,
        "bottom_margin_in": BOTTOM_MARGIN_IN,
        "comparison_spacing_in": COMP_SPACING_IN,
        "card_gap_in": CARD_GAP_IN,
        "label_band_in": LABEL_BAND_IN,
        "label_font_in": LABEL_FONT_IN,
        "ink_rgb": list(INK),
        "paper_rgb": list(PAPER),
        "frame_rgb": list(FRAME_GREY),
    }


def write_stimulus_set(root: str | Path, force: bool = False, version: str = "v1") -> dict[str, Any]:
    """Render the formal set for every arrangement plus the calibration set.

    Writes ``stimuli/manifest.json`` (sizes, hashes, design table) and
    ``stimuli/answer_key.json``. Refuses to overwrite an existing manifest
    unless ``force`` is set, because a frozen set must not drift silently.
    """
    root = Path(root)
    manifest_path = root / "stimuli" / "manifest.json"
    key_path = root / "stimuli" / "answer_key.json"
    if manifest_path.exists() and not force:
        raise FileExistsError(
            f"{manifest_path} already exists; pass force=True (or --force) to regenerate, "
            "and bump the stimulus version if the images actually change"
        )

    check_design()
    files: list[dict[str, Any]] = []
    answer_key: list[dict[str, Any]] = []

    for arrangement in ARRANGEMENTS:
        for trial in build_trials(arrangement):
            relpath = formal_image_relpath(arrangement, trial.trial_id)
            path = root / relpath
            path.parent.mkdir(parents=True, exist_ok=True)
            render(trial).save(path, format="PNG", optimize=True)
            files.append(
                {
                    "trial_id": trial.trial_id,
                    "index": trial.index,
                    "kind": trial.kind,
                    "arrangement": arrangement,
                    "set": "formal",
                    "path": relpath,
                    "bytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
            answer_key.append(trial.answer_key())

    for trial in calibration_trials():
        relpath = calibration_image_relpath(trial.trial_id)
        path = root / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        render(trial).save(path, format="PNG", optimize=True)
        files.append(
            {
                "trial_id": trial.trial_id,
                "index": trial.index,
                "kind": trial.kind,
                "arrangement": "A1",
                "set": "calibration",
                "path": relpath,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
        answer_key.append(trial.answer_key())

    manifest = {
        "schema": "asch.stimuli.manifest/1",
        "version": version,
        "generator": "asch.stimuli.write_stimulus_set",
        "design": check_design(),
        "geometry": geometry(),
        "basic_comparisons": BASIC_COMPARISONS,
        "trial_design": TRIAL_DESIGN,
        "arrangements": ARRANGEMENTS,
        "calibration": {
            "count": CALIBRATION_COUNT,
            "standards_in": list(CALIBRATION_STANDARDS),
            "deltas_in": CALIBRATION_DELTAS,
        },
        "answer_key_path": "stimuli/answer_key.json",
        "files": files,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_text(
        json.dumps(
            {
                "schema": "asch.stimuli.answer_key/1",
                "version": version,
                "note": "Never send this file, or any field of it, to a subject.",
                "trials": answer_key,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "manifest": str(manifest_path),
        "answer_key": str(key_path),
        "images": len(files),
        "design": manifest["design"],
    }


def verify_stimulus_set(root: str | Path) -> dict[str, Any]:
    """Re-hash every recorded image and re-check the design invariants."""
    root = Path(root)
    manifest = json.loads((root / "stimuli" / "manifest.json").read_text(encoding="utf-8"))
    check_design()
    problems: list[str] = []
    for record in manifest["files"]:
        path = root / record["path"]
        if not path.exists():
            problems.append(f"missing image {record['path']}")
            continue
        digest = _sha256(path)
        if digest != record["sha256"]:
            problems.append(f"hash mismatch for {record['path']}: {digest} != {record['sha256']}")
        if path.stat().st_size != record["bytes"]:
            problems.append(f"size mismatch for {record['path']}")
    if problems:
        raise AssertionError("stimulus set verification failed:\n  " + "\n  ".join(problems))
    return {"images": len(manifest["files"]), "version": manifest.get("version"), "verified": True}