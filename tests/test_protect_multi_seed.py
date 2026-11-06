"""Unit tests for multi-seed training, evaluation, and confidence interval reporting."""

import json
from pathlib import Path
from unittest.mock import patch

from vgc_rulebreak.agents.base import BattleAgent
from vgc_rulebreak.cli import main
from vgc_rulebreak.evaluation import EvaluationBattleResult
from vgc_rulebreak.manifest import load_manifest
from vgc_rulebreak.protect_multi_seed import (
    ProtectMultiSeedConfig,
    bootstrap_ci,
    calculate_ci,
    run_protect_multi_seed,
)
from vgc_rulebreak.spec import validate_spec
from vgc_rulebreak.training import GameTask

SPEC_PATH = Path("experiments/protect-pp.json")
MANIFEST_PATH = Path("experiments/teams/protect-pp.json")


def fake_training_game(task: GameTask) -> dict[str, float]:
    won = task.params["base_score"] < 60
    return {
        "points": 1.0 if won else 0.0,
        "protect_uses": 1.0,
        "protect_opportunities": 4.0,
        "protect_depleted": 0.0,
        "turns": 8.0,
    }


def fake_eval_battle(
    candidate_agent: BattleAgent,
    opponent_agent: BattleAgent,
    format_id: str,
    candidate_team: str,
    opponent_team: str,
    candidate_role: str = "p1",
    seed: tuple[int, int, int, int] | None = None,
    showdown_dir: Path | str | None = None,
    max_turns: int = 60,
) -> EvaluationBattleResult:
    return EvaluationBattleResult(
        winner=candidate_agent.name,
        turns=7,
        duration_seconds=0.1,
        candidate_decisions=5,
        opponent_decisions=5,
        candidate_protect_uses=1,
        opponent_protect_uses=1,
        protect_depleted=False,
        candidate_won=True,
        end_reason="win",
        replay={"log": ["|turn|1"], "decisions": []},
        candidate_protect_opportunities=4,
    )


def test_bootstrap_ci_basic() -> None:
    assert bootstrap_ci([]) == (0.0, 0.0)
    assert bootstrap_ci([0.5]) == (0.5, 0.5)
    assert bootstrap_ci([0.0, 0.0, 0.0]) == (0.0, 0.0)

    scores = [1.0, 1.0, 0.5, 0.0, 1.0, 1.0, 0.5, 0.5]
    ci_low, ci_high = bootstrap_ci(scores, n_resamples=500, seed=42)
    assert 0.0 <= ci_low <= ci_high <= 1.0
    assert ci_low >= 0.4
    assert ci_high <= 1.0


def test_calculate_ci() -> None:
    empty_ci = calculate_ci([])
    assert empty_ci.mean == 0.0
    assert empty_ci.n == 0

    scores = [0.8, 0.6, 0.7, 0.9, 0.75]
    ci = calculate_ci(scores, n_resamples=500, seed=42)
    assert ci.n == 5
    assert ci.min == 0.6
    assert ci.max == 0.9
    assert ci.ci_lower <= ci.mean <= ci.ci_upper
    assert ci.std > 0.0


def test_multi_seed_config_defaults() -> None:
    cfg = ProtectMultiSeedConfig()
    assert cfg.training_seeds == (11, 29, 47)
    assert cfg.eval_seed == 101
    assert cfg.generations == 3
    assert cfg.population == 6
    assert cfg.elites == 2
    assert cfg.pairs == 1
    assert cfg.eval_pairs == 1
    assert cfg.workers == 4
    assert not cfg.eval_all_checkpoints
    assert cfg.opponent_policy == "HeuristicBaseline"
    assert cfg.bootstrap_resamples == 1000
    assert cfg.alpha == 0.05
    assert cfg.bootstrap_seed == 42


