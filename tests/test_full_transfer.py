"""Paired full-ruleset transfer estimates and training/evaluation isolation."""

import copy
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest

from vgc_rulebreak import full_transfer as ft
from vgc_rulebreak.agents.base import BattleAgent
from vgc_rulebreak.cli import main
from vgc_rulebreak.evaluation import EvaluationBattleResult
from vgc_rulebreak.manifest import load_manifest
from vgc_rulebreak.recovery import summarize_recovery


def rows() -> list[dict[str, Any]]:
    return [
        {
            "training_seed": training_seed,
            "eval_seed": eval_seed,
            "matchup": 0,
            "pair_index": 0,
            "game_in_pair": seat,
            "candidate_team": "team-a" if seat == 0 else "team-b",
            "opponent_team": "team-b" if seat == 0 else "team-a",
            "candidate_role": "p1" if seat == 0 else "p2",
            "battle_seed": [eval_seed, 2, 3, 4],
            "cell": cell,
            "result": result,
        }
        for training_seed in (11, 29, 47)
        for eval_seed in (101, 202, 303)
        for seat in (0, 1)
        for cell, result in (
            ("source-source", "win"),
            ("source-target", "loss"),
            ("native-target", "win"),
            ("adapted-g01-target", "tie"),
        )
    ]


def test_paired_metrics_include_ties_and_bootstrap_training_seeds() -> None:
    report = ft.summarize_transfer(rows(), 1)
    for team in ("all", "team-a", "team-b"):
        metrics = report["by_candidate_team"][team]["metrics"]
        for name, value in (
            ("transfer_loss_ppg", 1),
            ("recovery_g01_ppg", 0.5),
            ("native_gap_g01_ppg", 0.5),
        ):
            assert metrics[name]["mean"] == value
            assert metrics[name]["ci_lower"] == value
            assert metrics[name]["ci_upper"] == value
            assert metrics[name]["n"] == 3  # Games and seats are not independent replicates.
    assert report["total_games"] == 72
    assert report["excluded_paired_blocks"] == 0


def test_unfinished_excludes_entire_matched_block() -> None:
    games = rows()
    games[0]["result"] = "unfinished"
    report = ft.summarize_transfer(games, 1)
    assert report["excluded_paired_blocks"] == 1
    assert report["unfinished_games"] == 1
    assert report["by_candidate_team"]["all"]["paired_blocks"] == 17
    assert report["by_candidate_team"]["all"]["metrics"]["transfer_loss_ppg"]["mean"] == 1


@pytest.mark.parametrize(
    "defect",
    [
        "duplicate",
        "missing",
        "seed",
        "team",
        "unknown",
        "all-unfinished",
        "seat",
        "schedule",
        "result",
        "battle-seed",
    ],
)
def test_reject_invalid_comparisons(defect: str) -> None:
    games = rows()
    if defect == "duplicate":
        games.append(copy.deepcopy(games[0]))
    elif defect == "missing":
        games.pop()
    elif defect == "seed":
        games = [g for g in games if g["training_seed"] != 47]
    elif defect == "team":
        games[1]["candidate_team"] = "wrong-team"
    elif defect == "unknown":
        games[0]["cell"] = "other"
    elif defect == "seat":
        games = [g for g in games if g["game_in_pair"] == 0]
    elif defect == "schedule":
        games = [g for g in games if g["training_seed"] != 47 or g["eval_seed"] != 303]
    elif defect == "result":
        games[0]["result"] = "invalid"
    elif defect == "battle-seed":
        games[0]["battle_seed"] = [1, 2, 3, 4]
    else:
        for game in games:
            game["result"] = "unfinished"
    with pytest.raises(ValueError):
        ft.summarize_transfer(games, 1)


