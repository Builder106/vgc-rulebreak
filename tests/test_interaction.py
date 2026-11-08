"""Factorial contrasts, matched RNGs, provenance gates and saved evidence."""

import gzip
import json
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest

from vgc_rulebreak import interaction
from vgc_rulebreak.cli import main
from vgc_rulebreak.evaluation import EvaluationBattleResult
from vgc_rulebreak.manifest import load_manifest
from vgc_rulebreak.spec import ExperimentSpec, validate_spec


@pytest.fixture
def spec() -> ExperimentSpec:
    return validate_spec(json.loads(Path("experiments/protect-pp.json").read_text()))


@pytest.fixture
def prerequisite(tmp_path: Path, spec: ExperimentSpec) -> Path:
    path = tmp_path / "study-p.json"
    path.write_text(
        json.dumps(
            {
                "spec": spec.name,
                "simulator_revision": spec.simulator_revision,
                "formats": {
                    "protect-16": "gen9rulebreakprotect16",
                    "protect-8": "gen9rulebreakprotect8",
                },
                "total_evaluation_games": 72,
                "findings": ["synthetic prerequisite for runner tests"],
            }
        )
    )
    return path


def test_signed_factorial_interaction_and_missing_cells() -> None:
    points = {"16-persist": 0.0, "16-reset": 1.0, "8-persist": 1.0, "8-reset": 0.0}
    assert interaction.factorial_contrasts(points) == {
        "reset_at_16": 1.0,
        "reset_at_8": -1.0,
        "pp_at_persist": 1.0,
        "pp_at_reset": -1.0,
        "interaction": -2.0,
    }
    for invalid in ({}, {**points, "8-reset": float("nan")}, {**points, "8-reset": 1.1}):
        with pytest.raises(ValueError, match="four cells"):
            interaction.factorial_contrasts(invalid)


def test_bootstrap_clusters_evaluation_seeds_and_preserves_cancellation() -> None:
    points = {"16-persist": 0.0, "16-reset": 1.0, "8-persist": 0.0, "8-reset": 1.0}
    blocks = [{"eval_seed": 101, "points": points}] * 10
    blocks += [{"eval_seed": 202, "points": {cell: 0.5 for cell in interaction.FORMATS}}]
    summary = interaction.summarize_blocks(blocks)
    assert summary["contrasts"]["reset_at_16"]["mean"] == 0.5
    assert summary["contrasts"]["reset_at_16"]["n"] == 2
    assert summary["contrasts"]["interaction"]["ci_lower"] == 0.0
    assert summary["contrasts"]["interaction"]["ci_upper"] == 0.0
    with pytest.raises(ValueError, match="empty"):
        interaction.summarize_blocks([])


def test_runner_matches_cells_mirrors_seats_and_saves_replays(
    tmp_path: Path, spec: ExperimentSpec, prerequisite: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = load_manifest(Path("experiments/teams/protect-pp.json"))
    calls: list[dict[str, Any]] = []

    def battle(*args: object, **kwargs: object) -> EvaluationBattleResult:
        calls.append({"args": args, **kwargs})
        format_id = str(args[2])
        won = format_id.endswith("16ragefistreset")
        end_reason = "win"
        if format_id.endswith("persist"):
            end_reason = "tie" if "protect16" in format_id else "turn-limit"
        return EvaluationBattleResult(
            winner=("candidate" if won else "opponent") if end_reason == "win" else None,
            turns=2,
            duration_seconds=0.01,
            candidate_decisions=1,
            opponent_decisions=1,
            candidate_protect_uses=0,
            opponent_protect_uses=0,
            protect_depleted=False,
            candidate_won=won,
            end_reason=end_reason,
            replay={"log": [], "decisions": []},
        )

    monkeypatch.setattr(interaction, "run_evaluation_battle", battle)
    monkeypatch.setattr(
        "vgc_rulebreak.interaction.ShowdownProcess._resolve_showdown_dir", lambda _: tmp_path
    )
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(return_value=subprocess.CompletedProcess([], 0, spec.simulator_revision + "\n")),
    )
    root = tmp_path / "run"
    report = interaction.run_interaction(spec, manifest, prerequisite, root, pairs=1)
    assert report["total_games"] == len(calls) == 288
    saved = json.loads((root / "results.json").read_text())
    assert len(saved["games"]) == 288
    assert len(report["strata"]) == 12
    assert len(list((root / "replays").glob("*.gz"))) == 288
    for offset in range(0, len(calls), 8):
        mirrored = calls[offset : offset + 8]
        assert [c["candidate_role"] for c in mirrored] == ["p1"] * 4 + ["p2"] * 4
        assert len({c["seed"] for c in mirrored}) == 1
        assert len({(c["args"][3], c["args"][4]) for c in mirrored}) == 1
        # Fresh policy objects are required because RandomAgent.reset keeps its RNG state.
        assert len({id(c["args"][0]) for c in mirrored}) == 8
        assert len({id(c["args"][1]) for c in mirrored}) == 8
        games = saved["games"][offset : offset + 8]
        for key in ("candidate_policy_seed", "opponent_policy_seed", "battle_seed"):
            assert len({json.dumps(g[key]) for g in games}) == 1
        rngs = [c["args"][1]._rng.getstate() for c in mirrored if hasattr(c["args"][1], "_rng")]
        assert all(state == rngs[0] for state in rngs)
    for game in saved["games"]:
        replay = json.loads(gzip.decompress((root / game["replay"]).read_bytes()))
        assert replay["format_id"] == game["format_id"]
        assert replay["battle_seed"] == game["battle_seed"]
        assert (
            replay["players"][game["candidate_role"]]["team"]
            == manifest.teams[game["candidate_team"]].packed
        )
    assert report["by_candidate"]["random"]["contrasts"]["interaction"]["mean"] == -1.0
    assert report["by_candidate"]["random"]["contrasts"]["reset_at_16"]["mean"] == 0.5
    assert report["strata"][0]["termination"]["8-persist"]["turn-limit"] == 6
    with pytest.raises(ValueError, match="empty"):
        interaction.run_interaction(spec, manifest, prerequisite, root)


