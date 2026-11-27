"""Population provider: the seven seats of one session.

The group is fixed by design (``实验规划.md`` §2, L17): six scripted
confederates and one LLM subject at seat 7. There is no sampling, no random
composition and no matching across conditions, so this provider is a
constructor, not a simulator of a population.

Personas carry a seat number and nothing else descriptive. In particular a
confederate persona has no attribute that would let a decision model or a
report call it an expert, a majority member or a confederate without going
through the design tables -- which is where the labels are allowed to appear.
"""

from __future__ import annotations

from typing import Any

from asch.conditions import CONFEDERATE_SEATS, SUBJECT_SEAT


def _abc():
    from socioverse.abc import PopulationProvider

    return PopulationProvider


def _persona_cls():
    from socioverse.schemas import Persona

    return Persona


def _register():
    from socioverse.engine import register

    return register


POP_REF = "asch.pop"
SUBJECT_ID = "P07"


def _confederate_id(seat: int) -> str:
    return f"P{seat:02d}"


@_register()("population", POP_REF)
class AschPopulationProvider(_abc()):  # type: ignore[misc]
    def __init__(self, bundle: Any = None, *, n_agents: int = 1, **_unused: Any) -> None:
        # Engine convention: ``cls(bundle)``. The bundle's provider_args decide how
        # many REAL personas exist. The six confederate seats are scripted inside
        # the environment and never make a decision, so they are NOT engine
        # personas; ``n_agents=1`` materializes only the subject (P07). The
        # historical ``n_agents=7`` snapshot is kept for the standalone record.
        if bundle is not None:
            n_agents = int((getattr(bundle, "provider_args", None) or {}).get("n_agents", 1))
        if n_agents not in (1, len(CONFEDERATE_SEATS) + 1):
            raise ValueError(
                f"n_agents={n_agents}: expected 1 (engine: subject only) "
                f"or {len(CONFEDERATE_SEATS) + 1} (standalone snapshot incl. scripted seats)"
            )
        self.n_agents = n_agents

    def build(self, seed: int = 0) -> list[Any]:
        Persona = _persona_cls()
        personas = []
        if self.n_agents == len(CONFEDERATE_SEATS) + 1:
            for seat in CONFEDERATE_SEATS:
                personas.append(
                    Persona(
                        agent_id=_confederate_id(seat),
                        group_key="session",
                        attributes={"seat": seat, "responds_by_script": True},
                        init_state={"answers_given": 0},
                    )
                )
        personas.append(
            Persona(
                agent_id=SUBJECT_ID,
                group_key="session",
                attributes={"seat": SUBJECT_SEAT, "responds_by_script": False},
                init_state={"answers_given": 0},
            )
        )
        if len(personas) != self.n_agents:
            raise AssertionError(f"built {len(personas)} personas, expected {self.n_agents}")
        return personas


def subject_agent_id() -> str:
    return SUBJECT_ID


def confederate_agent_ids() -> list[str]:
    return [_confederate_id(seat) for seat in CONFEDERATE_SEATS]