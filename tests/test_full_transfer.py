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
from vgc_rulebreak.simulator.process import ShowdownProcess


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


@pytest.mark.parametrize("compare_pools", [False, True])
def test_pipeline_freezes_source_and_uses_only_training_split(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    compare_pools: bool,
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
                opponent=opponent.name,
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
    report = ft.run_full_transfer(
        tmp_path, ft.FullTransferConfig(compare_opponent_pools=compare_pools), showdown_dir=tmp_path
    )
    expected_games = 576 if compare_pools else 216
    assert report["total_games"] == expected_games
    assert report["training_games"] == 108
    manifest = load_manifest(ft.MANIFEST_PATH)
    training = {manifest.teams[t].packed for t in manifest.splits["training"]}
    test = {manifest.teams[t].packed for t in manifest.splits["test"]}
    extended, pools = ft.load_opponent_pools()
    new = {extended.teams[t].packed for t in pools["new"]}
    for call in calls:
        pool = training if call["candidate"] == "Candidate" else test
        assert call["own"] in pool
        assert call["other"] in (test | new if compare_pools and pool == test else pool)
        assert call["opponent"] == "HeuristicBaseline"
    for seed in (11, 29, 47):
        source = json.loads((tmp_path / f"checkpoints/source-s{seed}-g01.json").read_text())
        initial = json.loads((tmp_path / f"checkpoints/adapted-s{seed}-g00.json").read_text())
        assert initial["params"] == source["params"]
        assert source["format_id"] == ft.SOURCE_FORMAT
        assert initial["format_id"] == "gen9championsdoublescustomgame"
    games = json.loads((tmp_path / "results.json").read_text())["games"]
    assert len(list((tmp_path / "replays").glob("*.json.gz"))) == expected_games
    for a in games:
        matched = [
            b
            for b in games
            if all(
                a[k] == b[k]
                for k in ("training_seed", "eval_seed", "matchup", "pair_index", "game_in_pair")
            )
        ]
        assert len(matched) == (8 if compare_pools else 4)
        assert all(a["battle_seed"] == b["battle_seed"] for b in matched)
    if compare_pools:
        assert report["opponent_pools"] == pools
        assert len(report["new_opponents_sha256"]) == 64
        for game in games:
            assert game["candidate_team"] in manifest.splits["test"]
            assert game["opponent_team"] in pools[game["opponent_pool"]]
        assert report["by_candidate_team"]["all"]["paired_blocks"] == 72
        assert set(report["by_candidate_team"]) == {"all", *manifest.splits["test"]}
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


def pool_rows() -> list[dict[str, Any]]:
    outcomes = {
        "source-source": "tie",
        "source-target": "win",
        "native-target": "loss",
        "adapted-g01-target": "win",
    }
    return [
        {
            **game,
            "opponent_pool": pool,
            "opponent_team": game["opponent_team"] if pool == "fixed" else "new-opponent",
            "result": game["result"] if pool == "fixed" else outcomes[game["cell"]],
            "checkpoint": f"{game['training_seed']}/{game['cell']}.json",
            "format_id": ft.SOURCE_FORMAT if game["cell"] == "source-source" else "target",
            "opponent": "HeuristicBaseline",
        }
        for game in rows()
        for pool in ("fixed", "new")
    ]


def test_pool_metrics_and_paired_differences() -> None:
    report = ft.summarize_transfer(pool_rows(), 1, compare_opponent_pools=True)
    for team in ("all", "team-a", "team-b"):
        metrics = report["by_candidate_team"][team]["metrics"]
        for name, value in (
            ("fixed/transfer_loss_ppg", 1),
            ("new/transfer_loss_ppg", -0.5),
            ("new_minus_fixed/transfer_loss_ppg", -1.5),
            ("new_minus_fixed/recovery_g01_ppg", -0.5),
            ("new_minus_fixed/native_gap_g01_ppg", -1.5),
            ("new_minus_fixed/source-target", 1),
        ):
            assert metrics[name]["mean"] == value
            assert metrics[name]["ci_lower"] == value
            assert metrics[name]["ci_upper"] == value
            assert metrics[name]["n"] == 3


def test_unfinished_pool_game_excludes_both_pools_and_all_checkpoints() -> None:
    games = pool_rows()
    games[1]["result"] = "unfinished"
    report = ft.summarize_transfer(games, 1, compare_opponent_pools=True)
    assert report["excluded_paired_blocks"] == 1
    assert report["unfinished_games"] == 1
    assert report["by_candidate_team"]["all"]["paired_blocks"] == 17
    assert (
        report["by_candidate_team"]["all"]["metrics"]["new_minus_fixed/transfer_loss_ppg"]["mean"]
        == -1.5
    )


@pytest.mark.parametrize(
    "defect", ["missing-pool", "unknown-pool", "checkpoint", "opponent", "format", "policy", "seat"]
)
def test_pool_pairing_rejects_mismatched_inputs(defect: str) -> None:
    games = pool_rows()
    if defect == "missing-pool":
        games = [g for g in games if g["opponent_pool"] == "fixed"]
    elif defect == "unknown-pool":
        games[1]["opponent_pool"] = "other"
    elif defect == "checkpoint":
        games[1]["checkpoint"] = "another-checkpoint.json"
    elif defect == "format":
        games[1]["format_id"] = "another-format"
    elif defect == "policy":
        games[1]["opponent"] = "another-policy"
    elif defect == "seat":
        for game in games:
            game["candidate_role"] = "p1"
    else:
        games[1]["opponent_team"] = "wrong-team"
    with pytest.raises(ValueError):
        ft.summarize_transfer(games, 1, compare_opponent_pools=True)


@pytest.mark.parametrize("defect", ["family", "packed", "id", "size", "split"])
def test_new_opponents_reject_contamination_or_unequal_pools(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, defect: str
) -> None:
    data = json.loads(ft.NEW_OPPONENTS_PATH.read_text())
    original = load_manifest(ft.MANIFEST_PATH)
    first = data["teams"]["new-snow"]
    if defect == "family":
        first["family"] = original.teams["train-rain"].family
    elif defect == "packed":
        first["packed"] = original.teams["test-sand"].packed
    elif defect == "id":
        data["teams"]["test-sand"] = data["teams"].pop("new-snow")
    elif defect == "size":
        data["teams"].pop("new-snow")
    else:
        first["split"] = "training"
    path = tmp_path / "opponents.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(ft, "NEW_OPPONENTS_PATH", path)
    with pytest.raises(ValueError):
        ft.load_opponent_pools()


def test_pool_bootstrap_weights_training_seeds_equally() -> None:
    games = pool_rows()
    for game in games:
        if game["training_seed"] == 47 and game["eval_seed"] != 101:
            game["result"] = "unfinished"
        elif game["training_seed"] == 47 and game["opponent_pool"] == "new":
            game["result"] = "loss"
    metrics = ft.summarize_transfer(games, 1, compare_opponent_pools=True)["by_candidate_team"][
        "all"
    ]["metrics"]
    # Seed deltas: 1, 1, 0. The last seed has fewer retained blocks, but equal weight.
    assert metrics["new_minus_fixed/source-target"]["mean"] == pytest.approx(2 / 3, abs=0.0001)
    assert metrics["new_minus_fixed/source-target"]["n"] == 3


def test_pool_difference_interval_preserves_seed_pairing() -> None:
    games = pool_rows()
    for game in games:
        if game["cell"] == "source-target":
            game["result"] = {11: "loss", 29: "tie", 47: "win"}[game["training_seed"]]
    metrics = ft.summarize_transfer(games, 1, compare_opponent_pools=True)["by_candidate_team"][
        "all"
    ]["metrics"]
    assert metrics["fixed/source-target"]["ci_lower"] == 0
    assert metrics["fixed/source-target"]["ci_upper"] == 1
    assert metrics["new_minus_fixed/source-target"]["ci_lower"] == 0
    assert metrics["new_minus_fixed/source-target"]["ci_upper"] == 0


def test_pool_comparison_retains_each_adapted_checkpoint() -> None:
    games = pool_rows()
    games += [
        {
            **game,
            "cell": "adapted-g02-target",
            "checkpoint": f"{game['training_seed']}/adapted-g02.json",
            "result": "win" if game["opponent_pool"] == "fixed" else "tie",
        }
        for game in games
        if game["cell"] == "adapted-g01-target"
    ]
    metrics = ft.summarize_transfer(games, 2, compare_opponent_pools=True)["by_candidate_team"][
        "all"
    ]["metrics"]
    assert metrics["new_minus_fixed/recovery_g01_ppg"]["mean"] == -0.5
    assert metrics["new_minus_fixed/recovery_g02_ppg"]["mean"] == -1.5
    assert metrics["new_minus_fixed/native_gap_g02_ppg"]["mean"] == -0.5


def test_cli_forwards_pool_comparison_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def run(output: Path, config: ft.FullTransferConfig, sd: Path | None) -> dict[str, bool]:
        assert output == tmp_path
        assert sd is None
        return {"compare_pools": config.compare_opponent_pools}

    monkeypatch.setattr(ft, "run_full_transfer", run)
    assert (
        main(["measure-full-transfer", "--output-dir", str(tmp_path), "--compare-opponent-pools"])
        == 0
    )
    assert json.loads(capsys.readouterr().out) == {"compare_pools": True}


def test_new_opponent_packed_teams_match_sheets_and_stats_across_domains() -> None:
    try:
        sd = ShowdownProcess._resolve_showdown_dir(None)
    except FileNotFoundError:
        pytest.skip("Showdown not found in default paths")
    script = """
    const fs = require('fs');
    const {Battle} = require('./dist/sim/battle.js');
    const {Teams} = require('./dist/sim/teams.js');
    const teams = JSON.parse(fs.readFileSync(0, 'utf8'));
    console.log(JSON.stringify(teams.map(team => ({
      unpacked: Teams.unpack(team),
      stats: ['gen9doublescustomgame', 'gen9championsdoublescustomgame'].map(formatid => {
        const battle = new Battle({formatid, seed: [1, 2, 3, 4]});
        battle.setPlayer('p1', {name: 'Candidate', team});
        battle.setPlayer('p2', {name: 'Opponent', team});
        return battle.p1.pokemon.map(p => ({hp: p.maxhp, ...p.storedStats}));
      }),
    }))));
    """
    manifest, pools = ft.load_opponent_pools()
    teams = [manifest.teams[t] for t in pools["new"]]
    result = subprocess.run(
        ["node", "-e", script],
        cwd=sd,
        input=json.dumps([t.packed for t in teams]),
        capture_output=True,
        text=True,
        check=True,
    )
    observations = json.loads(result.stdout)
    for team, observed in zip(teams, observations, strict=True):
        assert observed["stats"][0] == observed["stats"][1]
        for stats in observed["stats"][0]:
            assert set(stats) == {"hp", "atk", "def", "spa", "spd", "spe"}
            assert all(value > 0 for value in stats.values())
        assert len(observed["unpacked"]) == 4
        for member, unpacked in zip(team.pokemon, observed["unpacked"], strict=True):
            assert unpacked["species"] == member.species
            assert unpacked["ability"] == member.ability
            assert unpacked["moves"] == list(member.moves)
            assert unpacked["nature"] == member.nature == "Serious"
            assert unpacked["evs"] == member.evs
            assert unpacked["item"] == member.item == ""
            assert unpacked["teraType"] == member.tera_type
            assert unpacked["level"] == 50
