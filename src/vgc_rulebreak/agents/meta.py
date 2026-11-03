"""Meta-tuned, broadly tuned, and adapted agents for Study A (Anti-meta teams)."""

from typing import TYPE_CHECKING, Any

from vgc_rulebreak.agents.heuristic import HeuristicAgent

if TYPE_CHECKING:
    from vgc_rulebreak.anti_meta import UsageSnapshot

# Default set of top staple sweepers and threats from the Champions ladder
DEFAULT_META_STAPLES: frozenset[str] = frozenset(
    {
        "charizard",
        "floette",
        "archaludon",
        "sneasler",
        "fluttermane",
        "basculegion",
        "incineroar",
        "rillaboom",
        "urshifu",
        "urshifurapidstrike",
    }
)


class BroadlyTunedAgent(HeuristicAgent):
    """Generalist baseline agent without ladder frequency bias.

    Evaluates damage output, active type match-ups, and current board state
    neutrally across all legal species without prioritizing or discounting targets
    based on usage statistics.
    """

    def __init__(self, name: str = "BroadlyTunedAgent") -> None:
        super().__init__(name)

    def score_target_bonus(self, target_species: str, target_slot: int, slot_idx: int) -> float:
        return 0.0


class MetaTunedAgent(HeuristicAgent):
    """Agent tuned on the dominant metagame pool.

    Prioritizes focus-firing high-usage meta staples (e.g. Charizard, Archaludon,
    Sneasler) and discounts off-meta anchors like Hippowdon as passive threats,
    modeling the meta-biased assumption that often costs games against anti-meta teams.
    """

    def __init__(
        self,
        name: str = "MetaTunedAgent",
        snapshot: "UsageSnapshot | None" = None,
        anchor: str = "Hippowdon",
    ) -> None:
        super().__init__(name)
        self.snapshot = snapshot
        self.anchor = anchor
        self.anchor_clean = anchor.lower().replace(" ", "").replace("-", "")

    def is_staple_threat(self, species: str) -> bool:
        clean = species.lower().replace(" ", "").replace("-", "")
        if not clean:
            return False
        if self.snapshot is not None:
            return self.snapshot.is_banned(species)
        return clean in DEFAULT_META_STAPLES

    def score_target_bonus(self, target_species: str, target_slot: int, slot_idx: int) -> float:
        clean = target_species.lower().replace(" ", "").replace("-", "")
        if not clean:
            return 0.0
        # Heavily target known meta sweepers and staples
        if self.is_staple_threat(target_species):
            return 25.0
        # Underestimate off-meta bulky anchors, leaving them alive to sweep
        if clean == self.anchor_clean:
            return -25.0
        return 0.0

    def choose_action(self, request: dict[str, Any]) -> str:
        # In team preview, meta-tuned agent expects high-speed offensive meta threats
        # and biases toward fast leads over defensive anchors
        return super().choose_action(request)


class AdaptedAntiMetaAgent(MetaTunedAgent):
    """Meta agent that has adapted its policy to respect anti-meta anchors.

    Recalibrates targeting priorities: recognizes that the off-meta anchor
    (Hippowdon) and Trick Room setters are high-threat win conditions and focus-fires
    them down, while measuring any retention trade-offs against the original meta pool.
    """

    def __init__(
        self,
        name: str = "AdaptedAntiMetaAgent",
        snapshot: "UsageSnapshot | None" = None,
        anchor: str = "Hippowdon",
        adaptation_weight: float = 1.0,
    ) -> None:
        super().__init__(name=name, snapshot=snapshot, anchor=anchor)
        if not (0.0 <= adaptation_weight <= 1.0):
            raise ValueError("adaptation_weight must be between 0.0 and 1.0")
        self.adaptation_weight = adaptation_weight

    def score_target_bonus(self, target_species: str, target_slot: int, slot_idx: int) -> float:
        clean = target_species.lower().replace(" ", "").replace("-", "")
        if not clean:
            return 0.0
        if clean == self.anchor_clean:
            # Shift from -25.0 (disregarding anchor) to +35.0 (prioritizing anchor shutdown)
            return -25.0 * (1.0 - self.adaptation_weight) + 35.0 * self.adaptation_weight
        if clean in {"farigiraf", "sinistcha"}:
            # Priority focus on support and Trick Room setters
            return 20.0 * self.adaptation_weight
        if self.is_staple_threat(target_species):
            # Maintain strong meta threat awareness with slight dilution
            return 25.0 * (1.0 - 0.25 * self.adaptation_weight)
        return 0.0
