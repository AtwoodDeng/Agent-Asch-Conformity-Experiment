"""Decision model: the subject's answer, from a scripted rule or a real LLM.

Two double modes, mirroring the platform convention (``llm_kind`` is decided at
one registration point, never per call):

``scripted``
    Deterministic and free. Used for pipeline validation and for the wiring
    tests. It **cannot** see the stimulus content and it **never** sees the
    answer key: the observation deliberately carries only the prompt, the image
    path, the peer answers and the seat. So its accuracy is the accuracy of a
    blind agent, and its numbers may never be reported as conformity results
    (``实验规划.md`` §6: standalone-loop output is engineering validation).

``openai``
    One call per trial with the stimulus image attached. The reply is parsed
    with :func:`asch.prompts.parse_answer`; an unparseable reply is recorded as
    a missing answer with ``action_source="fallback"`` and counted, never
    filled in with the correct or the majority answer (§7, L181).

The observation never contains ``correct`` or ``error``. That is the single most
important property of this module: a model cannot accidentally read the key.
:func:`check_no_key_leak` asserts it, and a test calls it on a rendered
observation.
"""

from __future__ import annotations

import hashlib
import os
import random
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from asch.prompts import build_messages, parse_answer

LLM_KINDS = ("scripted", "openai")
SCRIPTED_POLICIES = ("random", "first", "last", "peer")

DEFAULT_SCRIPTED_POLICY = "random"

KEY_FIELDS = ("correct", "correct_answer", "error", "designated_error", "answer_key", "is_correct")


def _load_dotenv() -> None:
    try:
        from socioverse.external_events import _load_dotenv as platform_load

        platform_load()
        return
    except Exception:  # pragma: no cover - depends on the platform install
        pass
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        pass


_load_dotenv()


def _abc():
    from socioverse.abc import DecisionModel

    return DecisionModel


def _action_cls():
    from socioverse.schemas import Action

    return Action


def _register():
    from socioverse.engine import register

    return register


DECISION_REF = "asch.decision"


# --------------------------------------------------------------------------
# Leak guard.
# --------------------------------------------------------------------------


def check_no_key_leak(observation: Any) -> None:
    """Raise if a rendered observation carries the answer key."""
    payload = getattr(observation, "local_physical", observation)
    if not isinstance(payload, dict):
        payload = dict(payload or {})
    for field in KEY_FIELDS:
        if field in payload:
            raise AssertionError(f"observation for {getattr(observation, 'agent_id', '?')} leaks field {field!r}")
    macro = getattr(observation, "macro_information", None) or {}
    for field in KEY_FIELDS:
        if field in macro:
            raise AssertionError(f"macro_information leaks field {field!r}")


# --------------------------------------------------------------------------
# LLM client (mirrors the platform adapter used by the sibling Tajfel study).
# --------------------------------------------------------------------------


