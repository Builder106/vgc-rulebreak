"""Base Agent interface and choice resolution utilities for Showdown battles."""

from abc import ABC, abstractmethod
from typing import Any


class BattleAgent(ABC):
    """Abstract base class for agents playing Showdown doubles battles."""

    def __init__(self, name: str) -> None:
        self.name = name

    @abstractmethod
    def reset(self) -> None:
        """Reset internal agent memory/state between battles."""
        ...

    @abstractmethod
    def choose_action(self, request: dict[str, Any]) -> str:
        """Given a Showdown request payload, return a valid action string."""
        ...


def get_active_unfainted_slots(
    request: dict[str, Any],
) -> list[tuple[int, dict[str, Any]]]:
    """Return (slot_index, slot_data) for active slots whose Pokemon are not fainted."""
    active_slots = request.get("active", [])
    pokemon_list = request.get("side", {}).get("pokemon", [])

    unfainted_slots: list[tuple[int, dict[str, Any]]] = []
    for slot_idx, slot_data in enumerate(active_slots):
        if slot_data is None:
            continue
        if slot_idx < len(pokemon_list):
            cond = pokemon_list[slot_idx].get("condition", "")
            if "fnt" in cond or cond.startswith("0/"):
                continue
        unfainted_slots.append((slot_idx, slot_data))

    return unfainted_slots


def get_available_switch_indices(pokemon_list: list[dict[str, Any]]) -> list[int]:
    """Return 1-indexed team slots of non-fainted, non-active bench Pokemon."""
    available: list[int] = []
    for idx, p in enumerate(pokemon_list, start=1):
        is_active = p.get("active", False)
        condition = p.get("condition", "")
        is_fainted = "fnt" in condition or condition.startswith("0/")
        if not is_active and not is_fainted:
            available.append(idx)
    return available


def get_legal_slot_choices(
    slot_active: dict[str, Any],
    pokemon_list: list[dict[str, Any]],
    slot_idx: int = 0,
    foe_count: int = 2,
) -> list[str]:
    """Enumerate legal action choices for a single active slot."""
    choices: list[str] = []
    moves = slot_active.get("moves", [])

    partner_idx = slot_idx ^ 1
    partner_alive = False
    if partner_idx < len(pokemon_list):
        p_cond = pokemon_list[partner_idx].get("condition", "")
        partner_alive = "fnt" not in p_cond and not p_cond.startswith("0/")

    for m_idx, move in enumerate(moves, start=1):
        if move.get("disabled", False):
            continue
        if move.get("pp", 0) <= 0:
            continue

        target = move.get("target", "normal")
        # In doubles:
        # Single foe moves require a positive target index (1 or 2).
        # Ally moves require a negative target index (-1 or -2).
        # Field, side, spread, and self moves do not specify a target index.
        if target in {"normal", "any", "adjacentFoe"}:
            for f in range(1, max(foe_count, 1) + 1):
                choices.append(f"move {m_idx} {f}")
        elif target == "adjacentAlly":
            if partner_alive:
                choices.append(f"move {m_idx} -{partner_idx + 1}")
        elif target == "adjacentAllyOrSelf":
            if partner_alive:
                choices.append(f"move {m_idx} -{partner_idx + 1}")
            choices.append(f"move {m_idx} -{slot_idx + 1}")
        else:
            choices.append(f"move {m_idx}")

    # Also consider legal switches if slot is not trapped
    if not slot_active.get("trapped", False):
        switches = get_available_switch_indices(pokemon_list)
        for sw in switches:
            choices.append(f"switch {sw}")

    if not choices:
        # Fallback if no moves are available (e.g. Struggle)
        choices.append("move 1")

    return choices