def test_protect_multi_seed_execution_with_mocks(tmp_path: Path) -> None:
    spec = validate_spec(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    manifest = load_manifest(MANIFEST_PATH)

    cfg = ProtectMultiSeedConfig(
        training_seeds=(11, 29, 47),
        eval_seed=101,
        generations=1,
        population=2,
        elites=1,
        pairs=1,
        eval_pairs=1,
        workers=1,
        bootstrap_resamples=200,
    )

    with (
        patch("vgc_rulebreak.training.play_training_game", side_effect=fake_training_game),
        patch("vgc_rulebreak.evaluation.run_evaluation_battle", side_effect=fake_eval_battle),
    ):
        report = run_protect_multi_seed(
            output_dir=tmp_path,
            config=cfg,
            spec=spec,
            manifest=manifest,
        )

    assert report.spec == "protect-pp"
    assert report.training_seeds == (11, 29, 47)
    assert report.eval_seed == 101
    assert report.formats == {
        "protect-16": "gen9rulebreakprotect16",
        "protect-8": "gen9rulebreakprotect8",
    }

    # Verify all training seeds have replicate summaries
    assert set(report.replicates.keys()) == {"11", "29", "47"}
    for seed_str, rep in report.replicates.items():
        assert rep.seed == int(seed_str)
        assert "source" in rep.agents
        assert "native" in rep.agents
        assert "adapted" in rep.agents
        assert "protect-16" in rep.agents["source"]
        assert "protect-8" in rep.agents["source"]
        assert rep.agents["source"]["protect-16"].games > 0

    # Verify confidence intervals across replicates and pooled games
    for role in ("source", "native", "adapted"):
        for var in ("protect-16", "protect-8"):
            stats = report.agent_confidence_intervals[role][var]
            ppg_rep = stats["ppg_across_replicates"]
            assert ppg_rep.ci_lower <= ppg_rep.mean <= ppg_rep.ci_upper
            ppg_pool = stats["ppg_pooled_games"]
            assert ppg_pool.ci_lower <= ppg_pool.mean <= ppg_pool.ci_upper
            prot_rate = stats["protect_rate_pooled_games"]
            assert prot_rate.ci_lower <= prot_rate.mean <= prot_rate.ci_upper

    # Verify causal effect confidence intervals
    transfer_ci = report.effect_confidence_intervals["transfer_delta_ppg"]
    assert transfer_ci.ci_lower <= transfer_ci.mean <= transfer_ci.ci_upper
    assert "adaptation_recovery_ppg" in report.effect_confidence_intervals
    assert "native_vs_source_ppg" in report.effect_confidence_intervals

    # Verify depletion / scarcity findings
    assert report.total_depletions == 0
    assert not report.scarcity_binds_in_any_seed
    assert "null_result_confirmed_across_seeds" in report.findings["conclusion"]

    # Verify files created on disk
    assert (tmp_path / "multi_seed_report.json").is_file()
    assert (tmp_path / "recovery.json").is_file()

    # Verify recovery.json contains series with all 3 seeds
    recovery_data = json.loads((tmp_path / "recovery.json").read_text(encoding="utf-8"))
    assert "series" in recovery_data
    for s in recovery_data["series"]:
        for pt in s["points"]:
            # Checkpoints evaluated have seeds
            seed_keys = set(pt["seeds"].keys())
            assert seed_keys.issubset({"11", "29", "47"})


def test_protect_multi_seed_cli_quick(tmp_path: Path) -> None:
    run_dir = tmp_path / "cli_run"
    args = [
        "protect-multi-seed",
        "--output-dir",
        str(run_dir),
        "--training-seeds",
        "11",
        "29",
        "--quick",
        "--workers",
        "1",
        "--bootstrap-resamples",
        "100",
    ]

    with (
        patch("vgc_rulebreak.training.play_training_game", side_effect=fake_training_game),
        patch("vgc_rulebreak.evaluation.run_evaluation_battle", side_effect=fake_eval_battle),
    ):
        ret = main(args)

    assert ret == 0
    assert (run_dir / "multi_seed_report.json").is_file()
    assert (run_dir / "recovery.json").is_file()

    report_data = json.loads((run_dir / "multi_seed_report.json").read_text(encoding="utf-8"))
    assert report_data["training_seeds"] == [11, 29]
    assert "11" in report_data["replicates"]
    assert "29" in report_data["replicates"]
