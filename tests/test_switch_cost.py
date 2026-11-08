"""Opportunity denominators, signed paired costs, and live replay branching."""

import copy
import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from vgc_rulebreak.cli import main
from vgc_rulebreak.explanation import RolloutTrialResult, replay_prefix_to_decision
from vgc_rulebreak.simulator.battle import BattleSession
from vgc_rulebreak.simulator.process import ShowdownProcess
from vgc_rulebreak.switch_cost import FORMATS, estimate_switch_costs, switch_opportunities


def decision(choice: str = "switch 3, move 1", side: str = "p1") -> dict[str, Any]:
    return {
        "side": side,
        "turn": 1,
        "choice": choice,
        "request": {
            "active": [
                {"moves": [{"id": "ragefist", "pp": 16, "target": "normal"}]},
                {"moves": [{"id": "splash", "pp": 40, "target": "self"}]},
            ],
            "side": {
                "pokemon": [
                    {
                        "ident": f"{side}: Annihilape",
                        "active": True,
                        "condition": "100/100",
                        "moves": ["ragefist"],
                    },
                    {
                        "ident": f"{side}: Magikarp",
                        "active": True,
                        "condition": "100/100",
                        "moves": ["splash"],
                    },
                    {
                        "ident": f"{side}: Pikachu",
                        "active": False,
                        "condition": "100/100",
                        "moves": ["tackle"],
                    },
                ]
            },
        },
    }


def test_opportunities_include_stays_and_preserve_partner() -> None:
    switches = decision()
    stay = decision("move 1 2, move 1")
    found = switch_opportunities([switches, stay, decision(side="p2")], "p1")
    assert len(found) == 2
    assert [o.chose_switch for o in found] == [True, False]
    assert found[0].stay_choice == "move 1 1, move 1"
    assert found[0].decision_index == 0
    assert found[0].pokemon == "p1: Annihilape"


def test_compact_choice_after_first_slot_faints() -> None:
    d = decision("switch 3")
    req = d["request"]
    req["side"]["pokemon"][0]["condition"] = "0 fnt"
    # An unrelated living slot must not be mistaken for missing choice evidence.
    assert switch_opportunities([d], "p1") == []
    req["side"]["pokemon"][1]["moves"] = ["ragefist"]
    req["active"][1] = req["active"][0]
    (opportunity,) = switch_opportunities([d], "p1")
    assert opportunity.slot == 1
    assert opportunity.chose_switch
    assert opportunity.actual_choice == "switch 3"
    assert opportunity.stay_choice == "pass, move 1 1"


def test_p2_branch_does_not_submit_half_a_simultaneous_step() -> None:
    session = MagicMock(spec=BattleSession)
    session.is_ended = False
    session.p1_request = {"active": []}
    session.p2_request = {"active": []}
    decisions = [decision(), decision(side="p2")]
    assert replay_prefix_to_decision(session, decisions, 1) == 0
    session.step.assert_not_called()


@pytest.mark.parametrize(
    "excluded",
    [
        "trapped",
        "fainted",
        "bench_fainted",
        "reserved",
        "forced",
        "preview",
        "wait",
        "no_rage_fist",
        "no_move",
    ],
)
def test_ineligible_slots(excluded: str) -> None:
    d = decision()
    req = d["request"]
    if excluded == "trapped":
        req["active"][0]["trapped"] = True
    elif excluded == "fainted":
        req["side"]["pokemon"][0]["condition"] = "0 fnt"
    elif excluded == "bench_fainted":
        req["side"]["pokemon"][2]["condition"] = "0 fnt"
    elif excluded == "reserved":
        d["choice"] = "move 1 1, switch 3"
    elif excluded == "no_rage_fist":
        req["side"]["pokemon"][0]["moves"] = ["tackle"]
    elif excluded == "no_move":
        req["active"][0]["moves"][0]["disabled"] = True
    else:
        req[{"forced": "forceSwitch", "preview": "teamPreview", "wait": "wait"}[excluded]] = (
            [True, False] if excluded == "forced" else True
        )
    assert switch_opportunities([d], "p1") == []


def test_missing_evidence_is_not_zero() -> None:
    with pytest.raises(ValueError, match="Missing request"):
        switch_opportunities([{"side": "p1"}], "p1")
    with pytest.raises(ValueError, match="candidate_role"):
        switch_opportunities([], "unknown")
    d = decision("switch 3, switch 3")
    with pytest.raises(ValueError, match="illegal"):
        # Another bench makes the slot eligible but the selected duplicate illegal.
        d["request"]["side"]["pokemon"].append(
            {"ident": "p1: Ditto", "condition": "100/100", "active": False}
        )
        switch_opportunities([d], "p1")


def write_replay(tmp_path: Path, decisions: list[dict[str, Any]], name: str = "game") -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(
        json.dumps(
            {
                "format_id": FORMATS[0],
                "battle_seed": [1, 2, 3, 4],
                "players": {"p1": {"name": "Alice"}, "p2": {"name": "Bob"}},
                "decisions": decisions,
            }
        )
    )
    return path


