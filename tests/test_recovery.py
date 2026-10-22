"""Tests for grouping checkpoint evaluations into habit-recovery series."""

import json
from pathlib import Path
from typing import Any

import pytest

from vgc_rulebreak.cli import main
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