@pytest.mark.parametrize("invalid", ["revision", "dirty", "stalled"])
def test_runner_rejects_wrong_simulator_and_incomplete_games(
    tmp_path: Path,
    spec: ExperimentSpec,
    prerequisite: Path,
    monkeypatch: pytest.MonkeyPatch,
    invalid: str,
) -> None:
    monkeypatch.setattr(
        "vgc_rulebreak.interaction.ShowdownProcess._resolve_showdown_dir", lambda _: tmp_path
    )
    revision = "wrong" if invalid == "revision" else spec.simulator_revision
    monkeypatch.setattr(
        subprocess,
        "run",
        Mock(return_value=subprocess.CompletedProcess([], int(invalid == "dirty"), revision)),
    )
    runner = Mock(
        return_value=EvaluationBattleResult(
            winner=None,
            turns=0,
            duration_seconds=0,
            candidate_decisions=0,
            opponent_decisions=0,
            candidate_protect_uses=0,
            opponent_protect_uses=0,
            protect_depleted=False,
            candidate_won=False,
            end_reason="stalled",
            replay={"log": [], "decisions": []},
        )
    )
    monkeypatch.setattr(interaction, "run_evaluation_battle", runner)
    error = RuntimeError if invalid == "stalled" else ValueError
    with pytest.raises(error, match=r"Incomplete|clean checkout"):
        interaction.run_interaction(
            spec,
            load_manifest(Path("experiments/teams/protect-pp.json")),
            prerequisite,
            tmp_path / "run",
        )
    assert runner.call_count == 4 * int(invalid == "stalled")
    assert not (tmp_path / "run" / "interaction_report.json").exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("total_evaluation_games", 0),
        ("simulator_revision", "wrong"),
        ("formats", {"protect-16": "gen9doublescustomgame"}),
        ("findings", []),
    ],
)
def test_prerequisite_fails_before_simulation(
    tmp_path: Path,
    spec: ExperimentSpec,
    prerequisite: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: object,
) -> None:
    raw = json.loads(prerequisite.read_text())
    raw[field] = value
    prerequisite.write_text(json.dumps(raw))
    runner = Mock()
    monkeypatch.setattr(interaction, "run_evaluation_battle", runner)
    with pytest.raises(ValueError, match="completed Protect-only"):
        interaction.run_interaction(
            spec,
            load_manifest(Path("experiments/teams/protect-pp.json")),
            prerequisite,
            tmp_path / "run",
        )
    runner.assert_not_called()


def test_duplicate_eval_seeds_fail(
    spec: ExperimentSpec, prerequisite: Path, tmp_path: Path
) -> None:
    assert spec.evaluation is not None
    spec = replace(spec, evaluation=replace(spec.evaluation, evaluation_seeds=(101, 101, 202)))
    with pytest.raises(ValueError, match="distinct"):
        interaction.run_interaction(
            spec,
            load_manifest(Path("experiments/teams/protect-pp.json")),
            prerequisite,
            tmp_path / "run",
        )


def test_cli_reports_invalid_prerequisite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(
            [
                "rage-fist-interaction",
                "--study-p-result",
                str(tmp_path / "missing.json"),
                "--output-dir",
                str(tmp_path / "run"),
            ]
        )
        == 2
    )
    assert "Interaction error" in capsys.readouterr().err
