"""Conditional Speed possibility sets from explicitly sanitized player evidence.

This module never accepts simulator state, opponent requests, or raw replay logs.
Evidence producers must certify that no unmodeled effect changed action order.
"""

from dataclasses import dataclass
from typing import Literal

StatSystem = Literal["ev", "sp"]


@dataclass(frozen=True)
class SpeedObservation:
    """One pair of observed moves by the same two Pokemon, before any pivot.

    Speeds are unmodified stats. Only Tailwind and Trick Room are modeled.
    Certification requires known priorities and no other Speed/order effects,
    including changes between the two actions. Unknown effects mean False.
    """

    turn: int
    own_speed: int
    opponent_first: bool
    own_priority: int
    opponent_priority: int
    trick_room: bool
    own_tailwind: bool
    opponent_tailwind: bool
    speed_order_certified: bool


def legal_speeds(base_speed: int, system: StatSystem) -> tuple[int, ...]:
    """All possible unmodified level-50 Speeds, with nature/investment unknown.

    EV rules allow IVs 0..31 and EV contributions 0..63. SP rules require IV 31
    and allow 0..32 points. Each investment is individually budget-feasible;
    no assumption about the opponent's other stats or usage distribution is made.
    """
    if type(base_speed) is not int or not 1 <= base_speed <= 255:
        raise ValueError("base_speed must be an integer in [1, 255]")
    if system == "ev":
        neutral = {(2 * base_speed + iv + ev) // 2 + 5 for iv in range(32) for ev in range(64)}
    elif system == "sp":
        neutral = {base_speed + 20 + points for points in range(33)}
    else:
        raise ValueError("system must be ev or sp")
    return tuple(sorted({stat * nature // 100 for stat in neutral for nature in (90, 100, 110)}))


def _fields(value: object, expected: set[str]) -> dict[str, object]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError("Evidence must contain exactly the documented public fields")
    return {str(key): item for key, item in value.items()}


def _integer(value: object, name: str, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return value


def _boolean(value: object, name: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{name} must be a boolean")
    return value


def parse_speed_evidence(value: object) -> tuple[int, StatSystem, list[SpeedObservation]]:
    """Reject extra fields rather than accidentally accepting private state."""
    data = _fields(value, {"base_speed", "system", "observations"})
    base = _integer(data["base_speed"], "base_speed", 1, 255)
    system = data["system"]
    if system not in ("ev", "sp"):
        raise ValueError("system must be ev or sp")
    observations = data["observations"]
    if not isinstance(observations, list):
        raise ValueError("observations must be a list")
    parsed: list[SpeedObservation] = []
    for observation in observations:
        row = _fields(observation, set(SpeedObservation.__dataclass_fields__))
        parsed.append(
            SpeedObservation(
                turn=_integer(row["turn"], "turn", 1, 10000),
                own_speed=_integer(row["own_speed"], "own_speed", 1, 1000),
                opponent_first=_boolean(row["opponent_first"], "opponent_first"),
                own_priority=_integer(row["own_priority"], "own_priority", -7, 5),
                opponent_priority=_integer(row["opponent_priority"], "opponent_priority", -7, 5),
                trick_room=_boolean(row["trick_room"], "trick_room"),
                own_tailwind=_boolean(row["own_tailwind"], "own_tailwind"),
                opponent_tailwind=_boolean(row["opponent_tailwind"], "opponent_tailwind"),
                speed_order_certified=_boolean(
                    row["speed_order_certified"], "speed_order_certified"
                ),
            )
        )
    # Explicit narrowing keeps the parser's boundary strictly typed.
    return base, "ev" if system == "ev" else "sp", parsed


def report_speed_uncertainty(evidence: object) -> dict[str, object]:
    """Intersect legal possibilities; ties remain possible in either order.

    These are logical support sets, not a posterior or confidence interval.
    Repeated orders never eliminate a tie or assign probability to a spread.
    """
    base, system, observations = parse_speed_evidence(evidence)
    prior = legal_speeds(base, system)
    remaining = list(prior)
    history: list[dict[str, object]] = []
    used = 0
    for observation in observations:
        reason = None
        if not observation.speed_order_certified:
            reason = "uncertified_speed_or_action_order_effects"
        elif observation.own_priority != observation.opponent_priority:
            reason = "different_move_priorities"
        else:
            used += 1
            own = observation.own_speed * (2 if observation.own_tailwind else 1)
            # Under Trick Room the slower Pokemon acts first. Equality always fits.
            faster_or_tied = observation.opponent_first != observation.trick_room
            remaining = [
                speed
                for speed in remaining
                if (
                    speed * (2 if observation.opponent_tailwind else 1) >= own
                    if faster_or_tied
                    else speed * (2 if observation.opponent_tailwind else 1) <= own
                )
            ]
        history.append(
            {
                "turn": observation.turn,
                "used": reason is None,
                "skip_reason": reason,
                "remaining_count": len(remaining),
            }
        )
    return {
        "schema_version": 1,
        "system": system,
        "level": 50,
        "base_speed": base,
        "status": "consistent" if remaining else "inconsistent_evidence",
        "prior_count": len(prior),
        "remaining_count": len(remaining),
        "possible_speeds": remaining,
        "minimum": min(remaining) if remaining else None,
        "maximum": max(remaining) if remaining else None,
        "observations_used": used,
        "observations_skipped": len(observations) - used,
        "history": history,
        "uncertainty": "Legal possibilities conditional on public evidence; no probabilities.",
        "limits": [
            "Nature and investment are unknown; IV legality follows the declared system.",
            "Only level 50, Tailwind and Trick Room are modeled; other effects require skipping.",
            "The evidence producer certifies eligibility; raw simulator logs are rejected.",
            "Track one unchanged opponent species/form and build across turns and switches.",
            "A tie is compatible with either move order, even across repeated observations.",
            "An empty set flags inconsistent evidence or assumptions, not a known opponent Speed.",
        ],
    }
