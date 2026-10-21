"""Unit tests for study agent variants: Source, Native, and Adapted."""

import pytest

from vgc_rulebreak.agents.variants import AdaptedAgent, NativeAgent, SourceAgent
from vgc_rulebreak.evaluation import create_candidate_agent


def test_source_agent_protect_scoring() -> None:
    agent = SourceAgent("TestSource")
    move_info_16 = {"id": "protect", "pp": 16, "maxpp": 16}
    move_info_1 = {"id": "protect", "pp": 1, "maxpp": 8}

    # High HP: baseline stall score 55.0 regardless of remaining PP
    assert agent.score_protect(move_info_16, slot_idx=0, hp_ratio=1.0) == 55.0
    assert agent.score_protect(move_info_1, slot_idx=0, hp_ratio=1.0) == 55.0

    # Threatened (< 0.45): high preservation score 95.0 regardless of remaining PP
    assert agent.score_protect(move_info_16, slot_idx=0, hp_ratio=0.40) == 95.0
    assert agent.score_protect(move_info_1, slot_idx=0, hp_ratio=0.40) == 95.0

    # Consecutive protect penalty -> 0.0
    agent._used_protect_last_turn[0] = True
    assert agent.score_protect(move_info_16, slot_idx=0, hp_ratio=0.20) == 0.0


def test_native_agent_protect_scoring() -> None:
    agent = NativeAgent("TestNative")

    # High PP (8 PP): standard defensive score
    info_8 = {"id": "protect", "pp": 8, "maxpp": 8}
    assert agent.score_protect(info_8, slot_idx=0, hp_ratio=0.30) == 90.0
    assert agent.score_protect(info_8, slot_idx=0, hp_ratio=0.80) == 45.0

    # Medium PP (4 PP): moderate conservation
    info_4 = {"id": "protect", "pp": 4, "maxpp": 8}
    assert agent.score_protect(info_4, slot_idx=0, hp_ratio=0.30) == 85.0
    assert agent.score_protect(info_4, slot_idx=0, hp_ratio=0.80) == 35.0

    # Low PP (2 PP): strict conservation
    info_2 = {"id": "protect", "pp": 2, "maxpp": 8}
    assert agent.score_protect(info_2, slot_idx=0, hp_ratio=0.25) == 90.0
    assert agent.score_protect(info_2, slot_idx=0, hp_ratio=0.80) == 25.0

    # Critical PP (1 PP): reserved strictly for imminent lethal threat
    info_1 = {"id": "protect", "pp": 1, "maxpp": 8}
    assert agent.score_protect(info_1, slot_idx=0, hp_ratio=0.15) == 110.0
    assert agent.score_protect(info_1, slot_idx=0, hp_ratio=0.80) == 10.0

    # Consecutive protect penalty -> 0.0
    agent._used_protect_last_turn[0] = True
    assert agent.score_protect(info_8, slot_idx=0, hp_ratio=0.10) == 0.0


def test_adapted_agent_interpolation() -> None:
    source = SourceAgent("Source")
    native = NativeAgent("Native")

    # Progress = 0.0 should exactly match SourceAgent
    adapted_0 = AdaptedAgent("Adapted0", adaptation_progress=0.0)
    # Progress = 1.0 should exactly match NativeAgent
    adapted_1 = AdaptedAgent("Adapted1", adaptation_progress=1.0)
    # Progress = 0.5 should be exact arithmetic midpoint
    adapted_mid = AdaptedAgent("AdaptedMid", adaptation_progress=0.5)

    info_1 = {"id": "protect", "pp": 1, "maxpp": 8}
    hp = 0.80

    s_score = source.score_protect(info_1, slot_idx=0, hp_ratio=hp)
    n_score = native.score_protect(info_1, slot_idx=0, hp_ratio=hp)
    a0_score = adapted_0.score_protect(info_1, slot_idx=0, hp_ratio=hp)
    a1_score = adapted_1.score_protect(info_1, slot_idx=0, hp_ratio=hp)
    amid_score = adapted_mid.score_protect(info_1, slot_idx=0, hp_ratio=hp)

    assert a0_score == pytest.approx(s_score)
    assert a1_score == pytest.approx(n_score)
    assert amid_score == pytest.approx((s_score + n_score) / 2.0)


def test_adapted_agent_invalid_progress() -> None:
    with pytest.raises(ValueError, match=r"adaptation_progress must be between 0\.0 and 1\.0"):
        AdaptedAgent("InvalidNeg", adaptation_progress=-0.1)

    with pytest.raises(ValueError, match=r"adaptation_progress must be between 0\.0 and 1\.0"):
        AdaptedAgent("InvalidHigh", adaptation_progress=1.5)


def test_create_candidate_agent_variants() -> None:
    src = create_candidate_agent("source")
    assert isinstance(src, SourceAgent)

    nat = create_candidate_agent("native")
    assert isinstance(nat, NativeAgent)

    adp = create_candidate_agent("adapted")
    assert isinstance(adp, AdaptedAgent)
