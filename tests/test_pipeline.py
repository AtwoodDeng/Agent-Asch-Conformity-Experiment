"""Testing the wiring that could silently invalidate every number.

The three risks worth automating are: the answer key reaching the decision
model, the subject seeing peer answers it should not (or not seeing the ones it
should), and the C4 distractors landing outside the gaps between trials.
"""

import json

import pytest

from asch.conditions import build_sessions, confederate_speeches
from asch.distractors import GAP_COUNT, STREAMS, stream_pieces
from asch.metrics import classify
from asch.model import KEY_FIELDS, check_no_key_leak
from asch.prompts import (
    build_prompt,
    parse_answer,
    render_trial,
)
from asch.stimuli import build_trials


# --------------------------------------------------------------------------
# The answer key must never be visible to the decision model.
# --------------------------------------------------------------------------


def _environment(condition="C1"):
    from asch.env import AschEnvironment

    session = build_sessions(condition)[0]
    return AschEnvironment(session=session, stimulus_root=".", agent_id="P07")


def test_observation_carries_no_answer_key():
    env = _environment("C1")
    env.reset()
    for observation in env.observe_batch(["P07"], t=3):
        check_no_key_leak(observation)


def test_observation_leaks_nothing_on_any_trial_of_any_condition():
    for condition in ("C0", "C1", "C2", "C3", "C4"):
        env = _environment(condition)
        env.reset()
        for t in range(1, 19):
            for observation in env.observe_batch(["P07"], t=t):
                blob = json.dumps(
                    {
                        "local": observation.local_physical,
                        "macro_info": observation.macro_information,
                    },
                    ensure_ascii=False,
                    default=str,
                )
                for field in KEY_FIELDS:
                    assert field not in observation.local_physical
                # the correct/error slot may appear only as a bare line length
                assert "correct_answer" not in blob


def test_observation_exposes_the_prompt_and_image_path_but_not_the_future():
    env = _environment("C1")
    env.reset()
    observation = env.observe_batch(["P07"], t=3)[0]
    local = observation.local_physical
    assert local["trial_index"] == 3
    assert local["image_path"].endswith(".png")
    assert "现在轮到你" in local["prompt"]
    # current trial's six peer answers, in seat order
    assert [s["seat"] for s in local["speeches"]] == [1, 2, 3, 4, 5, 6]


def test_c0_observation_has_no_peer_record():
    env = _environment("C0")
    env.reset()
    observation = env.observe_batch(["P07"], t=3)[0]
    assert observation.local_physical["speeches"] == []
    assert observation.local_physical["shows_peer_answers"] is False
    assert "此前参与者的回答" not in observation.local_physical["prompt"]


def test_scripted_policy_never_reads_the_key():
    """A blind policy must not track the designated error: that would prove leakage."""
    from asch.model import AschDecisionModel

    model = AschDecisionModel(llm_kind="scripted", policy="first")
    env = _environment("C1")
    env.reset()
    agree = 0
    total = 0
    for t in range(1, 19):
        observation = env.observe_batch(["P07"], t=t)[0]
        action = model.decide_batch([observation])[0]
        payload = observation.local_physical
        assert payload["trial_index"] == t
        rows_trial = build_trials(observation.local_physical["arrangement"])[t - 1]
        if rows_trial.is_critical:
            total += 1
            if action.payload["answer"] == rows_trial.error:
                agree += 1
        env.apply([action])
    # "first" always answers A; agreement with the designated error is whatever
    # the design's slot balance makes it, nowhere near a certainty.
    assert total == 12
    assert agree <= 6


