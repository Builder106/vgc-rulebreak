"""Competent heuristic baseline agent for Showdown doubles battles."""

from typing import Any

from vgc_rulebreak.agents.base import (
    BattleAgent,
    get_active_unfainted_slots,
    get_available_switch_indices,
    get_legal_slot_choices,
)

# Standard Gen 9 type effectiveness table: (attack_type, defend_type) -> multiplier
TYPE_CHART: dict[tuple[str, str], float] = {
    # Normal
    ("normal", "rock"): 0.5,
    ("normal", "ghost"): 0.0,
    ("normal", "steel"): 0.5,
    # Fire
    ("fire", "fire"): 0.5,
    ("fire", "water"): 0.5,
    ("fire", "grass"): 2.0,
    ("fire", "ice"): 2.0,
    ("fire", "bug"): 2.0,
    ("fire", "rock"): 0.5,
    ("fire", "dragon"): 0.5,
    ("fire", "steel"): 2.0,
    # Water
    ("water", "fire"): 2.0,
    ("water", "water"): 0.5,
    ("water", "grass"): 0.5,
    ("water", "ground"): 2.0,
    ("water", "rock"): 2.0,
    ("water", "dragon"): 0.5,
    # Grass
    ("grass", "fire"): 0.5,
    ("grass", "water"): 2.0,
    ("grass", "grass"): 0.5,
    ("grass", "poison"): 0.5,
    ("grass", "ground"): 2.0,
    ("grass", "flying"): 0.5,
    ("grass", "bug"): 0.5,
    ("grass", "rock"): 2.0,
    ("grass", "dragon"): 0.5,
    ("grass", "steel"): 0.5,
    # Electric
    ("electric", "water"): 2.0,
    ("electric", "electric"): 0.5,
    ("electric", "grass"): 0.5,
    ("electric", "ground"): 0.0,
    ("electric", "flying"): 2.0,
    ("electric", "dragon"): 0.5,
    # Ice
    ("ice", "fire"): 0.5,
    ("ice", "water"): 0.5,
    ("ice", "grass"): 2.0,
    ("ice", "ice"): 0.5,
    ("ice", "ground"): 2.0,
    ("ice", "flying"): 2.0,
    ("ice", "dragon"): 2.0,
    ("ice", "steel"): 0.5,
    # Fighting
    ("fighting", "normal"): 2.0,
    ("fighting", "ice"): 2.0,
    ("fighting", "poison"): 0.5,
    ("fighting", "flying"): 0.5,
    ("fighting", "psychic"): 0.5,
    ("fighting", "bug"): 0.5,
    ("fighting", "rock"): 2.0,
    ("fighting", "ghost"): 0.0,
    ("fighting", "dark"): 2.0,
    ("fighting", "steel"): 2.0,
    ("fighting", "fairy"): 0.5,
    # Poison
    ("poison", "grass"): 2.0,
    ("poison", "poison"): 0.5,
    ("poison", "ground"): 0.5,
    ("poison", "rock"): 0.5,
    ("poison", "ghost"): 0.5,
    ("poison", "steel"): 0.0,
    ("poison", "fairy"): 2.0,
    # Ground
    ("ground", "fire"): 2.0,
    ("ground", "electric"): 2.0,
    ("ground", "grass"): 0.5,
    ("ground", "poison"): 2.0,
    ("ground", "flying"): 0.0,
    ("ground", "bug"): 0.5,
    ("ground", "rock"): 2.0,
    ("ground", "steel"): 2.0,
    # Flying
    ("flying", "electric"): 0.5,
    ("flying", "grass"): 2.0,
    ("flying", "fighting"): 2.0,
    ("flying", "bug"): 2.0,
    ("flying", "rock"): 0.5,
    ("flying", "steel"): 0.5,
    # Psychic
    ("psychic", "fighting"): 2.0,
    ("psychic", "poison"): 2.0,
    ("psychic", "psychic"): 0.5,
    ("psychic", "dark"): 0.0,
    ("psychic", "steel"): 0.5,
    # Bug
    ("bug", "fire"): 0.5,
    ("bug", "grass"): 2.0,
    ("bug", "fighting"): 0.5,
    ("bug", "poison"): 0.5,
    ("bug", "flying"): 0.5,
    ("bug", "psychic"): 2.0,
    ("bug", "ghost"): 0.5,
    ("bug", "dark"): 2.0,
    ("bug", "steel"): 0.5,
    ("bug", "fairy"): 0.5,
    # Rock
    ("rock", "fire"): 2.0,
    ("rock", "ice"): 2.0,
    ("rock", "fighting"): 0.5,
    ("rock", "ground"): 0.5,
    ("rock", "flying"): 2.0,
    ("rock", "bug"): 2.0,
    ("rock", "steel"): 0.5,
    # Ghost
    ("ghost", "normal"): 0.0,
    ("ghost", "psychic"): 2.0,
    ("ghost", "ghost"): 2.0,
    ("ghost", "dark"): 0.5,
    # Dragon
    ("dragon", "dragon"): 2.0,
    ("dragon", "steel"): 0.5,
    ("dragon", "fairy"): 0.0,
    # Steel
    ("steel", "fire"): 0.5,
    ("steel", "water"): 0.5,
    ("steel", "electric"): 0.5,
    ("steel", "ice"): 2.0,
    ("steel", "rock"): 2.0,
    ("steel", "steel"): 0.5,
    ("steel", "fairy"): 2.0,
    # Dark
    ("dark", "fighting"): 0.5,
    ("dark", "psychic"): 2.0,
    ("dark", "ghost"): 2.0,
    ("dark", "dark"): 0.5,
    ("dark", "fairy"): 0.5,
    # Fairy
    ("fairy", "fire"): 0.5,
    ("fairy", "fighting"): 2.0,
    ("fairy", "poison"): 0.5,
    ("fairy", "dragon"): 2.0,
    ("fairy", "dark"): 2.0,
    ("fairy", "steel"): 0.5,
}

