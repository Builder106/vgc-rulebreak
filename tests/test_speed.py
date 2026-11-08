"""Legal-build equivalence and paired one-turn pivot evidence for Study S."""

import copy
import gzip
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from vgc_rulebreak import speed
from vgc_rulebreak.cli import main
from vgc_rulebreak.simulator.process import ShowdownProcess
from vgc_rulebreak.speed import (
    comparison_config,
    equivalent_evs,
    run_speed_comparison,
    summarize_speed,
)


def test_equivalent_allocation_matches_every_legal_single_stat_point() -> None:
    for points in range(33):
        ev = equivalent_evs({"spe": points})["spe"]
        for base in (5, 47, 60, 135):
            gen9 = (2 * base + 31 + ev // 4) // 2 + 5
            champions = base + points + 20
            assert gen9 == champions
    assert sum(equivalent_evs({"hp": 32, "def": 32, "spd": 1}).values()) == 508


@pytest.mark.parametrize(
    "points",
    [{"spe": -1}, {"spe": 33}, {"speed": 1}, {"spe": True}, {"hp": 32, "def": 32, "spd": 2}],
)
def test_reject_illegal_or_unmatchable_allocation(points: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        equivalent_evs(points)


def test_fixture_config_is_reproducible_and_labels_minimum_speed_exception() -> None:
    config = comparison_config(2, 79)
    assert config == comparison_config(2, 79)
    assert config["seeds"] != comparison_config(2, 80)["seeds"]
    for scenario in config["scenarios"]:
        iv = scenario["teams"]["ev"]["candidate"][0]["ivs"]["spe"]
        assert iv == (0 if scenario["name"] == "minimum_legal_speed" else 31)
        assert scenario["teams"]["sp"]["candidate"][0]["ivs"]["spe"] == 31
    with pytest.raises(ValueError):
        comparison_config(1)


def _rows() -> list[dict[str, Any]]:
    return [
        {
            "scenario": "fixture",
            "context": "normal",
            "seed": [seed, 2, 3, 4],
            "seat": seat,
            "system": system,
            "action": action,
            "pivot_before_opponent": system == "sp",
            "pivot_completed": True,
            "incoming_damage_fraction": 0.2 if action == "switch" else 0.1,
            "team_damage_fraction": 0.3 if action == "switch" else 0.1,
        }
        for seed in (1, 5)
        for seat in ("p1", "p2")
        for system in ("ev", "sp")
        for action in ("pivot", "switch")
    ]


def test_summary_pairs_actions_and_systems_with_seed_as_uncertainty_unit() -> None:
    summary = summarize_speed(_rows())[0]
    assert summary["eligible_paired_decisions"] == 4
    metrics = summary["metrics"]
    assert metrics["move_order_changed"]["mean"] == 1
    assert metrics["ev_pivot_minus_switch_incoming_damage_fraction"]["mean"] == -0.1
    assert metrics["sp_minus_ev_pivot_effect_team_damage_fraction"]["mean"] == 0
    assert metrics["move_order_changed"]["n"] == 2


@pytest.mark.parametrize("defect", ["duplicate", "cell", "seat", "seed", "empty"])
def test_summary_rejects_missing_or_duplicate_pairs(defect: str) -> None:
    rows = _rows()
    if defect == "duplicate":
        rows.append(copy.deepcopy(rows[0]))
    elif defect == "cell":
        rows.pop()
    elif defect == "seat":
        rows = [row for row in rows if row["seat"] == "p1"]
    elif defect == "seed":
        rows = rows[:8]
    else:
        rows = []
    with pytest.raises(ValueError):
        summarize_speed(rows)


def test_cli_rejects_invalid_budget(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["compare-speed", "--trials", "1", "--output-dir", str(tmp_path)]) == 2
    assert "at least two" in capsys.readouterr().err


def test_existing_evidence_is_never_overwritten(tmp_path: Path) -> None:
    evidence = tmp_path / "results.json"
    evidence.write_text("existing", encoding="utf-8")
    with pytest.raises(ValueError, match="never overwritten"):
        run_speed_comparison(tmp_path, trials=2)
    assert evidence.read_text(encoding="utf-8") == "existing"


@pytest.mark.parametrize("revision,dirty", [("wrong", 0), (speed.SIMULATOR_REVISION, 1)])
def test_reject_unpinned_or_dirty_simulator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, revision: str, dirty: int
) -> None:
    responses = iter(
        [
            subprocess.CompletedProcess([], 0, revision + "\n"),
            subprocess.CompletedProcess([], dirty),
        ]
    )
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: next(responses))
    with pytest.raises(ValueError, match="clean checkout"):
        run_speed_comparison(tmp_path / "output", trials=2, showdown_dir=tmp_path)
    assert not (tmp_path / "output").exists()


