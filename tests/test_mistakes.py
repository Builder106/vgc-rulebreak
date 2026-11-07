"""Synthetic request/choice fixtures for candidate mistake opportunity counts."""

from copy import deepcopy
from typing import Any

import pytest

from vgc_rulebreak.mistakes import DETECTOR, candidate_mistakes


def decision(turn: int, choice: str = "move 1, move 2", side: str = "p1") -> dict[str, Any]:
    return {
        "turn": turn,
        "side": side,
        "choice": choice,
        "request": {
            "active": [
                {
                    "moves": [
                        {"id": "protect", "pp": 8, "target": "self"},
                        {"id": "tackle", "pp": 35, "target": "normal"},
                    ]
                }
                for _ in range(2)
            ],
            "side": {
                "pokemon": [
                    {"ident": f"{side}: {name}", "condition": "100/100", "active": True}
                    for name in ("Annihilape", "Incineroar")
                ]
            },
        },
    }


def test_counts_per_slot_and_filters_candidate_side() -> None:
    decisions = [
        decision(1, "move 1, move 1"),
        decision(1, "move 1, move 1", "p2"),
        decision(2, "move 1 mega, move 2 1"),
        decision(2, "move 1, move 1", "p2"),
        decision(3, "move 2 1, move 2 1"),
    ]
    result = candidate_mistakes(decisions, "p1")
    assert result is not None
    assert result[DETECTOR] == {
        "detector_version": 1,
        "events": 1,
        "eligible_opportunities": 3,
        "rate": 1 / 3,
        "evidence": [{"decision_index": 2, "turn": 2, "slot": 0}],
    }
    opponent = candidate_mistakes(decisions, "p2")
    assert opponent is not None
    assert opponent[DETECTOR]["events"] == 2
    assert opponent[DETECTOR]["eligible_opportunities"] == 2


@pytest.mark.parametrize(
    "case",
    [
        "disabled",
        "depleted",
        "fainted",
        "replacement",
        "gap",
        "detect",
        "no_alternative",
        "null_slot",
    ],
)
def test_ineligible_slots_do_not_inflate_denominator(case: str) -> None:
    first, second = decision(1), decision(2)
    active = second["request"]["active"][0]
    if case == "disabled":
        active["moves"][0]["disabled"] = True
    elif case == "depleted":
        active["moves"][0]["pp"] = 0
    elif case == "fainted":
        second["request"]["side"]["pokemon"][0]["condition"] = "0 fnt"
    elif case == "replacement":
        second["request"]["side"]["pokemon"][0]["ident"] = "p1: Rillaboom"
    elif case == "gap":
        second["turn"] = 3
    elif case == "detect":
        first["request"]["active"][0]["moves"][0]["id"] = "detect"
    elif case == "no_alternative":
        active["moves"][1]["disabled"] = True
    elif case == "null_slot":
        second["request"]["active"][0] = None
    result = candidate_mistakes([first, second], "p1")
    assert result is not None
    assert result[DETECTOR]["events"] == 0
    assert result[DETECTOR]["eligible_opportunities"] == 0
    assert result[DETECTOR]["rate"] is None


def test_switching_is_an_alternative_unless_trapped() -> None:
    first, second = decision(1), decision(2)
    second["request"]["active"][0]["moves"][1]["disabled"] = True
    second["request"]["side"]["pokemon"].append(
        {"ident": "p1: Rillaboom", "condition": "100/100", "active": False}
    )
    result = candidate_mistakes([first, second], "p1")
    assert result is not None
    assert result[DETECTOR]["eligible_opportunities"] == 1
    second["request"]["active"][0]["trapped"] = True
    result = candidate_mistakes([first, second], "p1")
    assert result is not None
    assert result[DETECTOR]["eligible_opportunities"] == 0


def test_forced_switch_only_clears_affected_slot_and_wait_does_not_count() -> None:
    forced = decision(1, "switch 3, pass")
    forced["request"]["forceSwitch"] = [True, False]
    waiting = decision(1)
    waiting["request"]["wait"] = True
    result = candidate_mistakes(
        [decision(1, "move 1, move 1"), waiting, forced, decision(2, "move 1, move 1")],
        "p1",
    )
    assert result is not None
    assert result[DETECTOR]["eligible_opportunities"] == 1
    assert result[DETECTOR]["evidence"] == [{"decision_index": 3, "turn": 2, "slot": 1}]


def test_preview_and_non_protect_choices_reset_history() -> None:
    preview = decision(0, "team 12")
    preview["request"] = {"teamPreview": True}
    result = candidate_mistakes(
        [preview, decision(1), decision(2, "move 2 1, move 2 1"), decision(3)], "p1"
    )
    assert result is not None
    assert result[DETECTOR]["eligible_opportunities"] == 1
    assert result[DETECTOR]["events"] == 0
    assert result[DETECTOR]["rate"] == 0.0


@pytest.mark.parametrize("missing", ["request", "identity", "choice_slot", "active"])
def test_incomplete_evidence_is_unknown(missing: str) -> None:
    partial = decision(2)
    if missing == "request":
        del partial["request"]
    elif missing == "identity":
        del partial["request"]["side"]["pokemon"][0]["ident"]
    elif missing == "active":
        del partial["request"]["active"]
    else:
        partial["choice"] = "move 1"
    assert candidate_mistakes([decision(1), partial], "p1") is None


def test_deterministic_analysis_does_not_mutate_replay() -> None:
    decisions = [decision(1), decision(2)]
    original = deepcopy(decisions)
    assert candidate_mistakes(decisions, "p1") == candidate_mistakes(decisions, "p1")
    assert decisions == original
    assert candidate_mistakes([], "p1") == {
        DETECTOR: {
            "detector_version": 1,
            "events": 0,
            "eligible_opportunities": 0,
            "rate": None,
            "evidence": [],
        }
    }
