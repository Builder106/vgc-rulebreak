"""Study agents for the Protect PP transfer experiment: Source, Adapted, and Target-Native."""

from typing import Any

from vgc_rulebreak.agents.heuristic import HeuristicAgent


class SourceAgent(HeuristicAgent):
    """Source policy calibrated in standard Gen 9 rules (16 Protect PP).

    In 16 PP doubles, Protect is virtually inexhaustible across a typical 7-12
    turn battle. The agent uses Protect liberally to scout, stall, and preserve
    positioning without any PP scarcity penalty.
    """

    def __init__(self, name: str = "SourceAgent") -> None:
        super().__init__(name)

    def score_protect(
        self,
        move_info: dict[str, Any],
        slot_idx: int,
        hp_ratio: float,
    ) -> float:
        """Score Protect liberally without PP awareness."""
        if self._used_protect_last_turn.get(slot_idx, False):
            return 0.0
        if hp_ratio < 0.45:
            return 95.0
        return 55.0


class NativeAgent(HeuristicAgent):
    """Target-native policy calibrated directly under Champions rules (8 Protect PP).

    Internalizes Protect PP scarcity from the start: scales Protect utility with
    remaining PP, reserving Protect strictly for high-yield or lethal incoming threats,
    and avoiding non-essential pacing stalls.
    """

    def __init__(self, name: str = "NativeAgent") -> None:
        super().__init__(name)

    def score_protect(
        self,
        move_info: dict[str, Any],
        slot_idx: int,
        hp_ratio: float,
    ) -> float:
        """Score Protect conservatively based on remaining PP and board preservation."""
        if self._used_protect_last_turn.get(slot_idx, False):
            return 0.0

        pp = int(move_info.get("pp", 8))

        if pp <= 1:
            return 110.0 if hp_ratio < 0.20 else 10.0
        elif pp <= 3:
            return 90.0 if hp_ratio < 0.30 else 25.0
        elif pp <= 5:
            return 85.0 if hp_ratio < 0.35 else 35.0
        else:
            return 90.0 if hp_ratio < 0.35 else 45.0


class AdaptedAgent(HeuristicAgent):
    """Adapted policy fine-tuned from source checkpoint under Champions rules.

    Interpolates between the source habit and the native conservation policy
    as a function of adaptation progress (0.0 = source, 1.0 = fully adapted).
    """

    def __init__(
        self,
        name: str = "AdaptedAgent",
        adaptation_progress: float = 1.0,
    ) -> None:
        super().__init__(name)
        if not (0.0 <= adaptation_progress <= 1.0):
            raise ValueError("adaptation_progress must be between 0.0 and 1.0")
        self.adaptation_progress = adaptation_progress

    def score_protect(
        self,
        move_info: dict[str, Any],
        slot_idx: int,
        hp_ratio: float,
    ) -> float:
        """Interpolate between source and native Protect scoring."""
        if self._used_protect_last_turn.get(slot_idx, False):
            return 0.0

        source_score = 95.0 if hp_ratio < 0.45 else 55.0

        pp = int(move_info.get("pp", 8))
        if pp <= 1:
            native_score = 110.0 if hp_ratio < 0.20 else 10.0
        elif pp <= 3:
            native_score = 90.0 if hp_ratio < 0.30 else 25.0
        elif pp <= 5:
            native_score = 85.0 if hp_ratio < 0.35 else 35.0
        else:
            native_score = 90.0 if hp_ratio < 0.35 else 45.0

        alpha = self.adaptation_progress
        return (1.0 - alpha) * source_score + alpha * native_score

