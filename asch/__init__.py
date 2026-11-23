"""Asch (1956) line-length judgement, rebuilt as a SocioVerse2 study.

The package is split so that the *design* half has no platform dependency and
the *runtime* half does:

* design and content -- :mod:`asch.stimuli`, :mod:`asch.conditions`,
  :mod:`asch.prompts`, :mod:`asch.distractors`. These import only the standard
  library and Pillow. Everything here is frozen by hash and can be inspected,
  rendered and tested without the SDK.
* runtime -- :mod:`asch.env`, :mod:`asch.model`, :mod:`asch.metrics`,
  :mod:`asch.population`, :mod:`asch.bundles`. These import ``socioverse`` and
  register the four provider classes.

Call :func:`register_providers` once, after ``socioverse`` (or the local stub that
``scripts/commshim.py`` installs) is importable, to make all four refs
available to the engine.
"""

from __future__ import annotations

__version__ = "0.1.0"

from asch.conditions import (  # noqa: E402
    CONDITION_ORDER,
    CONDITIONS,
    CONFEDERATE_SEATS,
    SUBJECT_SEAT,
    Session,
    all_sessions,
    build_sessions,
    check_conditions,
    confederate_speeches,
    find_session,
)
from asch.distractors import STREAMS, check_streams, stream_pieces  # noqa: E402
from asch.prompts import (  # noqa: E402
    COMMON_INSTRUCTION,
    PUBLIC_ANSWERING_INSTRUCTION,
    SOLO_ANSWERING_INSTRUCTION,
    build_messages,
    build_prompt,
    check_prompts,
    parse_answer,
)
from asch.stimuli import (  # noqa: E402
    BASIC_COMPARISONS,
    TRIAL_COUNT,
    build_trials,
    check_design,
    render,
    verify_stimulus_set,
    write_stimulus_set,
)

__all__ = [
    "__version__",
    # design
    "BASIC_COMPARISONS",
    "TRIAL_COUNT",
    "CONDITION_ORDER",
    "CONDITIONS",
    "CONFEDERATE_SEATS",
    "SUBJECT_SEAT",
    "STREAMS",
    "Session",
    "all_sessions",
    "build_sessions",
    "build_trials",
    "check_conditions",
    "check_design",
    "check_prompts",
    "check_streams",
    "confederate_speeches",
    "find_session",
    "render",
    "stream_pieces",
    "verify_stimulus_set",
    "write_stimulus_set",
    # prompts
    "COMMON_INSTRUCTION",
    "PUBLIC_ANSWERING_INSTRUCTION",
    "SOLO_ANSWERING_INSTRUCTION",
    "build_messages",
    "build_prompt",
    "parse_answer",
    # runtime
    "register_providers",
    "PROVIDER_REFS",
]

PROVIDER_REFS = {
    "environment": "asch.env",
    "decision": "asch.decision",
    "collector": "asch.collector",
    "population": "asch.pop",
}


def register_providers() -> dict[str, str]:
    """Import the runtime modules so the four provider classes register.

    Importing is the registration: each module registers its class with the
    engine's registry at import time. Requires ``socioverse`` (or the stub from
    ``scripts/commshim.py``) to be importable.
    """
    from asch import bundles, env, metrics, model, population  # noqa: F401

    return dict(PROVIDER_REFS)