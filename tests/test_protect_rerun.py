"""Unit tests for the Protect-only training and evaluation rerun harness."""

import json
from pathlib import Path
from unittest.mock import patch

from vgc_rulebreak.agents.base import BattleAgent
from vgc_rulebreak.cli import main
from vgc_rulebreak.evaluation import EvaluationBattleResult
from vgc_rulebreak.manifest import load_manifest
from vgc_rulebreak.protect_rerun import (
    ProtectRerunConfig,
    run_protect_rerun,
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


def test_protect_rerun_config_defaults() -> None:
    cfg = ProtectRerunConfig()
    assert cfg.training_seed == 11
    assert cfg.eval_seed == 101
    assert cfg.generations == 3
    assert cfg.population == 6
    assert cfg.elites == 2
    assert cfg.pairs == 1
    assert cfg.eval_pairs == 1
    assert cfg.workers == 4
    assert not cfg.eval_all_checkpoints
    assert cfg.opponent_policy == "HeuristicBaseline"


def test_protect_rerun_execution_with_mocks(tmp_path: Path) -> None:
    spec = validate_spec(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    manifest = load_manifest(MANIFEST_PATH)

    cfg = ProtectRerunConfig(
        training_seed=11,
        eval_seed=101,
        generations=1,
        population=2,
        elites=1,
        pairs=1,
        eval_pairs=1,
        workers=1,
    )

    with (
        patch("vgc_rulebreak.training.play_training_game", side_effect=fake_training_game),
        patch("vgc_rulebreak.evaluation.run_evaluation_battle", side_effect=fake_eval_battle),
    ):
        report = run_protect_rerun(
            output_dir=tmp_path,
            config=cfg,
            spec=spec,
            manifest=manifest,
        )

    assert report.spec == "protect-pp"
    assert report.training_seed == 11
    assert report.eval_seed == 101
    assert report.formats == {
        "protect-16": "gen9rulebreakprotect16",
        "protect-8": "gen9rulebreakprotect8",
    }
    assert "source" in report.checkpoints
    assert "native" in report.checkpoints
    assert "adapted" in report.checkpoints

    # Checkpoints exist and have correct formats
    source_first = json.loads(Path(report.checkpoints["source"][0]).read_text(encoding="utf-8"))
    assert source_first["format_id"] == "gen9rulebreakprotect16"
    assert source_first["ruleset"] == "protect-16"

    native_first = json.loads(Path(report.checkpoints["native"][0]).read_text(encoding="utf-8"))
    assert native_first["format_id"] == "gen9rulebreakprotect8"
    assert native_first["ruleset"] == "protect-8"

    adapted_first = json.loads(Path(report.checkpoints["adapted"][0]).read_text(encoding="utf-8"))
    assert adapted_first["format_id"] == "gen9rulebreakprotect8"
    assert adapted_first["ruleset"] == "protect-8"
    assert adapted_first["init_checkpoint"]["agent"] == "source"

    # Evaluated checkpoints
    assert len(report.evaluated_checkpoints) > 0
    assert report.total_evaluation_games > 0
    assert report.total_depletions == 0
    assert not report.scarcity_binds

    # Verify recovery.json and rerun_summary.json exist
    recovery_file = tmp_path / "recovery.json"
    assert recovery_file.is_file()
    recovery_data = json.loads(recovery_file.read_text(encoding="utf-8"))
    assert "series" in recovery_data

    summary_file = tmp_path / "rerun_summary.json"
    assert summary_file.is_file()
    summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
    assert summary_data["spec"] == "protect-pp"


def test_protect_rerun_cli_quick(tmp_path: Path) -> None:
    run_dir = tmp_path / "cli_run"
    args = [
        "protect-rerun",
        "--output-dir",
        str(run_dir),
        "--quick",
        "--workers",
        "1",
    ]

    with (
        patch("vgc_rulebreak.training.play_training_game", side_effect=fake_training_game),
        patch("vgc_rulebreak.evaluation.run_evaluation_battle", side_effect=fake_eval_battle),
    ):
        ret = main(args)

    assert ret == 0
    assert (run_dir / "rerun_summary.json").is_file()
    assert (run_dir / "recovery.json").is_file()
