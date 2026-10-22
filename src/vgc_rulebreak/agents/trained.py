"""A heuristic agent whose Protect scoring comes from trainable parameters."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vgc_rulebreak.agents.heuristic import HeuristicAgent

# Search bounds for each parameter. Move scores elsewhere in the heuristic run from
# about 40 to 200, so Protect scores in this range can win or lose against attacks.
PARAM_BOUNDS: dict[str, tuple[float, float]] = {
    "base_score": (0.0, 150.0),
    "low_hp_score": (0.0, 200.0),
    "hp_threshold": (0.0, 1.0),
    "scarcity_slope": (0.0, 40.0),
    "pp_cushion": (0.0, 16.0),
}


@dataclass(frozen=True)
class ProtectParams:
    """How much the agent wants Protect.

    The score is `low_hp_score` below `hp_threshold` and `base_score` otherwise. Each
    PP below `pp_cushion` lowers it by `scarcity_slope`.
    """

    base_score: float
    low_hp_score: float
    hp_threshold: float
    scarcity_slope: float
    pp_cushion: float

    def score(self, pp: int, hp_ratio: float) -> float:
        score = self.low_hp_score if hp_ratio < self.hp_threshold else self.base_score
        score -= self.scarcity_slope * max(0.0, self.pp_cushion - pp)
        return max(score, 0.0)

    def to_unit(self) -> list[float]:
        """Map each parameter into [0, 1] using PARAM_BOUNDS, in field order."""
        values = asdict(self)
        return [(values[name] - lo) / (hi - lo) for name, (lo, hi) in PARAM_BOUNDS.items()]

    @classmethod
    def from_unit(cls, unit: list[float]) -> "ProtectParams":
        """Inverse of to_unit. Values outside [0, 1] are clipped to the bounds."""
        values = {}
        for (name, (lo, hi)), u in zip(PARAM_BOUNDS.items(), unit, strict=True):
            values[name] = lo + min(max(u, 0.0), 1.0) * (hi - lo)
        return cls(**values)


# The heuristic baseline's own Protect scoring, expressed as parameters.
HEURISTIC_PARAMS = ProtectParams(
    base_score=50.0, low_hp_score=95.0, hp_threshold=0.35, scarcity_slope=0.0, pp_cushion=0.0
)


class TrainedProtectAgent(HeuristicAgent):
    """Heuristic agent that scores Protect with trained parameters."""

    def __init__(self, params: ProtectParams, name: str = "TrainedProtectAgent") -> None:
        super().__init__(name)
        self.params = params

    def score_protect(
        self,
        move_info: dict[str, Any],
        slot_idx: int,
        hp_ratio: float,
    ) -> float:
        if self._used_protect_last_turn.get(slot_idx, False):
            return 0.0
        return self.params.score(int(move_info.get("pp", 0)), hp_ratio)


def load_checkpoint(path: Path) -> tuple[ProtectParams, dict[str, Any]]:
    """Read a training checkpoint and return its parameters and metadata."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProtectParams(**data["params"]), data


def checkpoint_agent(path: Path) -> TrainedProtectAgent:
    """Build an agent from a checkpoint, named after its agent, seed, and generation."""
    params, meta = load_checkpoint(path)
    name = f"{meta['agent']}-s{meta['training_seed']}-g{meta['generation']:02d}"
    return TrainedProtectAgent(params, name=name)
