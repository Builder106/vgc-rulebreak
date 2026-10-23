"""Tests for the trainable Protect policy and its cross-entropy training loop."""

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from vgc_rulebreak.agents.trained import (
    HEURISTIC_PARAMS,
    PARAM_BOUNDS,
    ProtectParams,
    TrainedProtectAgent,
    checkpoint_agent,
    load_checkpoint,
)
from vgc_rulebreak.cli import main
from vgc_rulebreak.manifest import load_manifest
from vgc_rulebreak.spec import validate_spec
from vgc_rulebreak.training import (
    TrainingConfig,
    run_cem,
    summarize_games,
    train_protect_policy,
    training_battle_seed,
)

SPEC_PATH = Path("experiments/protect-pp.json")
MANIFEST_PATH = Path("experiments/teams/protect-pp.json")


def params(**overrides: float) -> ProtectParams:
    values = {
        "base_score": 50.0,
        "low_hp_score": 95.0,
        "hp_threshold": 0.35,
        "scarcity_slope": 10.0,
        "pp_cushion": 4.0,
    }
    values.update(overrides)
    return ProtectParams(**values)


def test_protect_score_uses_hp_threshold_and_scarcity() -> None:
    p = params()
    assert p.score(pp=8, hp_ratio=0.9) == 50.0
    assert p.score(pp=8, hp_ratio=0.2) == 95.0
    assert p.score(pp=2, hp_ratio=0.9) == 30.0
    assert p.score(pp=0, hp_ratio=0.9) == 10.0
    assert params(scarcity_slope=40.0).score(pp=0, hp_ratio=0.9) == 0.0


def test_heuristic_params_match_the_baseline_protect_score() -> None:
    assert HEURISTIC_PARAMS.score(pp=16, hp_ratio=0.5) == 50.0
    assert HEURISTIC_PARAMS.score(pp=1, hp_ratio=0.3) == 95.0


def test_unit_round_trip_and_clipping() -> None:
    p = params()
    assert asdict(ProtectParams.from_unit(p.to_unit())) == pytest.approx(asdict(p))
    clipped = ProtectParams.from_unit([-1.0, 2.0, 0.5, 0.0, 1.0])
    assert clipped.base_score == PARAM_BOUNDS["base_score"][0]
    assert clipped.low_hp_score == PARAM_BOUNDS["low_hp_score"][1]


def test_trained_agent_skips_consecutive_protect() -> None:
    agent = TrainedProtectAgent(params())
    assert agent.score_protect({"pp": 8}, slot_idx=0, hp_ratio=0.9) == 50.0
    agent._used_protect_last_turn[0] = True
    assert agent.score_protect({"pp": 8}, slot_idx=0, hp_ratio=0.9) == 0.0


def test_training_seeds_are_shared_and_distinct() -> None:
    assert training_battle_seed(11, 0, 0, 0) == training_battle_seed(11, 0, 0, 0)
    seeds = {training_battle_seed(11, g, m, p) for g in range(3) for m in range(3) for p in (0, 1)}
    assert len(seeds) == 18
    assert training_battle_seed(29, 0, 0, 0) != training_battle_seed(11, 0, 0, 0)
    assert all(0 <= part < 65536 for seed in seeds for part in seed)


def test_mirrored_pair_shares_one_seed(tmp_path: Path) -> None:
    spec, manifest = load_study()
    config = TrainingConfig(
        agent="native", training_seed=11, generations=1, population=1, elites=1, workers=1
    )
    tasks: list[Any] = []

    def capture(task: Any) -> dict[str, float]:
        tasks.append(task)
        return fake_game(task)

    with patch("vgc_rulebreak.training.play_training_game", side_effect=capture):
        train_protect_policy(spec, manifest, config, tmp_path)

    assert len(tasks) == 6
    for first, second in zip(tasks[::2], tasks[1::2], strict=True):
        assert first.seed == second.seed
        assert (first.candidate_role, second.candidate_role) == ("p1", "p2")
        assert (first.candidate_team, first.opponent_team) == (
            second.opponent_team,
            second.candidate_team,
        )


def test_summarize_games() -> None:
    games = [
        {
            "points": 1.0,
            "protect_uses": 2,
            "protect_opportunities": 8,
            "protect_depleted": 0,
            "turns": 9,
        },
        {
            "points": 0.0,
            "protect_uses": 4,
            "protect_opportunities": 8,
            "protect_depleted": 1,
            "turns": 11,
        },
    ]
    stats = summarize_games(games)
    assert stats["fitness"] == 0.5
    assert stats["protect_use_rate"] == 6 / 16
    assert stats["depletion_rate"] == 0.5
    assert stats["avg_turns"] == 10.0


def test_run_cem_moves_toward_better_parameters() -> None:
    target = [0.8, 0.2, 0.5, 0.7, 0.3]
    seen_generations: list[int] = []

    def fitness(candidates: list[ProtectParams], generation: int) -> list[dict[str, float]]:
        seen_generations.append(generation)
        return [
            {"fitness": -sum((u - t) ** 2 for u, t in zip(c.to_unit(), target, strict=True))}
            for c in candidates
        ]

    checkpoints: list[tuple[int, list[float], dict[str, Any]]] = []
    config = TrainingConfig(
        agent="native", training_seed=11, generations=15, population=16, elites=4
    )
    final = run_cem(
        config,
        fitness,
        [0.5] * 5,
        0.25,
        lambda g, mean, std, stats: checkpoints.append((g, list(mean), stats)),
    )

    assert seen_generations == list(range(15))
    assert [g for g, _, _ in checkpoints] == list(range(16))
    assert checkpoints[0][1] == [0.5] * 5
    assert checkpoints[-1][2] == {}
    start = sum((0.5 - t) ** 2 for t in target)
    assert sum((u - t) ** 2 for u, t in zip(final, target, strict=True)) < start / 10
    assert checkpoints[5][2]["mean_stats"]["fitness"] > checkpoints[0][2]["mean_stats"]["fitness"]


