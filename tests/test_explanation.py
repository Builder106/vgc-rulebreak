"""Tests for replay explanation with repeated-rollout evidence."""

import gzip
import json
from pathlib import Path
from typing import Any

import pytest

from vgc_rulebreak.agents.base import BattleAgent
from vgc_rulebreak.cli import main
from vgc_rulebreak.explanation import (
    RolloutTrialResult,
    build_explanation_narrative,
    detect_candidate_decision,
    determine_alternatives,
    extract_board_state,
    produce_replay_explanation,
    read_replay_file,
)


def sample_request() -> dict[str, Any]:
    return {
        "active": [
            {
                "moves": [
                    {"move": "Moonblast", "id": "moonblast", "pp": 24, "maxpp": 24},
                    {"move": "Protect", "id": "protect", "pp": 16, "maxpp": 16},
                ]
            },
            {
                "moves": [
                    {"move": "Follow Me", "id": "followme", "pp": 32, "maxpp": 32},
                    {"move": "Protect", "id": "protect", "pp": 8, "maxpp": 8},
                ]
            },
        ],
        "side": {
            "name": "p1",
            "pokemon": [
                {
                    "ident": "p1: Flutter Mane",
                    "details": "Flutter Mane",
                    "condition": "280/280",
                    "active": True,
                    "moves": ["moonblast", "protect"],
                },
                {
                    "ident": "p1: Maushold",
                    "details": "Maushold",
                    "condition": "153/352",
                    "active": True,
                    "moves": ["followme", "protect"],
                },
                {
                    "ident": "p1: Ting-Lu",
                    "details": "Ting-Lu",
                    "condition": "500/500",
                    "active": False,
                    "moves": ["stompingtantrum"],
                },
            ],
        },
    }


def sample_replay() -> dict[str, Any]:
    req = sample_request()
    return {
        "schema_version": 1,
        "game_id": "g00042",
        "format_id": "gen9rulebreakprotect8",
        "battle_seed": [11, 22, 33, 44],
        "players": {
            "p1": {"name": "adapted-s11-g00", "team_id": "team-a", "team": "packed-a"},
            "p2": {"name": "HeuristicBaseline", "team_id": "team-b", "team": "packed-b"},
        },
        "log": [
            "|turn|1",
            "|switch|p2a: Annihilape|Annihilape, M|424/424",
            "|switch|p2b: Urshifu|Urshifu-Rapid-Strike, F|342/342",
            "|turn|2",
        ],
        "decisions": [
            {"turn": 0, "side": "p1", "choice": "team 1234", "request": {"teamPreview": True}},
            {"turn": 0, "side": "p2", "choice": "team 1234", "request": {"teamPreview": True}},
            {"turn": 1, "side": "p1", "choice": "move 1 1, move 1", "request": req},
            {"turn": 1, "side": "p2", "choice": "move 1 1, move 1", "request": req},
            {"turn": 2, "side": "p1", "choice": "move 1 1, move 2", "request": req},
            {"turn": 2, "side": "p2", "choice": "move 1 1, move 1", "request": req},
        ],
    }


def test_read_replay_file_supports_plain_and_gzipped(tmp_path: Path) -> None:
    data = sample_replay()
    plain_path = tmp_path / "replay.json"
    plain_path.write_text(json.dumps(data), encoding="utf-8")
    assert read_replay_file(plain_path)["game_id"] == "g00042"

    gz_path = tmp_path / "replay.json.gz"
    gz_path.write_bytes(gzip.compress(json.dumps(data).encode("utf-8")))
    assert read_replay_file(gz_path)["game_id"] == "g00042"