# Common STAB moves mapped to species for quick heuristics
SPECIES_STAB_MOVES: dict[str, set[str]] = {
    "fluttermane": {"moonblast", "shadowball", "dazzlinggleam"},
    "tornadus": {"bleakwindstorm"},
    "urshifu": {"surgingstrikes", "closecombat", "aquajet", "wickedblow", "suckerpunch"},
    "urshifurapidstrike": {"surgingstrikes", "closecombat", "aquajet"},
    "rillaboom": {"grassyglide", "woodhammer"},
    "ogerpon": {"ivycudgel", "hornleech"},
    "ogerponwellspring": {"ivycudgel", "hornleech"},
    "chienpao": {"iciclecrash", "suckerpunch", "sacredsword"},
    "annihilape": {"ragefist", "drainpunch", "closecombat"},
    "torkoal": {"eruption", "heatwave", "solarbeam"},
    "chiyu": {"heatwave", "darkpulse", "overheat", "snarl"},
    "farigiraf": {"hypervoice", "psychic"},
}
MOVE_POWER: dict[str, int] = {
    "tackle": 40,
    "moonblast": 95,
    "shadowball": 80,
    "dazzlinggleam": 80,
    "surgingstrikes": 105,
    "wickedblow": 115,
    "bleakwindstorm": 80,
    "closecombat": 120,
    "aquajet": 40,
    "uturn": 70,
    "grassyglide": 55,
    "woodhammer": 120,
    "highhorsepower": 95,
    "ivycudgel": 100,
    "hornleech": 75,
    "iciclecrash": 85,
    "suckerpunch": 70,
    "sacredsword": 90,
    "eruption": 150,
    "heatwave": 95,
    "solarbeam": 120,
    "darkpulse": 80,
    "overheat": 130,
    "snarl": 55,
    "bloodmoon": 140,
    "earthpower": 90,
    "hypervoice": 90,
    "fakeout": 40,
    "knockoff": 65,
    "flareblitz": 120,
    "ragefist": 50,
    "drainpunch": 75,
    "kowtowcleave": 85,
    "ironhead": 80,
    "weatherball": 100,
    "hurricane": 110,
    "electroshot": 130,
    "flashcannon": 80,
    "dracometeor": 130,
    "bodypress": 80,
    "thunderbolt": 90,
    "stompingtantrum": 75,
    "rockslide": 75,
}