@pytest.mark.parametrize("switch_points,expected_cost", [(1.0, -1.0), (0.0, 1.0)])
def test_paired_signed_costs_and_pooled_denominators(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, switch_points: float, expected_cost: float
) -> None:
    calls: list[tuple[str, tuple[int, int, int, int], str]] = []

    def rollout(*args: Any, **kwargs: Any) -> RolloutTrialResult:  # noqa: ANN401
        choice, seed, opponent = args[2], args[3], args[5]
        calls.append((choice, seed, opponent.name))
        points = switch_points if choice.startswith("switch") else 1.0 - switch_points
        return RolloutTrialResult(0, seed, opponent.name, choice, None, False, points, 5, False)

    monkeypatch.setattr("vgc_rulebreak.switch_cost.execute_rollout_trial", rollout)
    first = write_replay(tmp_path, [decision()])
    second = write_replay(tmp_path, [decision("move 1 1, move 1")] * 3, "stays")
    report = estimate_switch_costs([first, second], "p1", trials=3)
    for summary in report["summaries"]:
        assert summary["eligible_opportunities"] == 4
        assert summary["switches"] == 1
        assert summary["cost_per_opportunity"] == expected_cost / 4
        assert summary["cost_per_switch"] == expected_cost
        assert summary["costly_switch_rate"] == (0.25 if expected_cost > 0 else 0.0)
    for left, right in zip(calls[::2], calls[1::2], strict=True):
        assert left[1:] == right[1:]
    assert report == estimate_switch_costs([first, second], "p1", trials=3)


def test_zero_denominator_and_cli_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = write_replay(tmp_path, [])
    report = estimate_switch_costs([path], "p1", trials=2)
    assert report["summaries"][0]["cost_per_opportunity"] is None
    assert report["summaries"][0]["cost_per_opportunity_ci_95"] is None
    assert (
        main(
            [
                "estimate-switch-cost",
                "--replay",
                str(path),
                "--candidate-role",
                "p1",
                "--trials",
                "2",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["schema_version"] == 1
    assert (
        main(
            [
                "estimate-switch-cost",
                "--replay",
                str(path),
                "--candidate-role",
                "p1",
                "--trials",
                "1",
            ]
        )
        == 1
    )
    assert "at least two" in capsys.readouterr().err
    with pytest.raises(ValueError, match="Duplicate"):
        estimate_switch_costs([path, path], "p1")
    raw = json.loads(path.read_text())
    raw["format_id"] = "gen9championsdoublescustomgame"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="single-factor"):
        estimate_switch_costs([path], "p1")


@pytest.mark.parametrize("format_id", FORMATS)
@pytest.mark.parametrize("role", ["p1", "p2"])
def test_live_switch_rollouts(tmp_path: Path, format_id: str, role: str) -> None:
    try:
        ShowdownProcess._resolve_showdown_dir(None)
    except FileNotFoundError:
        pytest.skip("Showdown not found")
    team = (
        "Annihilape|||VitalSpirit|RageFist,Protect|Serious||||||"
        "]Magikarp|||SwiftSwim|Splash,Protect|Serious||||||"
        "]Pikachu|||Static|Tackle,Protect|Serious||||||"
    )
    decisions: list[dict[str, Any]] = []
    with ShowdownProcess() as process:
        session = BattleSession(process)
        session.start(format_id, "Alice", team, "Bob", team, seed=(1, 2, 3, 4))
        for choices in [("team 123", "team 123"), ("move 1 1, move 1", "move 1 1, move 1")]:
            for side, request, choice in zip(
                ("p1", "p2"), (session.p1_request, session.p2_request), choices, strict=True
            ):
                decisions.append(
                    {
                        "side": side,
                        "turn": session.turn,
                        "request": copy.deepcopy(request),
                        "choice": choice,
                    }
                )
            session.step(*choices)
        assert session.turn == 2
        for side, request in (("p1", session.p1_request), ("p2", session.p2_request)):
            decisions.append(
                {
                    "side": side,
                    "turn": session.turn,
                    "request": request,
                    "choice": "switch 3, move 1" if side == role else "move 1 1, move 1",
                }
            )
    path = tmp_path / "live.json"
    path.write_text(
        json.dumps(
            {
                "format_id": format_id,
                "battle_seed": [1, 2, 3, 4],
                "players": {
                    "p1": {"name": "Alice", "team": team},
                    "p2": {"name": "Bob", "team": team},
                },
                "decisions": decisions,
            }
        )
    )
    output = tmp_path / "report.json"
    report = estimate_switch_costs([path], role, trials=2, max_turns=5, output_path=output)
    assert len(report["summaries"]) == 2
    assert report["summaries"][0]["eligible_opportunities"] == 2
    assert report["summaries"][0]["switches"] == 1
    assert json.loads(output.read_text())["candidate_role"] == role