def test_extract_board_state_identifies_protect_pp_and_active_mons() -> None:
    req = sample_request()
    log = [
        "|switch|p2a: Annihilape|Annihilape, M|424/424",
        "|switch|p2b: Flutter Mane|Flutter Mane|280/280",
    ]
    state = extract_board_state(req, log)

    assert len(state["active_pokemon"]) == 2
    fm = state["active_pokemon"][0]
    assert fm["ident"] == "p1: Flutter Mane"
    assert fm["hp"] == 280
    assert fm["maxhp"] == 280
    assert fm["protect_pp"]["current"] == 16
    assert fm["protect_pp"]["max"] == 16

    maus = state["active_pokemon"][1]
    assert maus["ident"] == "p1: Maushold"
    assert maus["hp"] == 153
    assert maus["maxhp"] == 352
    assert maus["protect_pp"]["current"] == 8
    assert maus["protect_pp"]["max"] == 8

    assert state["protect_pp_summary"]["p1: Flutter Mane"] == {"current": 16, "max": 16}
    assert state["protect_pp_summary"]["p1: Maushold"] == {"current": 8, "max": 8}
    assert state["scarcity_binds_at_decision"] is False
    assert len(state["opponent_active"]) == 2


def test_determine_alternatives_generates_valid_actions() -> None:
    req = sample_request()
    actual_choice = "move 1 1, move 2"  # slot 1 chose move 2 (Protect)
    alts = determine_alternatives(req, actual_choice, target_slot=1)

    assert len(alts) >= 1
    # Check that alternative replaces slot 1 with another move (e.g. Follow Me)
    alt_choices = [c for c, _ in alts]
    assert any(c.startswith("move 1 1, move 1") for c in alt_choices)
    assert all(c != actual_choice for c in alt_choices)


def test_detect_candidate_decision_finds_protect_and_validates_index() -> None:
    replay = sample_replay()
    # Explicit valid index
    idx, dec = detect_candidate_decision(replay, "p1", decision_index=4)
    assert idx == 4
    assert dec["choice"] == "move 1 1, move 2"

    # Out of range index
    with pytest.raises(ValueError, match="out of range"):
        detect_candidate_decision(replay, "p1", decision_index=99)

    # Wrong side
    with pytest.raises(ValueError, match="belongs to p2"):
        detect_candidate_decision(replay, "p1", decision_index=3)

    # Auto-detect Protect choice
    idx_auto, dec_auto = detect_candidate_decision(replay, "p1")
    assert idx_auto == 4
    assert dec_auto["turn"] == 2


def test_build_explanation_narrative_avoids_inferring_internal_beliefs() -> None:
    meta = {
        "game_id": "g00042",
        "candidate": "adapted-s11-g00",
        "format_id": "gen9rulebreakprotect8",
        "turn": 2,
    }
    board = {
        "protect_pp_summary": {
            "p1: Maushold": {"current": 8, "max": 8},
        },
        "scarcity_binds_at_decision": False,
    }
    diffs = [
        {
            "alternative_choice": "move 1 1, move 1",
            "delta_ppg": 0.05,
            "delta_ci_95": {"ci_lower": -0.1, "ci_upper": 0.2},
            "is_statistically_significant": False,
        }
    ]
    narrative = build_explanation_narrative(meta, board, "move 1 1, move 2", [], diffs)

    assert "g00042" in narrative
    assert "8/8 PP remaining" in narrative
    assert "Protect scarcity was not binding" in narrative
    assert "not statistically distinguishable from zero" in narrative
    # Adherence to research protocol: no internal belief words
    forbidden = ["believed", "thought", "hoped", "felt", "intended", "wanted"]
    assert not any(w in narrative.lower() for w in forbidden)


