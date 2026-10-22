"""Tests for battle logs, decision capture, and per-game evaluation records."""

import gzip
import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from vgc_rulebreak.agents.base import BattleAgent
from vgc_rulebreak.cli import main
from vgc_rulebreak.evaluation import (
    AgentComparisonReport,
    EvaluationBattleResult,
    compare_study_agents,
    run_evaluation_battle,
)
from vgc_rulebreak.manifest import load_manifest
from vgc_rulebreak.records import GameContext, GameRecorder, game_outcome
from vgc_rulebreak.simulator.battle import BattleSession
from vgc_rulebreak.spec import validate_spec

SPEC_PATH = Path("experiments/protect-pp.json")
MANIFEST_PATH = Path("experiments/teams/protect-pp.json")
REQUEST = '|request|{"active": [{"moves": [{"id": "protect", "pp": 8}]}]}'


class ScriptedStream:
    """Battle stream that replays scripted simulator output."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.sent: list[str] = []

    def send(self, command: str) -> None:
        self.sent.append(command)

    def read_line(self, timeout: float = 5.0) -> str | None:
        return self.responses.pop(0) if self.responses else None

    def close(self) -> None:
        pass


class FixedAgent(BattleAgent):
    """Agent that always picks the first move."""

    def reset(self) -> None:
        pass

    def choose_action(self, request: dict[str, Any]) -> str:
        return "move 1"


def battle_script(winner: str) -> list[str]:
    return [
        "update",
        "|gametype|doubles",
        "|split|p1",
        "|switch|p1a: Annihilape|Annihilape, L50|187/187",
        "|switch|p1a: Annihilape|Annihilape, L50|100/100",
        "sideupdate",
        "p1",
        REQUEST,
        "sideupdate",
        "p2",
        REQUEST,
        "update",
        "|move|p1a: Annihilape|Protect|p1a: Annihilape",
        "|turn|1",
        f"|win|{winner}",
    ]


def make_context(**overrides: Any) -> GameContext:
    fields: dict[str, Any] = {
        "stage": "benchmark",
        "variant": "protect-8",
        "format_id": "gen9championsdoublescustomgame",
        "eval_seed": 101,
        "battle_seed": (1, 2, 3, 4),
        "candidate": "SourceAgent",
        "opponent": "RandomBaseline",
        "candidate_team": "test-annihilape-bulky",
        "opponent_team": "test-balance-pivot",
        "candidate_role": "p2",
        "pair_index": 0,
        "game_in_pair": 1,
    }
    fields.update(overrides)
    return GameContext(**fields)


def make_result(**overrides: Any) -> EvaluationBattleResult:
    fields: dict[str, Any] = {
        "winner": "SourceAgent",
        "turns": 9,
        "duration_seconds": 1.23456,
        "candidate_decisions": 9,
        "opponent_decisions": 9,
        "candidate_protect_uses": 3,
        "opponent_protect_uses": 1,
        "protect_depleted": False,
        "candidate_won": True,
        "end_reason": "win",
        "replay": {
            "log": ["|turn|1"],
            "decisions": [{"turn": 1, "side": "p2", "choice": "move 1"}],
        },
    }
    fields.update(overrides)
    return EvaluationBattleResult(**fields)


def test_battle_session_log_excludes_requests() -> None:
    session = BattleSession(ScriptedStream(battle_script("Alice")))
    session.start("gen9customgame", "Alice", "TeamA", "Bob", "TeamB")
    session.step("move 1", "move 1")

    assert "|switch|p1a: Annihilape|Annihilape, L50|187/187" in session.log
    assert "|move|p1a: Annihilape|Protect|p1a: Annihilape" in session.log
    assert session.log[-1] == "|win|Alice"
    assert not any(line.startswith("|request|") for line in session.log)


def test_run_evaluation_battle_captures_replay() -> None:
    stream = ScriptedStream(battle_script("Candidate"))

    class FakeProcess:
        def __init__(self, showdown_dir: Any) -> None:
            pass

        def __enter__(self) -> ScriptedStream:
            return stream

        def __exit__(self, *exc: Any) -> None:
            pass

    with patch("vgc_rulebreak.evaluation.ShowdownProcess", FakeProcess):
        result = run_evaluation_battle(
            candidate_agent=FixedAgent("Candidate"),
            opponent_agent=FixedAgent("Opponent"),
            format_id="gen9championsdoublescustomgame",
            candidate_team="TeamA",
            opponent_team="TeamB",
            candidate_role="p1",
        )

    assert result.candidate_won
    assert result.end_reason == "win"
    assert result.candidate_protect_uses == 1
    assert result.replay is not None
    assert [(d["side"], d["choice"], d["turn"]) for d in result.replay["decisions"]] == [
        ("p1", "move 1", 0),
        ("p2", "move 1", 0),
    ]
    assert result.replay["decisions"][0]["request"]["active"][0]["moves"][0]["id"] == "protect"
    assert result.replay["log"][-1] == "|win|Candidate"


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({}, "win"),
        ({"candidate_won": False, "winner": "RandomBaseline"}, "loss"),
        ({"candidate_won": False, "winner": None, "end_reason": "tie"}, "tie"),
        ({"candidate_won": False, "winner": None, "end_reason": "turn-limit"}, "unfinished"),
    ],
)
def test_game_outcome(overrides: dict[str, Any], expected: str) -> None:
    assert game_outcome(make_result(**overrides)) == expected


def test_recorder_writes_replay_and_results(tmp_path: Path) -> None:
    recorder = GameRecorder(tmp_path, {"test-annihilape-bulky": "PACKED-A"})
    game_id = recorder.record(make_context(), make_result())
    recorder.record(make_context(), make_result(replay=None))
    path = recorder.finish({"command": "compare-agents"}, {"entries": []})

    assert game_id == "g00001"
    replay = json.loads(gzip.decompress((tmp_path / "replays/g00001.json.gz").read_bytes()))
    assert replay["schema_version"] == 1
    assert replay["battle_seed"] == [1, 2, 3, 4]
    assert replay["players"]["p2"] == {
        "name": "SourceAgent",
        "team_id": "test-annihilape-bulky",
        "team": "PACKED-A",
    }
    assert replay["players"]["p1"]["name"] == "RandomBaseline"
    assert replay["decisions"][0]["choice"] == "move 1"

    results = json.loads(path.read_text(encoding="utf-8"))
    assert results["command"] == "compare-agents"
    assert [g["replay"] for g in results["games"]] == ["replays/g00001.json.gz", None]
    assert results["games"][0]["result"] == "win"
    assert results["games"][0]["duration_seconds"] == 1.235
    assert not (tmp_path / "replays/g00002.json.gz").exists()


def test_replay_bytes_are_reproducible(tmp_path: Path) -> None:
    first = GameRecorder(tmp_path / "a", {})
    second = GameRecorder(tmp_path / "b", {})
    first.record(make_context(), make_result())
    second.record(make_context(), make_result())

    assert (tmp_path / "a/replays/g00001.json.gz").read_bytes() == (
        tmp_path / "b/replays/g00001.json.gz"
    ).read_bytes()


def test_compare_study_agents_records_every_game(tmp_path: Path) -> None:
    spec = validate_spec(json.loads(SPEC_PATH.read_text(encoding="utf-8")))
    manifest = load_manifest(MANIFEST_PATH)
    recorder = GameRecorder(tmp_path, {})

    def fake_battle(*args: Any, **kwargs: Any) -> EvaluationBattleResult:
        return make_result(
            winner=kwargs["candidate_agent"].name, replay={"log": [], "decisions": []}
        )

    with patch("vgc_rulebreak.evaluation.run_evaluation_battle", side_effect=fake_battle):
        compare_study_agents(spec=spec, manifest=manifest, quick=True, recorder=recorder)

    stages = [g["stage"] for g in recorder.games]
    assert stages.count("benchmark") == 12  # 3 agents, 2 variants, one mirrored pair
    assert stages.count("head-to-head") == 6  # 3 pairings, one mirrored pair
    assert len(list((tmp_path / "replays").iterdir())) == 18
    first, second = recorder.games[0], recorder.games[1]
    assert (first["candidate_role"], second["candidate_role"]) == ("p1", "p2")
    assert first["candidate_team"] == second["opponent_team"]


def test_cli_compare_agents_output_dir(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    report = AgentComparisonReport(
        eval_seed=101,
        baseline_opponent="RandomBaseline",
        pairs_per_matchup=1,
        quick=True,
        entries=(),
        head_to_head=(),
        findings={},
    )
    out = tmp_path / "run"
    with patch("vgc_rulebreak.evaluation.compare_study_agents", return_value=report) as fake:
        code = main(["compare-agents", "--quick", "--output-dir", str(out)])

    assert code == 0
    assert isinstance(fake.call_args.kwargs["recorder"], GameRecorder)
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert results["command"] == "compare-agents"
    assert results["simulator_revision"] == "9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e"
    assert results["options"]["quick"] is True
    assert results["summary"]["eval_seed"] == 101
    assert "Wrote 0 games" in capsys.readouterr().err