def test_run_cem_rejects_bad_elite_count() -> None:
    config = TrainingConfig(agent="native", training_seed=11, population=4, elites=5)
    with pytest.raises(ValueError, match="elites"):
        run_cem(config, lambda c, g: [], [0.5] * 5, 0.25, lambda *a: None)


def fake_game(task: Any) -> dict[str, float]:
    won = task.params["base_score"] < 60
    return {
        "points": 1.0 if won else 0.0,
        "protect_uses": 1.0,
        "protect_opportunities": 4.0,
        "protect_depleted": 0.0,
        "turns": 10.0,
    }


def load_study() -> tuple[Any, Any]:
    spec = validate_spec(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    return spec, load_manifest(MANIFEST_PATH)


def test_train_writes_checkpoints_and_adapts_from_source(tmp_path: Path) -> None:
    spec, manifest = load_study()
    config = TrainingConfig(
        agent="source", training_seed=11, generations=2, population=4, workers=1
    )
    with patch("vgc_rulebreak.training.play_training_game", side_effect=fake_game):
        paths = train_protect_policy(spec, manifest, config, tmp_path)

    assert [p.name for p in paths] == [
        "source-s11-g00.json",
        "source-s11-g01.json",
        "source-s11-g02.json",
    ]
    first = json.loads(paths[0].read_text(encoding="utf-8"))
    assert first["ruleset"] == "protect-16"
    assert first["format_id"] == "gen9rulebreakprotect16"
    assert first["params"] == pytest.approx(asdict(HEURISTIC_PARAMS))
    assert first["training"]["games_per_candidate"] == 6  # 3 training pairings, mirrored
    assert first["training"]["mean_stats"]["protect_use_rate"] == 0.25
    assert first["training_teams"] == list(manifest.splits["training"])
    assert not json.loads(paths[-1].read_text(encoding="utf-8"))["training"]["evaluated"]

    adapted = TrainingConfig(
        agent="adapted", training_seed=11, generations=1, population=4, workers=1
    )
    with patch("vgc_rulebreak.training.play_training_game", side_effect=fake_game):
        adapted_paths = train_protect_policy(
            spec, manifest, adapted, tmp_path, init_checkpoint=paths[-1]
        )
    start, meta = load_checkpoint(adapted_paths[0])
    assert asdict(start) == pytest.approx(asdict(load_checkpoint(paths[-1])[0]))

    legacy = json.loads(paths[-1].read_text(encoding="utf-8"))
    legacy["format_id"] = "gen9doublescustomgame"
    legacy_path = tmp_path / "legacy-source.json"
    legacy_path.write_text(json.dumps(legacy), encoding="utf-8")
    with pytest.raises(ValueError, match="Protect-only 16 PP format"):
        train_protect_policy(spec, manifest, adapted, tmp_path, init_checkpoint=legacy_path)
    assert meta["ruleset"] == "protect-8"
    assert meta["init_checkpoint"] == {"agent": "source", "training_seed": 11, "generation": 2}
    assert checkpoint_agent(adapted_paths[0]).name == "adapted-s11-g00"


@pytest.mark.parametrize(
    ("config", "init", "message"),
    [
        (TrainingConfig(agent="native", training_seed=12), None, "training seed"),
        (TrainingConfig(agent="adapted", training_seed=11), None, "needs --init"),
        (TrainingConfig(agent="champion", training_seed=11), None, "agent must be"),
    ],
)
def test_train_rejects_bad_setups(
    tmp_path: Path, config: TrainingConfig, init: Path | None, message: str
) -> None:
    spec, manifest = load_study()
    with pytest.raises(ValueError, match=message):
        train_protect_policy(spec, manifest, config, tmp_path, init_checkpoint=init)


def test_cli_train_reports_setup_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["train", "--agent", "adapted", "--seed", "11", "--output-dir", str(tmp_path)])
    assert code == 2
    assert "needs --init" in capsys.readouterr().err


def test_cli_evaluate_loads_checkpoint(tmp_path: Path) -> None:
    spec, manifest = load_study()
    config = TrainingConfig(
        agent="native", training_seed=29, generations=1, population=2, elites=1, workers=1
    )
    with patch("vgc_rulebreak.training.play_training_game", side_effect=fake_game):
        paths = train_protect_policy(spec, manifest, config, tmp_path)

    with patch("vgc_rulebreak.evaluation.run_evaluation_suite") as suite:
        suite.side_effect = RuntimeError("stop after loading")
        code = main(["evaluate", "--checkpoint", str(paths[-1])])

    assert code == 2
    candidate = suite.call_args.kwargs["candidate"]
    assert isinstance(candidate, TrainedProtectAgent)
    assert candidate.name == "native-s29-g01"