def test_produce_replay_explanation_with_runner_mock(tmp_path: Path) -> None:
    replay = sample_replay()
    replay_file = tmp_path / "replay.json"
    replay_file.write_text(json.dumps(replay), encoding="utf-8")
    out_file = tmp_path / "explanation.json"

    # Mock trial runner returning deterministic results
    def mock_runner(
        replay_data: dict[str, object],
        decision_index: int,
        candidate_choice: str,
        reseed: tuple[int, int, int, int],
        candidate_agent: BattleAgent,
        opponent_agent: BattleAgent,
        candidate_role: str,
        trial_number: int,
        max_turns: int = 60,
        showdown_dir: Path | str | None = None,
    ) -> RolloutTrialResult:
        won = "move 2" in candidate_choice  # Protect choice wins in mock
        return RolloutTrialResult(
            trial=trial_number,
            seed=reseed,
            opponent_policy=opponent_agent.name,
            choice=candidate_choice,
            winner="adapted-s11-g00" if won else "HeuristicBaseline",
            candidate_won=won,
            points=1.0 if won else 0.0,
            turns=8,
            protect_depleted=False,
        )

    explanation = produce_replay_explanation(
        replay_path=replay_file,
        decision_index=4,
        trials_per_action=3,
        opponent_policies=("HeuristicBaseline", "RandomBaseline"),
        runner=mock_runner,
        output_path=out_file,
    )

    assert explanation["schema_version"] == 1
    assert explanation["explanation_id"] == "exp-g00042-t02"
    assert explanation["match"]["game_id"] == "g00042"
    assert explanation["decision"]["actual_choice"] == "move 1 1, move 2"
    assert len(explanation["action_summaries"]) >= 2
    assert len(explanation["outcome_differences"]) >= 1

    actual_summary = next(
        s for s in explanation["action_summaries"] if s["choice"] == "move 1 1, move 2"
    )
    assert actual_summary["win_rate"] == 1.0

    alt_summary = next(
        s for s in explanation["action_summaries"] if s["choice"] != "move 1 1, move 2"
    )
    assert alt_summary["win_rate"] == 0.0

    diff = explanation["outcome_differences"][0]
    assert diff["delta_ppg"] == -1.0
    assert diff["is_statistically_significant"] is True

    # Verify file was written
    assert out_file.exists()
    saved_data = json.loads(out_file.read_text(encoding="utf-8"))
    assert saved_data["explanation_id"] == "exp-g00042-t02"


def test_cli_explain_replay(tmp_path: Path) -> None:
    replay = sample_replay()
    replay_file = tmp_path / "replay.json"
    replay_file.write_text(json.dumps(replay), encoding="utf-8")
    out_file = tmp_path / "cli_explanation.json"

    # Run CLI command with mocked runner via monkeypatch
    import vgc_rulebreak.explanation as expl_mod

    def mock_runner(
        replay_data: dict[str, object],
        decision_index: int,
        candidate_choice: str,
        reseed: tuple[int, int, int, int],
        candidate_agent: BattleAgent,
        opponent_agent: BattleAgent,
        candidate_role: str,
        trial_number: int,
        max_turns: int = 60,
        showdown_dir: Path | str | None = None,
    ) -> RolloutTrialResult:
        return RolloutTrialResult(
            trial=trial_number,
            seed=reseed,
            opponent_policy=opponent_agent.name,
            choice=candidate_choice,
            winner="adapted-s11-g00",
            candidate_won=True,
            points=1.0,
            turns=7,
            protect_depleted=False,
        )

    orig_runner = expl_mod.execute_rollout_trial
    try:
        expl_mod.execute_rollout_trial = mock_runner
        code = main(
            [
                "explain-replay",
                "--replay",
                str(replay_file),
                "--decision-index",
                "4",
                "--trials",
                "2",
                "--output",
                str(out_file),
            ]
        )
        assert code == 0
        assert out_file.exists()
        saved = json.loads(out_file.read_text(encoding="utf-8"))
        assert saved["match"]["game_id"] == "g00042"
    finally:
        expl_mod.execute_rollout_trial = orig_runner


def test_live_showdown_replay_explanation(tmp_path: Path) -> None:
    live_replay = Path("runs/protect-rerun-milestone/eval/adapted-s11-g00/replays/g00007.json.gz")
    if not live_replay.exists():
        pytest.skip("Archived replay runs not present on disk")

    out_file = tmp_path / "live_explanation.json"
    result = produce_replay_explanation(
        replay_path=live_replay,
        decision_index=8,
        alternative_choices=[("move 1 2, move 2", "Follow Me on Maushold (alternative)")],
        trials_per_action=1,
        opponent_policies=("HeuristicBaseline",),
        output_path=out_file,
    )

    assert result["match"]["game_id"] == "g00007"
    assert result["match"]["format_id"] == "gen9rulebreakprotect8"
    assert result["board_state"]["protect_pp_summary"]["p1: Maushold"]["max"] == 8
    assert len(result["action_summaries"]) == 2
    assert len(result["outcome_differences"]) == 1
    assert out_file.exists()