@pytest.mark.parametrize(
    "overrides",
    [
        {"training_seeds": (11, 29)},
        {"evaluation_seeds": (11, 202, 303)},
        {"training_seeds": (11, 11, 47)},
        {"generations": 0},
        {"population": 0},
        {"elites": 3},
        {"pairs": 0},
        {"workers": 0},
    ],
)
def test_invalid_budget_or_seed_schedule(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        ft.FullTransferConfig(**overrides).validate()


def test_pipeline_freezes_source_and_uses_only_training_split(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def battle(
        candidate: BattleAgent,
        opponent: BattleAgent,
        format_id: str,
        own: str,
        other: str,
        role: str,
        seed: tuple[int, int, int, int],
        showdown_dir: Path,
        *,
        skip_build: bool,
    ) -> EvaluationBattleResult:
        calls.append(
            dict(
                candidate=candidate.name,
                format_id=format_id,
                own=own,
                other=other,
                role=role,
                seed=seed,
            )
        )
        return EvaluationBattleResult(
            winner=opponent.name,
            turns=5,
            duration_seconds=0.01,
            candidate_decisions=5,
            opponent_decisions=5,
            candidate_protect_uses=1,
            opponent_protect_uses=1,
            protect_depleted=False,
            candidate_won=False,
            end_reason="win",
            replay={"log": [], "decisions": []},
        )

    monkeypatch.setattr(ft, "ProcessPoolExecutor", ThreadPoolExecutor)
    monkeypatch.setattr(ft, "run_evaluation_battle", battle)
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: ft.SIMULATOR_REVISION)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess([], 0))
    report = ft.run_full_transfer(tmp_path, showdown_dir=tmp_path)
    assert report["total_games"] == 216
    assert report["training_games"] == 108
    manifest = load_manifest(ft.MANIFEST_PATH)
    training = {manifest.teams[t].packed for t in manifest.splits["training"]}
    test = {manifest.teams[t].packed for t in manifest.splits["test"]}
    for call in calls:
        pool = training if call["candidate"] == "Candidate" else test
        assert call["own"] in pool and call["other"] in pool
    for seed in (11, 29, 47):
        source = json.loads((tmp_path / f"checkpoints/source-s{seed}-g01.json").read_text())
        initial = json.loads((tmp_path / f"checkpoints/adapted-s{seed}-g00.json").read_text())
        assert initial["params"] == source["params"]
        assert source["format_id"] == ft.SOURCE_FORMAT
        assert initial["format_id"] == "gen9championsdoublescustomgame"
    games = json.loads((tmp_path / "results.json").read_text())["games"]
    assert len(list((tmp_path / "replays").glob("*.json.gz"))) == 216
    for a in games:
        matched = [
            b
            for b in games
            if all(
                a[k] == b[k]
                for k in ("training_seed", "eval_seed", "matchup", "pair_index", "game_in_pair")
            )
        ]
        assert len(matched) == 4
        assert all(a["battle_seed"] == b["battle_seed"] for b in matched)
    assert json.loads((tmp_path / "transfer_report.json").read_text())["limitations"]
    assert summarize_recovery([tmp_path / "results.json"])["series"] == []
    with pytest.raises(ValueError, match="empty"):
        ft.run_full_transfer(tmp_path)


def test_simulator_pin_fails_before_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: "wrong")
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="revision"):
        ft.run_full_transfer(output, showdown_dir=tmp_path)
    assert not output.exists()


def test_cli_rejects_invalid_budget(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["measure-full-transfer", "--output-dir", str(tmp_path), "--pairs", "0"]) == 2
    assert "positive" in capsys.readouterr().err


def test_dirty_simulator_fails_before_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subprocess, "check_output", lambda *a, **k: ft.SIMULATOR_REVISION)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess([], 1))
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="clean checkout"):
        ft.run_full_transfer(output, showdown_dir=tmp_path)
    assert not output.exists()


def test_unfinished_training_game_is_never_scored_as_a_draw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import asdict

    from vgc_rulebreak.agents.trained import HEURISTIC_PARAMS
    from vgc_rulebreak.training import GameTask

    def unfinished(*args: object, **kwargs: object) -> EvaluationBattleResult:
        return EvaluationBattleResult(
            winner=None,
            turns=60,
            duration_seconds=0.1,
            candidate_decisions=60,
            opponent_decisions=60,
            candidate_protect_uses=2,
            opponent_protect_uses=2,
            protect_depleted=False,
            candidate_won=False,
            end_reason="turn-limit",
        )

    monkeypatch.setattr(ft, "run_evaluation_battle", unfinished)
    task = GameTask(asdict(HEURISTIC_PARAMS), ft.SOURCE_FORMAT, "a", "b", "p1", (1, 2, 3, 4), None)
    with pytest.raises(ValueError, match="unfinished training"):
        ft._training_game(task)
