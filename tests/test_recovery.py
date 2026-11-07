"""Tests for grouping checkpoint evaluations into habit-recovery series."""

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from vgc_rulebreak.cli import main
from vgc_rulebreak.mistakes import DETECTOR
from vgc_rulebreak.recovery import summarize_recovery


def game(result: str, uses: int, chances: int, depleted: bool = False) -> dict[str, Any]:
    return {
        "variant": "protect-8",
        "opponent": "HeuristicBaseline",
        "result": result,
        "candidate_protect_uses": uses,
        "candidate_protect_opportunities": chances,
        "protect_depleted": depleted,
    }


def write_run(root: Path, name: str, games: list[dict[str, Any]]) -> Path:
    path = root / name / "results.json"
    path.parent.mkdir(parents=True)
    document = {
        "spec": "protect-pp",
        "simulator_revision": "9fb3a5b",
        "summary": {"candidate_name": name},
        "games": games,
    }
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_summarize_recovery_groups_by_generation_and_seed(tmp_path: Path) -> None:
    write_run(tmp_path, "adapted-s11-g00", [game("loss", 4, 8, True), game("win", 2, 8)])
    write_run(tmp_path, "adapted-s29-g00", [game("win", 0, 8), game("tie", 0, 8)])
    write_run(tmp_path, "adapted-s11-g01", [game("win", 1, 10), game("win", 1, 10)])
    write_run(tmp_path, "HeuristicCandidate", [game("win", 0, 1)])

    dataset = summarize_recovery(tmp_path.rglob("results.json"))

    assert dataset["spec"] == ["protect-pp"]
    assert dataset["opponent"] == ["HeuristicBaseline"]
    [series] = dataset["series"]
    assert (series["agent"], series["variant"]) == ("adapted", "protect-8")
    first, second = series["points"]
    assert first["generation"] == 0
    assert first["seeds"]["11"]["points_per_game"] == 0.5
    assert first["seeds"]["11"]["protect_use_rate"] == 6 / 16
    assert first["seeds"]["11"]["depletion_rate"] == 0.5
    assert first["seeds"]["29"]["points_per_game"] == 0.75
    assert first["points_per_game"] == {"mean": 0.625, "min": 0.5, "max": 0.75}
    assert first["protect_use_rate"]["min"] == 0.0
    assert first["games"] == 4
    assert first["protect_opportunities"] == 32
    assert second["generation"] == 1
    assert list(second["seeds"]) == ["11"]
    assert second["points_per_game"]["mean"] == 1.0


def test_cli_summarize_recovery(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    write_run(tmp_path / "runs", "native-s47-g10", [game("win", 1, 4)])
    out = tmp_path / "data" / "habit-recovery.json"

    assert main(["summarize-recovery", "--runs", str(tmp_path / "runs"), "--output", str(out)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["series"][0]["agent"] == "native"
    assert "1 series, 1 points" in capsys.readouterr().out

    assert (
        main(["summarize-recovery", "--runs", str(tmp_path / "empty"), "--output", str(out)]) == 2
    )


def measured_game(events: int, opportunities: int) -> dict[str, Any]:
    return {
        **game("win", 1, 4),
        "candidate_mistakes": {
            DETECTOR: {
                "detector_version": 1,
                "events": events,
                "eligible_opportunities": opportunities,
            }
        },
    }


def test_mistake_rates_pool_opportunities_and_keep_seed_spread(tmp_path: Path) -> None:
    write_run(tmp_path, "adapted-s11-g00", [measured_game(1, 1), measured_game(0, 9)])
    write_run(tmp_path, "adapted-s29-g00", [measured_game(1, 2)])
    write_run(tmp_path, "adapted-s47-g00", [measured_game(0, 0), game("loss", 0, 0)])

    result = summarize_recovery(tmp_path.rglob("results.json"))
    metric = result["series"][0]["points"][0]["candidate_mistakes"][DETECTOR]
    assert metric["events"] == 2
    assert metric["eligible_opportunities"] == 12
    assert metric["rate"] == 2 / 12  # Not an unweighted average of game rates.
    assert metric["measured_games"] == 4
    assert metric["unmeasured_games"] == 1
    assert metric["seeds"]["11"]["rate"] == 0.1
    assert metric["seeds"]["29"]["rate"] == 0.5
    assert metric["seeds"]["47"]["rate"] is None
    assert metric["seeds_with_opportunities"] == 2
    assert metric["rate_across_seeds"] == {"mean": 0.3, "min": 0.1, "max": 0.5}


def test_legacy_replays_are_backfilled_and_missing_replays_are_unknown(tmp_path: Path) -> None:
    legacy = {**game("win", 2, 4), "candidate_role": "p2", "replay": "replays/game.json.gz"}
    path = write_run(tmp_path, "native-s11-g00", [legacy])
    original = path.read_bytes()
    request = {
        "active": [{"moves": [{"id": "protect", "pp": 8}, {"id": "tackle", "pp": 35}]}],
        "side": {"pokemon": [{"ident": "p2: Annihilape", "condition": "100/100"}]},
    }
    replay = {
        "decisions": [
            {"turn": turn, "side": "p2", "choice": "move 1", "request": request} for turn in (1, 2)
        ]
    }
    replay_path = path.parent / legacy["replay"]
    replay_path.parent.mkdir()
    replay_path.write_bytes(gzip.compress(json.dumps(replay).encode()))
    result = summarize_recovery([path])
    metric = result["series"][0]["points"][0]["candidate_mistakes"][DETECTOR]
    assert metric["events"] == metric["eligible_opportunities"] == 1
    assert metric["rate"] == 1.0
    assert path.read_bytes() == original

    replay_path.unlink()
    result = summarize_recovery([path])
    metric = result["series"][0]["points"][0]["candidate_mistakes"][DETECTOR]
    assert metric["rate"] is None
    assert metric["rate_across_seeds"] is None
    assert metric["measured_games"] == 0
    assert metric["unmeasured_games"] == 1


def test_different_detector_versions_cannot_be_pooled(tmp_path: Path) -> None:
    other_version = measured_game(1, 2)
    other_version["candidate_mistakes"][DETECTOR]["detector_version"] = 2
    path = write_run(tmp_path, "native-s11-g00", [measured_game(1, 2), other_version])
    with pytest.raises(ValueError, match="different candidate-mistake detector versions"):
        summarize_recovery([path])