class _OpenAILLM:
    def __init__(
        self,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 24,
        timeout: float = 60.0,
    ) -> None:
        self.model = model or os.environ.get("SV_LLM_MODEL", "gpt-4o")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self._client: Any = None
        self._lock = threading.Lock()

    def _ensure(self) -> Any:
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is None:
                from openai import OpenAI

                api_key = os.environ.get("SV_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
                if not api_key:
                    raise RuntimeError(
                        "no API key: set SV_LLM_API_KEY or OPENAI_API_KEY, "
                        "or run with --llm scripted"
                    )
                kwargs: dict[str, Any] = {"api_key": api_key, "timeout": self.timeout}
                base_url = os.environ.get("SV_LLM_BASE_URL")
                if base_url:
                    kwargs["base_url"] = base_url
                self._client = OpenAI(**kwargs)
        return self._client

    def complete(self, messages: list[dict[str, Any]]) -> str:
        client = self._ensure()
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        return (response.choices[0].message.content or "").strip()


def _make_llm(kind: str, **kwargs: Any) -> _OpenAILLM | None:
    if kind == "scripted":
        return None
    if kind == "openai":
        return _OpenAILLM(**kwargs)
    raise ValueError(f"unknown llm_kind {kind!r}; expected one of {LLM_KINDS}")


# --------------------------------------------------------------------------
# Scripted policy.
# --------------------------------------------------------------------------


def derived_seed(*parts: Any) -> str:
    """A reproducible string seed from arbitrary parts.

    ``random.Random`` rejects tuples, and Python's ``hash`` is not stable across
    processes, so the seed is derived from a hash of the joined parts instead.
    """
    joined = "|".join("" if part is None else str(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16]


def scripted_answer(payload: dict[str, Any], policy: str, rng: random.Random) -> str:
    """A deterministic, answer-key-blind choice among the three slots.

    ``peer`` reproduces the majority answer when one exists, which is a
    deliberately mechanical way of proving that the routing and metric chain
    works end to end. It is a wiring check, not a behavioural finding, and the
    run record labels it as such.
    """
    slots = ("A", "B", "C")
    if policy == "first":
        return slots[0]
    if policy == "last":
        return slots[-1]
    if policy == "peer":
        votes = [s.get("answer") for s in payload.get("speeches") or []]
        votes = [v for v in votes if v in slots]
        if votes:
            counts: dict[str, int] = {}
            for vote in votes:
                counts[vote] = counts.get(vote, 0) + 1
            best = max(counts.values())
            leaders = [v for v, c in counts.items() if c == best]
            if len(leaders) == 1:
                return leaders[0]
        return rng.choice(slots)
    if policy == "random":
        return rng.choice(slots)
    raise ValueError(f"unknown scripted policy {policy!r}; expected one of {SCRIPTED_POLICIES}")


# --------------------------------------------------------------------------
# Decision model.
# --------------------------------------------------------------------------


@_register()("decision", DECISION_REF)
class AschDecisionModel(_abc()):  # type: ignore[misc]
    def __init__(
        self,
        *,
        llm_kind: str = "scripted",
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 24,
        max_workers: int = 4,
        policy: str = DEFAULT_SCRIPTED_POLICY,
        prompt_lang: str = "zh",
        seed: int = 0,
        timeout: float = 60.0,
    ) -> None:
        if llm_kind not in LLM_KINDS:
            raise ValueError(f"unknown llm_kind {llm_kind!r}")
        if policy not in SCRIPTED_POLICIES:
            raise ValueError(f"unknown scripted policy {policy!r}")
        if prompt_lang != "zh":
            # The frozen texts of §3.2 are Chinese; an English rendering would be
            # a different (unfrozen) instrument.
            raise ValueError(f"prompt_lang {prompt_lang!r} is not available; the frozen prompts are zh only")
        self.llm_kind = llm_kind
        self.policy = policy
        self.prompt_lang = prompt_lang
        self.max_workers = max_workers
        self.seed = seed
        self.llm = _make_llm(llm_kind, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
        self.model_name = self.llm.model if self.llm else "scripted"
        self.call_count = 0
        self.fallback_count = 0
        self.parse_failures: list[dict[str, Any]] = []
        self._counter_lock = threading.Lock()

    # -- one decision --------------------------------------------------

    def _decide_one(self, observation: Any) -> tuple[str | None, str, str | None]:
        payload = getattr(observation, "local_physical", None) or {}
        check_no_key_leak(observation)
        prompt = payload.get("prompt")
        if not prompt:
            raise ValueError(f"observation for {getattr(observation, 'agent_id', '?')} carries no prompt")

        if self.llm is None:
            rng = random.Random(derived_seed(self.seed, payload.get("session_id"), payload.get("trial_index")))
            return scripted_answer(payload, self.policy, rng), "rule", f"scripted policy={self.policy}"

        messages = build_messages(prompt=prompt, image_path=payload.get("image_path"))
        with self._counter_lock:
            self.call_count += 1
        try:
            reply = self.llm.complete(messages)
        except Exception as exc:  # a failed call is a missing answer, not a guess
            with self._counter_lock:
                self.fallback_count += 1
                self.parse_failures.append(
                    {"trial_index": payload.get("trial_index"), "reason": "api_error", "detail": str(exc)[:240]}
                )
            return None, "fallback", f"api_error: {exc}"[:240]

        answer = parse_answer(reply)
        if answer is None:
            with self._counter_lock:
                self.fallback_count += 1
                self.parse_failures.append(
                    {"trial_index": payload.get("trial_index"), "reason": "parse_failure", "detail": reply[:240]}
                )
            return None, "fallback", reply[:240]
        return answer, "llm", reply[:240]

    # -- batch API -----------------------------------------------------

    def decide_batch(self, observations: list[Any], memories: Any = None) -> list[Any]:
        Action = _action_cls()
        if not observations:
            return []
        if self.llm is None or len(observations) == 1:
            results = [self._decide_one(ob) for ob in observations]
        else:
            workers = min(self.max_workers, len(observations))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = list(pool.map(self._decide_one, observations))
        actions = []
        for observation, (answer, source, rationale) in zip(observations, results):
            payload = getattr(observation, "local_physical", None) or {}
            actions.append(
                Action(
                    agent_id=getattr(observation, "agent_id", "subject"),
                    step=getattr(observation, "step", None),
                    kind="answer",
                    payload={
                        "answer": answer,
                        "raw": rationale,
                        "source": source,
                        "trial_index": payload.get("trial_index"),
                        "trial_id": payload.get("trial_id"),
                    },
                    source=source,
                    rationale=rationale,
                )
            )
        return actions

    # -- accounting ----------------------------------------------------

    def counters(self) -> dict[str, Any]:
        attempted = self.call_count if self.llm is not None else 0
        return {
            "llm_kind": self.llm_kind,
            "model": self.model_name,
            "scripted_policy": self.policy if self.llm is None else None,
            "calls": self.call_count,
            "fallbacks": self.fallback_count,
            "fallback_rate": (self.fallback_count / attempted) if attempted else 0.0,
            "parse_failures": list(self.parse_failures),
        }