def test_llm_provider_registry_resolves_env_like_the_tajfel_client(monkeypatch):
    """The provider registry is the single source of --llm choices (tajfel-style)."""
    from asch.model import (
        LLM_KINDS,
        LLM_PROVIDERS,
        SCRIPTED_KIND,
        _provider_env,
        is_llm_kind,
    )

    assert set(LLM_PROVIDERS) == {"openai"}
    assert LLM_KINDS == (SCRIPTED_KIND, *LLM_PROVIDERS)
    assert is_llm_kind("openai") is True
    assert is_llm_kind(SCRIPTED_KIND) is False

    monkeypatch.delenv("SV_LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("SV_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("SV_LLM_MODEL", raising=False)
    assert _provider_env("openai") == ("", "https://api.openai.com/v1", "gpt-4o")

    monkeypatch.setenv("SV_LLM_API_KEY", "k1")
    monkeypatch.setenv("OPENAI_API_KEY", "k2")
    monkeypatch.setenv("SV_LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("SV_LLM_MODEL", "gpt-4o-mini")
    assert _provider_env("openai") == ("k1", "https://example.test/v1", "gpt-4o-mini")

    # SV_LLM_* wins over the OPENAI_API_KEY fallback alias.
    monkeypatch.delenv("SV_LLM_API_KEY")
    assert _provider_env("openai")[0] == "k2"


def test_decision_model_rejects_unknown_llm_kind_and_builds_openai_lazily(monkeypatch):
    from asch.model import AschDecisionModel

    with pytest.raises(ValueError, match="unknown llm_kind"):
        AschDecisionModel(llm_kind="bogus")

    # A local .env may override the provider defaults; clear it so this test is
    # deterministic regardless of the developer's machine.
    monkeypatch.delenv("SV_LLM_MODEL", raising=False)
    monkeypatch.delenv("SV_LLM_API_KEY", raising=False)
    monkeypatch.delenv("SV_LLM_BASE_URL", raising=False)

    # Constructing the openai client must not import the openai SDK or read a
    # key; both happen lazily on the first completed request.
    model = AschDecisionModel(llm_kind="openai")
    assert model.llm is not None
    assert model.llm.provider == "openai"
    assert model.model_name == "gpt-4o"


# --------------------------------------------------------------------------
# Peer visibility must match the condition, exactly.
# --------------------------------------------------------------------------


def _pairs(speeches):
    """``render_trial`` takes (seat, answer) pairs, not Speech objects."""
    return [(speech.seat, speech.answer) for speech in speeches]


def test_peer_answers_present_iff_the_condition_shows_them():
    for condition in ("C0", "C1", "C2", "C3", "C4"):
        session = build_sessions(condition)[0]
        shows = session.condition_meta.shows_peer_answers
        for trial in session.trials:
            text = render_trial(trial.index, _pairs(confederate_speeches(session, trial)), show_peers=shows)
            if shows:
                assert "此前参与者的回答" in text
                assert text.count("参与者 ") == 6
            else:
                assert "此前参与者的回答" not in text
                assert "参与者 " not in text
            assert f"第 {trial.index} 题" in text


def test_renderer_rejects_inconsistent_peer_arguments():
    with pytest.raises(ValueError):
        render_trial(1, [], show_peers=True)
    session = build_sessions("C1")[0]
    with pytest.raises(ValueError):
        render_trial(1, _pairs(confederate_speeches(session, session.trials[0])), show_peers=False)


def test_no_condition_labels_reach_the_subject():
    """§3.2 L47: the subject must never see which arm it is in."""
    forbidden = ("C0", "C1", "C2", "C3", "C4", "同盟", "从众", "正确", "错误", "实验组", "控制组")
    for condition in ("C0", "C1", "C2", "C3", "C4"):
        session = build_sessions(condition)[0]
        history = []
        for trial in session.trials:
            prompt = build_prompt(
                condition=condition,
                index=trial.index,
                n_trials=len(session.trials),
                speeches=_pairs(confederate_speeches(session, trial)),
                history=tuple(history),
            )
            for token in forbidden:
                assert token not in prompt, f"{condition} trial {trial.index} leaked {token!r}"
            history.append(("trial", prompt))


# --------------------------------------------------------------------------
# The C4 distractors must sit strictly between adjacent trials.
# --------------------------------------------------------------------------


def test_c4_inserts_exactly_seventeen_fragments_between_eighteen_trials():
    env = _environment("C4")
    env.reset()
    for t in range(1, 19):
        for observation in env.observe_batch(["P07"], t=t):
            from asch.model import AschDecisionModel

            action = AschDecisionModel(llm_kind="scripted", policy="last").decide_batch([observation])[0]
            env.apply([action])
    assert env.gaps_shown == GAP_COUNT == 17
    kinds = [kind for kind, _ in env.history]
    assert kinds.count("trial") == 18
    assert kinds.count("gap") == GAP_COUNT
    # the run must start with a trial and end with a trial: no trailing fragment
    assert kinds[0] == "trial"
    assert kinds[-1] == "trial"
    # every gap follows a trial, i.e. no two gaps are adjacent
    for i in range(1, len(kinds)):
        if kinds[i] == "gap":
            assert kinds[i - 1] == "trial"


def test_c1_has_no_gaps():
    env = _environment("C1")
    env.reset()
    from asch.model import AschDecisionModel

    model = AschDecisionModel(llm_kind="scripted", policy="last")
    for t in range(1, 19):
        env.apply(model.decide_batch(env.observe_batch(["P07"], t=t)))
    assert env.gaps_shown == 0
    assert [kind for kind, _ in env.history] == ["trial"] * 18


def test_c4_and_c1_receive_identical_trial_material():
    """The contrast is only interpretable if the trials themselves are matched."""
    for index in range(12):
        c1 = build_sessions("C1")[index]
        c4 = build_sessions("C4")[index]
        assert [t.trial_id for t in c1.trials] == [t.trial_id for t in c4.trials]
        assert c1.arrangement == c4.arrangement


def test_three_streams_are_distinct_and_complete():
    assert set(STREAMS) == {"S1", "S2", "S3"}
    texts = set()
    for stream_id in STREAMS:
        pieces = stream_pieces(stream_id)
        assert len(pieces) == GAP_COUNT == 17
        for piece in pieces:
            assert 60 <= piece["chars"] <= 100
            assert 3 <= piece["sentences"] <= 5
            texts.add(piece["text"])
    assert len(texts) == 51, "the three streams must not share any fragment"


# --------------------------------------------------------------------------
# Parsing must be strict: a parsed answer is what the metrics count.
# --------------------------------------------------------------------------


def test_parser_accepts_clean_letters_and_rejects_ambiguity():
    assert parse_answer("B") == "B"
    assert parse_answer(" b ") == "B"
    assert parse_answer("答案是C。") == "C"
    assert parse_answer("我选 A，因为它更长") == "A"
    for bad in ("", "   ", "D", "AB", "A或B", "不知道", "1", "I think it is A? or maybe C"):
        assert parse_answer(bad) is None, bad


def test_unparsed_answers_are_counted_as_missing_not_as_correct():
    """§7 L181: a parse failure is missing data, never silently scored as correct."""
    row = {"correct_answer": "B", "designated_error": "A"}
    verdict = classify(row, None)
    assert verdict["parsed"] is False
    assert verdict["is_correct"] is False
    assert verdict["is_designated_error"] is False


def test_classify_three_way_against_the_key():
    row = {"correct_answer": "B", "designated_error": "A"}
    assert classify(row, "B") == {
        "parsed": True,
        "is_correct": True,
        "is_designated_error": False,
        "is_other": False,
    }
    assert classify(row, "A")["is_designated_error"] is True
    third = classify(row, "C")
    assert third["is_other"] is True
    assert third["is_correct"] is False and third["is_designated_error"] is False

# ---------------------------------------------------------------------------
# §9 C4 acceptance: exactly 17 gaps per session, strictly ordered, in between
# adjacent trials, and no past trial history truncated.
# ---------------------------------------------------------------------------


def _drive_session(condition: str, index: int = 0):
    """Run one whole session exactly the way the standalone driver does."""
    from asch.env import AschEnvironment
    from asch.model import AschDecisionModel

    session = build_sessions(condition)[index]
    env = AschEnvironment(session=session, stimulus_root=".", agent_id="P07")
    decision = AschDecisionModel(llm_kind="scripted", policy="random", seed=session.seed)
    for t in range(1, len(session.trials) + 1):
        observations = env.observe_batch(["P07"], t)
        actions = decision.decide_batch(observations, None)
        env.apply(actions)
    return session, env.record


def test_every_c4_session_receives_exactly_seventeen_ordered_pieces():
    """§9: "C4 额外验收每个会话恰有 17 个按序到达的片段"."""
    for index in (0, 5, 11):
        session, record = _drive_session("C4", index)
        assert len(record.gaps) == GAP_COUNT == 17
        keys = sorted(record.gaps)
        assert keys == list(range(1, 18)), "gaps must be keyed by the trial they follow"
        visible = [record.gaps[k]["visible_order"] for k in keys]
        assert visible == sorted(visible), "pieces must arrive in order"
        assert len(set(visible)) == 17, "no piece may be delivered twice"
        assert all(g["after_trial_id"] for g in record.gaps.values())


def test_c4_gaps_never_follow_the_last_trial():
    """A trailing fragment would append material after the task ended."""
    _, record = _drive_session("C4", 0)
    assert 18 not in record.gaps
    assert max(record.gaps) <= 17


def test_c4_does_not_truncate_the_trial_history():
    """§9 also requires that no earlier trial history is dropped."""
    session, record = _drive_session("C4", 0)
    assert len(record.trials) == len(session.trials) == 18
    # Every trial keeps its full public record: six speeches or, for C0, none.
    for index, entry in record.trials.items():
        assert "speeches" in entry, f"trial {index} lost its public record"
        assert len(entry["speeches"]) == 6
        assert "subject_answer" in entry


def test_non_c4_sessions_carry_no_gaps():
    for condition in ("C0", "C1", "C2", "C3"):
        _, record = _drive_session(condition, 0)
        assert record.gaps == {}, f"{condition} must not receive ambient text"


def test_the_environment_refuses_to_present_a_trial_out_of_range():
    """t=0 would silently wrap to the last trial through negative indexing."""
    from asch.env import AschEnvironment

    session = build_sessions("C1")[0]
    env = AschEnvironment(session=session, stimulus_root=".", agent_id="P07")
    env.reset()
    with pytest.raises((IndexError, ValueError)):
        # t=0 must not be served as the final trial, and must not be served at all.
        env.observe_batch(["P07"], 0)
    with pytest.raises((IndexError, ValueError)):
        # Past the end: presenting trial 18 as if it were trial 19 would repeat it.
        env.observe_batch(["P07"], len(session.trials) + 1)


def test_apply_also_refuses_a_step_outside_the_design():
    from asch.env import AschEnvironment

    session = build_sessions("C1")[0]
    env = AschEnvironment(session=session, stimulus_root=".", agent_id="P07")
    env.reset()
    with pytest.raises(IndexError):
        env.apply([])


def test_a_full_session_reaches_every_trial_exactly_once():
    session, record = _drive_session("C1", 0)
    assert sorted(record.trials) == list(range(1, 19))
    assert len(record.trials) == 18
