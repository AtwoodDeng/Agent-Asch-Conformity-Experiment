"""Local stand-in for the SocioVerse runtime, so the CLI can be exercised offline.

The real ``socioverse`` package is not installed on this interpreter (it lives
in the WSL checkout the platform runs). ``scripts/run_asch.py --local-stub``
installs this module *before* importing ``asch``, which lets the same CLI code
path run end to end here: the same condition tables, the same environment, the
same decision model, the same metrics, the same exports.

What is stubbed is only the platform's plumbing -- the ABC base classes, the
registration decorator and the schema containers. Every decision, routing rule,
prompt, stimulus and aggregate exercised under the stub is the real
implementation in ``asch/``.

Nothing produced under the stub is a SocioVerse2 result. It validates that the
study wiring is correct; ``实验规划.md`` §6 requires that this distinction be
stated wherever such a run is reported.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class _Schema:
    """Permissive pydantic-lite stand-in: keeps kwargs, tolerates attribute access."""

    def __init__(self, **kwargs: object) -> None:
        for key, value in kwargs.items():
            setattr(self, key, value)

    def model_copy(self, *, update: dict | None = None, deep: bool = False):  # noqa: ARG002
        clone = type(self)(**{k: v for k, v in vars(self).items()})
        for key, value in (update or {}).items():
            setattr(clone, key, value)
        return clone

    def model_dump(self, **kwargs: object) -> dict:
        return dict(vars(self))

    def __repr__(self) -> str:
        return f"{type(self).__name__}({vars(self)!r})"


REGISTRY: dict[tuple[str, str], type] = {}


def _register(kind: str, key: str):
    def deco(cls: type) -> type:
        REGISTRY[(kind, key)] = cls
        return cls

    return deco


class _ProviderBase:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass


def install() -> dict[tuple[str, str], type]:
    """Install the stub modules. Must run before ``import asch`` runtime modules."""
    if "socioverse" in sys.modules:
        return REGISTRY

    for name in ("socioverse", "socioverse.abc", "socioverse.engine", "socioverse.schemas"):
        sys.modules[name] = types.ModuleType(name)

    for name in ("DecisionModel", "EnvironmentProvider", "MetricCollector", "PopulationProvider"):
        setattr(sys.modules["socioverse.abc"], name, _ProviderBase)

    engine = sys.modules["socioverse.engine"]
    engine.register = _register

    schemas = sys.modules["socioverse.schemas"]
    for name in (
        "Action",
        "Broadcast",
        "EnvironmentBundle",
        "EnvironmentLayer",
        "InformationProgram",
        "InteractionStructure",
        "Observation",
        "Persona",
        "PopulationBundle",
        "PropagationMode",
        "ScheduledEvent",
        "SimulationConfig",
        "StudySpec",
    ):
        setattr(schemas, name, type(name, (_Schema,), {}))

    return REGISTRY