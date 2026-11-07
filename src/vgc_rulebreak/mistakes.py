"""Opportunity-normalized review flags, not evidence of harmful decisions."""

from typing import Any

from vgc_rulebreak.agents.base import get_active_unfainted_slots, get_legal_slot_choices

DETECTOR = "consecutive_protect"
DETECTOR_VERSION = 1


def _chooses_protect(action: str, moves: list[dict[str, Any]]) -> bool:
    parts = action.split()
    if len(parts) < 2 or parts[0] != "move":
        return False
    try:
        index = int(parts[1]) - 1
    except ValueError:
        return False
    return (
        0 <= index < len(moves)
        and moves[index].get("id") == "protect"
        and moves[index].get("pp", 0) > 0
        and not moves[index].get("disabled", False)
    )


def candidate_mistakes(
    decisions: list[dict[str, Any]], candidate_role: str
) -> dict[str, Any] | None:
    """Flag repeated Protect choices per eligible active-slot decision.

    An eligible slot has legal Protect and an alternative, and the same Pokémon
    chose Protect in that slot on the immediately preceding turn. This describes
    choices, including choices prevented by sleep or other effects, not successful
    executions or estimated decision costs. Missing request evidence is unknown.
    """
    previous: dict[int, tuple[int, str]] = {}
    opportunities = 0
    evidence: list[dict[str, int]] = []
    for decision_index, decision in enumerate(decisions):
        if decision["side"] != candidate_role:
            continue
        request = decision.get("request")
        if request is None:
            return None
        if request.get("wait"):
            continue
        if request.get("teamPreview"):
            previous.clear()
            continue
        forced = request.get("forceSwitch", [])
        if any(forced):
            for slot, must_switch in enumerate(forced):
                if must_switch:
                    previous.pop(slot, None)
            continue
        if "active" not in request:
            return None

        turn = decision["turn"]
        actions = [action.strip() for action in decision["choice"].split(",")]
        pokemon = request.get("side", {}).get("pokemon", [])
        next_previous: dict[int, tuple[int, str]] = {}
        for slot, active in get_active_unfainted_slots(request):
            if slot >= len(pokemon) or not pokemon[slot].get("ident") or slot >= len(actions):
                return None
            ident = pokemon[slot]["ident"]
            moves = active.get("moves", [])
            legal = get_legal_slot_choices(active, pokemon, slot)
            eligible = (
                previous.get(slot) == (turn - 1, ident)
                and any(_chooses_protect(action, moves) for action in legal)
                and any(not _chooses_protect(action, moves) for action in legal)
            )
            chose_protect = _chooses_protect(actions[slot], moves)
            if eligible:
                opportunities += 1
                if chose_protect:
                    evidence.append({"decision_index": decision_index, "turn": turn, "slot": slot})
            if chose_protect:
                next_previous[slot] = (turn, ident)
        previous = next_previous

    events = len(evidence)
    return {
        DETECTOR: {
            "detector_version": DETECTOR_VERSION,
            "events": events,
            "eligible_opportunities": opportunities,
            "rate": events / opportunities if opportunities else None,
            "evidence": evidence,
        }
    }
