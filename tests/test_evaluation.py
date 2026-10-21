"""Unit and integration tests for frozen evaluation harness."""

import json
from pathlib import Path

import pytest

from vgc_rulebreak.agents.heuristic import HeuristicAgent
from vgc_rulebreak.agents.random import RandomAgent
from vgc_rulebreak.cli import main
from vgc_rulebreak.evaluation import (
    build_test_matchups,
    create_candidate_agent,
    create_opponent_agent,
    get_evaluation_plan,
    make_eval_battle_seed,
    verify_frozen_evaluation,
)
from vgc_rulebreak.manifest import load_manifest
from vgc_rulebreak.spec import EvaluationSpec, ExperimentSpec, validate_spec

SPEC_PATH = Path("experiments/protect-pp.json")
MANIFEST_PATH = Path("experiments/teams/protect-pp.json")


def test_verify_frozen_evaluation_valid() -> None:
    spec = validate_spec(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    manifest = load_manifest(MANIFEST_PATH)
    verify_frozen_evaluation(spec, manifest)


def test_verify_frozen_evaluation_missing_eval() -> None:
    spec = ExperimentSpec(
        name="test",
        simulator_revision="9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e",
        information_mode="open",
        training_seeds=(11, 29, 47),
        variants={"protect-16": 16, "protect-8": 8},
        pending_gates=(),
        evaluation=None,
    )
    manifest = load_manifest(MANIFEST_PATH)
    with pytest.raises(ValueError, match="missing evaluation configuration"):
        verify_frozen_evaluation(spec, manifest)


def test_verify_frozen_evaluation_rejects_training_contamination() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    spec = ExperimentSpec(
        name="test",
        simulator_revision="9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e",
        information_mode="open",
        training_seeds=(11, 29, 47),
        variants={"protect-16": 16, "protect-8": 8},
        pending_gates=(),
        evaluation=EvaluationSpec(
            test_teams=("train-tailwind-offense", "test-balance-pivot"),
            opponent_policies=("HeuristicBaseline", "RandomBaseline"),
            evaluation_seeds=(101, 202, 303),
        ),
    )
    with pytest.raises(ValueError, match=r"expected 'test'|training split"):
        verify_frozen_evaluation(spec, manifest)


def test_verify_frozen_evaluation_rejects_validation_contamination() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    spec = ExperimentSpec(
        name="test",
        simulator_revision="9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e",
        information_mode="open",
        training_seeds=(11, 29, 47),
        variants={"protect-16": 16, "protect-8": 8},
        pending_gates=(),
        evaluation=EvaluationSpec(
            test_teams=("val-trickroom-bulky", "test-balance-pivot"),
            opponent_policies=("HeuristicBaseline", "RandomBaseline"),
            evaluation_seeds=(101, 202, 303),
        ),
    )
    with pytest.raises(ValueError, match=r"expected 'test'|validation split"):
        verify_frozen_evaluation(spec, manifest)


def test_verify_frozen_evaluation_rejects_missing_team() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    spec = ExperimentSpec(
        name="test",
        simulator_revision="9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e",
        information_mode="open",
        training_seeds=(11, 29, 47),
        variants={"protect-16": 16, "protect-8": 8},
        pending_gates=(),
        evaluation=EvaluationSpec(
            test_teams=("nonexistent-team", "test-balance-pivot"),
            opponent_policies=("HeuristicBaseline", "RandomBaseline"),
            evaluation_seeds=(101, 202, 303),
        ),
    )
    with pytest.raises(ValueError, match="not found in team manifest"):
        verify_frozen_evaluation(spec, manifest)


def test_build_test_matchups() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    teams = ("test-annihilape-bulky", "test-balance-pivot")
    matchups = build_test_matchups(manifest, teams)
    # 2 teams: (A, A), (A, B), (B, B) -> 3 matchups
    assert len(matchups) == 3
    pair_ids = [(m[0], m[2]) for m in matchups]
    assert ("test-annihilape-bulky", "test-annihilape-bulky") in pair_ids
    assert ("test-annihilape-bulky", "test-balance-pivot") in pair_ids
    assert ("test-balance-pivot", "test-balance-pivot") in pair_ids


def test_make_eval_battle_seed() -> None:
    seed1 = make_eval_battle_seed(101, 0, 0, 0, 0, 0)
    seed2 = make_eval_battle_seed(101, 0, 0, 0, 0, 1)
    seed3 = make_eval_battle_seed(202, 0, 0, 0, 0, 0)

    assert isinstance(seed1, tuple) and len(seed1) == 4
    for val in seed1:
        assert 0 <= val <= 0xFFFF

    assert seed1 != seed2
    assert seed1 != seed3


def test_create_opponent_agent() -> None:
    h = create_opponent_agent("HeuristicBaseline")
    assert isinstance(h, HeuristicAgent)
    assert h.name == "HeuristicBaseline"

    r = create_opponent_agent("RandomBaseline", seed=42)
    assert isinstance(r, RandomAgent)
    assert r.name == "RandomBaseline"

    with pytest.raises(ValueError, match="Unrecognized opponent policy"):
        create_opponent_agent("UnknownAgent")


def test_create_candidate_agent() -> None:
    h = create_candidate_agent("heuristic")
    assert isinstance(h, HeuristicAgent)

    r = create_candidate_agent("random", seed=42)
    assert isinstance(r, RandomAgent)

    existing = HeuristicAgent("Custom")
    assert create_candidate_agent(existing) is existing

    with pytest.raises(ValueError, match="Unknown candidate agent type"):
        create_candidate_agent("unknown")


def test_get_evaluation_plan() -> None:
    spec = validate_spec(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    manifest = load_manifest(MANIFEST_PATH)
    plan = get_evaluation_plan(spec, manifest, pairs_override=5)

    assert plan["status"] == "frozen"
    assert plan["test_teams"] == ["test-annihilape-bulky", "test-balance-pivot"]
    assert plan["opponent_policies"] == ["HeuristicBaseline", "RandomBaseline"]
    assert plan["evaluation_seeds"] == [101, 202, 303]
    assert plan["pairs_per_matchup"] == 5
    # 2 variants * 2 opponents * 3 matchups * 2 mirrored * 5 pairs = 120 per seed
    assert plan["battles_per_seed"] == 120
    # 120 * 3 seeds = 360 total battles
    assert plan["total_evaluation_battles"] == 360
    assert isinstance(plan["estimated_duration_seconds"], float)


def test_cli_evaluate_check_only(capsys: pytest.CaptureFixture[str]) -> None:
    ret = main(["evaluate", "--check-only"])
    assert ret == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["status"] == "frozen"
    assert "test-annihilape-bulky" in data["test_teams"]
    assert "HeuristicBaseline" in data["opponent_policies"]