class HeuristicAgent(BattleAgent):
    """Competent heuristic agent prioritizing high-yield STAB/super-effective moves and Protect."""

    def __init__(self, name: str = "HeuristicPlayer") -> None:
        super().__init__(name)
        # Track whether Protect/Spiky Shield/Detect was used in the previous turn per slot
        self._used_protect_last_turn: dict[int, bool] = {0: False, 1: False}
        self._turns_active: dict[int, int] = {0: 0, 1: 0}
        self._tailwind_turns_left: int = 0

    def reset(self) -> None:
        self._used_protect_last_turn = {0: False, 1: False}
        self._turns_active = {0: 0, 1: 0}
        self._tailwind_turns_left = 0

    def score_protect(
        self,
        move_info: dict[str, Any],
        slot_idx: int,
        hp_ratio: float,
    ) -> float:
        """Score a Protect-like move (Protect, Detect, Spiky Shield)."""
        if self._used_protect_last_turn.get(slot_idx, False):
            return 0.0
        if hp_ratio < 0.35:
            return 95.0
        return 50.0

    def choose_action(self, request: dict[str, Any]) -> str:
        # 1. Handle team preview: order by speed and offensive presence
        if request.get("teamPreview"):
            pokemon_list = request.get("side", {}).get("pokemon", [])
            if pokemon_list:

                def lead_score(p: dict[str, Any]) -> float:
                    stats = p.get("stats", {})
                    spe = float(stats.get("spe", 100))
                    spa = float(stats.get("spa", 100))
                    atk = float(stats.get("atk", 100))
                    return spe * 1.5 + max(spa, atk)

                indexed = list(enumerate(pokemon_list, start=1))
                indexed.sort(key=lambda item: lead_score(item[1]), reverse=True)
                order = "".join(str(idx) for idx, _ in indexed)
                return f"team {order}"
            return "team 123456"

        pokemon_list = request.get("side", {}).get("pokemon", [])

        # 2. Handle force switch (fainted replacement)
        force_switch = request.get("forceSwitch")
        if force_switch:
            available = get_available_switch_indices(pokemon_list)
            slot_choices: list[str] = []
            for must_switch in force_switch:
                if must_switch and available:
                    chosen = available.pop(0)
                    slot_choices.append(f"switch {chosen}")
                else:
                    slot_choices.append("pass")
            return ", ".join(slot_choices)

        # 3. Regular active turn
        unfainted_slots = get_active_unfainted_slots(request)
        if not unfainted_slots:
            return "default"

        chosen_actions: list[str] = []
        claimed_switches: set[int] = set()

        for slot_idx, slot_data in unfainted_slots:
            legal_choices = get_legal_slot_choices(slot_data, pokemon_list, slot_idx=slot_idx)
            moves = slot_data.get("moves", [])

            # Species and HP ratio for current slot
            species_key = ""
            hp_ratio = 1.0
            if slot_idx < len(pokemon_list):
                raw_ident = pokemon_list[slot_idx].get("ident", "")
                species_key = raw_ident.split(":")[-1].replace(" ", "").replace("-", "").lower()
                cond = pokemon_list[slot_idx].get("condition", "100/100")
                if "/" in cond:
                    try:
                        cur_hp, max_hp = map(float, cond.split()[0].split("/"))
                        hp_ratio = cur_hp / max(max_hp, 1.0)
                    except Exception:
                        hp_ratio = 1.0

            best_choice = legal_choices[0] if legal_choices else "move 1"
            best_score = -1.0

            for choice in legal_choices:
                if choice.startswith("switch "):
                    sw_idx = int(choice.split()[1])
                    if sw_idx in claimed_switches:
                        continue
                    # Low baseline score for manual switching unless forced
                    score = 10.0
                else:
                    # Move choice
                    parts = choice.split()
                    m_idx = int(parts[1]) - 1
                    move_info = moves[m_idx] if m_idx < len(moves) else {}
                    move_id = move_info.get("id", "")

                    if move_id in {"protect", "spikyshield", "detect"}:
                        score = self.score_protect(move_info, slot_idx, hp_ratio)
                    elif move_id == "tailwind":
                        # Tailwind setup is high priority on turn 1
                        score = 0.0 if self._tailwind_turns_left > 0 else 140.0
                    elif move_id == "fakeout":
                        score = 90.0 if self._turns_active.get(slot_idx, 0) == 0 else 0.0
                    elif move_id == "spore":
                        score = 110.0
                    elif move_id == "helpinghand":
                        score = 70.0
                    elif move_id in {"eruption", "waterspout"}:
                        score = float(int(150 * hp_ratio))
                        if move_id in SPECIES_STAB_MOVES.get(species_key, set()):
                            score *= 1.5
                        score *= 1.35
                    else:
                        base_power = MOVE_POWER.get(move_id, 65)
                        score = float(base_power)
                        # Apply STAB multiplier if move matches species STAB set
                        if move_id in SPECIES_STAB_MOVES.get(species_key, set()):
                            score *= 1.5
                        # Spread move multiplier (hits both foes)
                        target = move_info.get("target", "")
                        if target in {"allAdjacentFoes", "allAdjacent", "all"}:
                            score *= 1.35
                        # Target slot preference to split focus across foes
                        if len(parts) > 2:
                            target_slot = int(parts[2])
                            if target_slot > 0:
                                preferred_target = 2 if slot_idx == 0 else 1
                                if target_slot == preferred_target:
                                    score += 5.0

                if score > best_score:
                    best_score = score
                    best_choice = choice

            if best_choice.startswith("switch "):
                claimed_switches.add(int(best_choice.split()[1]))
                self._used_protect_last_turn[slot_idx] = False
                self._turns_active[slot_idx] = 0
            else:
                parts = best_choice.split()
                m_idx = int(parts[1]) - 1
                move_info = moves[m_idx] if m_idx < len(moves) else {}
                move_id = move_info.get("id", "")
                if move_id == "tailwind":
                    self._tailwind_turns_left = 4
                self._used_protect_last_turn[slot_idx] = move_id in {
                    "protect",
                    "spikyshield",
                    "detect",
                }
                self._turns_active[slot_idx] = self._turns_active.get(slot_idx, 0) + 1

            chosen_actions.append(best_choice)

        if self._tailwind_turns_left > 0:
            self._tailwind_turns_left -= 1

        return ", ".join(chosen_actions)
