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
    def __init__(self, *, n_agents: int = 7, **_unused: Any) -> None:
        if n_agents != len(CONFEDERATE_SEATS) + 1:
            raise ValueError(
                f"n_agents={n_agents}: the design fixes {len(CONFEDERATE_SEATS)} confederates + 1 subject"
            )
        self.n_agents = n_agents

    def build(self, seed: int = 0) -> list[Any]:
        Persona = _persona_cls()
        personas = []
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