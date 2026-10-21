"""Random baseline agent for Showdown battles."""

import random
from typing import Any

from vgc_rulebreak.agents.base import (
    BattleAgent,
    get_active_unfainted_slots,
    get_available_switch_indices,
    get_legal_slot_choices,
)


class RandomAgent(BattleAgent):
    """Uniform random decision-maker across legal moves and switches."""

    def __init__(self, name: str = "RandomPlayer", seed: int | None = None) -> None:
        super().__init__(name)
        self._rng = random.Random(seed)

    def reset(self) -> None:
        """Reset agent state between battles."""
        pass

    def choose_action(self, request: dict[str, Any]) -> str:
        # 1. Handle team preview
        if request.get("teamPreview"):
            pokemon_list = request.get("side", {}).get("pokemon", [])
            if pokemon_list:
                order = "".join(str(i) for i in range(1, len(pokemon_list) + 1))
                return f"team {order}"
            return "team 123456"

        pokemon_list = request.get("side", {}).get("pokemon", [])

        # 2. Handle force switch (fainted Pokémon replacement)
        force_switch = request.get("forceSwitch")
        if force_switch:
            available = get_available_switch_indices(pokemon_list)
            slot_choices: list[str] = []
            for must_switch in force_switch:
                if must_switch and available:
                    chosen_idx = self._rng.choice(available)
                    available.remove(chosen_idx)
                    slot_choices.append(f"switch {chosen_idx}")
                else:
                    slot_choices.append("pass")
            return ", ".join(slot_choices)

        # 3. Regular active turn
        unfainted_slots = get_active_unfainted_slots(request)
        if not unfainted_slots:
            return "default"

        chosen_actions: list[str] = []
        claimed_switches: set[int] = set()

        for _slot_idx, slot_data in unfainted_slots:
            legal_choices = get_legal_slot_choices(slot_data, pokemon_list, slot_idx=_slot_idx)
            # Filter out switch targets already chosen by the partner slot
            valid = [
                c
                for c in legal_choices
                if not (c.startswith("switch ") and int(c.split()[1]) in claimed_switches)
            ]
            if not valid:
                valid = [c for c in legal_choices if not c.startswith("switch ")] or ["move 1"]

            choice = self._rng.choice(valid)
            if choice.startswith("switch "):
                claimed_switches.add(int(choice.split()[1]))
            chosen_actions.append(choice)

        return ", ".join(chosen_actions)
