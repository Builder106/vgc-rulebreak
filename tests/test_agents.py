from vgc_rulebreak.agents.base import get_available_switch_indices, get_legal_slot_choices
from vgc_rulebreak.agents.heuristic import HeuristicAgent
from vgc_rulebreak.agents.random import RandomAgent


def test_get_available_switch_indices() -> None:
    pokemon = [
        {"active": True, "condition": "100/100"},
        {"active": True, "condition": "100/100"},
        {"active": False, "condition": "0 fnt"},
        {"active": False, "condition": "100/100"},
    ]
    switches = get_available_switch_indices(pokemon)
    assert switches == [4]


def test_get_legal_slot_choices() -> None:
    slot_active = {
        "moves": [
            {"move": "Tackle", "id": "tackle", "pp": 10, "disabled": False, "target": "normal"},
            {"move": "Protect", "id": "protect", "pp": 10, "disabled": False, "target": "self"},
            {"move": "Exhausted", "id": "ex", "pp": 0, "disabled": False, "target": "normal"},
            {"move": "Disabled", "id": "dis", "pp": 10, "disabled": True, "target": "normal"},
        ]
    }
    pokemon = [
        {"active": True, "condition": "100/100"},
        {"active": False, "condition": "100/100"},
    ]
    choices = get_legal_slot_choices(slot_active, pokemon, foe_count=2)
    assert "move 1 1" in choices
    assert "move 1 2" in choices
    assert "move 2" in choices
    assert "switch 2" in choices
    # Exhausted and disabled moves should not be in choices
    assert not any("move 3" in c for c in choices)
    assert not any("move 4" in c for c in choices)


def test_get_legal_slot_choices_adjacent_ally() -> None:
    slot_active = {
        "moves": [
            {
                "move": "Helping Hand",
                "id": "helpinghand",
                "pp": 20,
                "disabled": False,
                "target": "adjacentAlly",
            },
            {
                "move": "Pollen Puff",
                "id": "pollenpuff",
                "pp": 15,
                "disabled": False,
                "target": "adjacentAllyOrSelf",
            },
        ]
    }
    # Partner (slot 1) is alive
    pokemon_alive = [
        {"active": True, "condition": "100/100"},
        {"active": True, "condition": "100/100"},
    ]
    choices_alive = get_legal_slot_choices(slot_active, pokemon_alive, slot_idx=0)
    assert "move 1 -2" in choices_alive
    assert "move 2 -2" in choices_alive
    assert "move 2 -1" in choices_alive

    # Partner (slot 1) is fainted
    pokemon_fainted = [
        {"active": True, "condition": "100/100"},
        {"active": True, "condition": "0 fnt"},
    ]
    choices_fainted = get_legal_slot_choices(slot_active, pokemon_fainted, slot_idx=0)
    assert "move 1 -2" not in choices_fainted
    assert "move 2 -1" in choices_fainted


def test_random_agent_team_preview() -> None:
    agent = RandomAgent("RandomTest", seed=1)
    req = {"teamPreview": True}
    assert agent.choose_action(req) == "team 123456"


def test_heuristic_agent_avoids_consecutive_protect() -> None:
    agent = HeuristicAgent("HeuristicTest")
    req = {
        "active": [
            {
                "moves": [
                    {
                        "move": "Protect",
                        "id": "protect",
                        "pp": 10,
                        "disabled": False,
                        "target": "self",
                    },
                    {
                        "move": "Tackle",
                        "id": "tackle",
                        "pp": 10,
                        "disabled": False,
                        "target": "normal",
                    },
                ]
            }
        ],
        "side": {"pokemon": [{"active": True, "condition": "100/100"}]},
    }
    # First turn: Protect has defensive value (score 50 > Tackle 40)
    choice1 = agent.choose_action(req)
    assert choice1 == "move 1"

    # Second turn: Consecutive Protect penalty kicks in (score 0 < Tackle 40), so Tackle is chosen
    choice2 = agent.choose_action(req)
    assert choice2.startswith("move 2")


def test_get_legal_slot_choices_trapped() -> None:
    slot_active = {
        "trapped": True,
        "moves": [
            {"move": "Tackle", "id": "tackle", "pp": 10, "disabled": False, "target": "normal"}
        ],
    }
    pokemon = [
        {"active": True, "condition": "100/100"},
        {"active": False, "condition": "100/100"},
    ]
    choices = get_legal_slot_choices(slot_active, pokemon)
    assert "move 1 1" in choices
    # Trapped slot must not emit switch choices
    assert not any(c.startswith("switch ") for c in choices)