def _showdown_available() -> bool:
    try:
        ShowdownProcess._resolve_showdown_dir(None)
        return True
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _showdown_available(), reason="Showdown not found in default paths")
@pytest.mark.parametrize("field,value", [("ivs", 0), ("evs", 33)])
def test_live_champions_validator_rejects_illegal_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, value: int
) -> None:
    config = comparison_config(2)
    config["scenarios"][0]["teams"]["sp"]["candidate"][0][field]["spe"] = value
    monkeypatch.setattr(speed, "comparison_config", lambda *args: config)
    with pytest.raises(subprocess.CalledProcessError) as error:
        run_speed_comparison(tmp_path, trials=2)
    assert (
        "IVs are not maxed" in error.value.stderr
        if field == "ivs"
        else ("more than 32 Stat Points" in error.value.stderr)
    )
    assert not (tmp_path / "results.json").exists()


@pytest.mark.skipif(not _showdown_available(), reason="Showdown not found in default paths")
def test_live_legal_builds_move_order_pivot_cost_and_controls(tmp_path: Path) -> None:
    report = run_speed_comparison(tmp_path, trials=2)
    assert report["branches"] == 192
    with gzip.open(tmp_path / report["evidence"], "rt", encoding="utf-8") as stream:
        rows = json.load(stream)
    assert len(rows) == report["branches"]
    assert len(report["summary"]) == 12
    for row in rows:
        assert row["requests"]["candidate"]["active"][0]["moves"][0]["id"] == "partingshot"
        for pokemon in row["initial"]:
            for move in pokemon["moves"]:
                if move["id"] == "protect":
                    assert move["maxpp"] == 16
        if row["action"] == "switch":
            assert row["outgoing_damage"] == 0
        elif row["context"] == "opponent_protect":
            assert row["pivot_before_opponent"] is False
            assert row["pivot_completed"] is False
        else:
            assert row["pivot_completed"] is True
            assert (row["incoming_damage"] > 0) == row["pivot_before_opponent"]
            assert (row["outgoing_damage"] > 0) != row["pivot_before_opponent"]
    paired: dict[tuple[object, ...], dict[str, dict[str, Any]]] = {}
    for row in rows:
        key = row["scenario"], row["context"], tuple(row["seed"]), row["seat"], row["action"]
        paired.setdefault(key, {})[row["system"]] = row
    for (scenario, context, *_), systems in paired.items():
        ev, sp = systems["ev"], systems["sp"]
        for before, after in zip(ev["initial"], sp["initial"], strict=True):
            if scenario == "minimum_legal_speed" and before["species"] == "incineroar":
                assert before["stats"]["spe"] == 58
                assert after["stats"]["spe"] == 72
                before = copy.deepcopy(before)
                before["stats"]["spe"] = after["stats"]["spe"]
                before["speed"] = after["speed"]
            assert before == after
        if scenario != "minimum_legal_speed":
            assert ev["pivot_before_opponent"] == sp["pivot_before_opponent"]
        elif context in {"normal", "trick_room"} and ev["action"] == "pivot":
            assert ev["pivot_before_opponent"] != sp["pivot_before_opponent"]
