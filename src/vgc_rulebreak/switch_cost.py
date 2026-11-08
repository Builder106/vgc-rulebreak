"""Study R: paired rollout costs of voluntary Rage Fist switches."""

import json
import random
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vgc_rulebreak.agents.base import get_active_unfainted_slots, get_legal_slot_choices
from vgc_rulebreak.agents.heuristic import HeuristicAgent
from vgc_rulebreak.agents.random import RandomAgent
from vgc_rulebreak.explanation import execute_rollout_trial, read_replay_file
from vgc_rulebreak.protect_multi_seed import bootstrap_ci

FORMATS = ("gen9rulebreakragefistpersist", "gen9rulebreakragefistreset")
POLICIES = ("HeuristicBaseline", "RandomBaseline")


@dataclass(frozen=True)
class SwitchOpportunity:
    decision_index: int
    turn: int
    slot: int
    pokemon: str
    actual_choice: str
    stay_choice: str
    chose_switch: bool


def switch_opportunities(
    decisions: list[dict[str, Any]], candidate_role: str
) -> list[SwitchOpportunity]:
    """Count each living Rage Fist slot with a legal switch and stay once.

    The partner's chosen action stays fixed, including its reserved switch target.
    Forced replacements, pivot moves, trapped slots, preview and waits are excluded.
    Missing request evidence is an error, never a measured zero.
    """
    if candidate_role not in {"p1", "p2"}:
        raise ValueError("candidate_role must be p1 or p2")
    opportunities: list[SwitchOpportunity] = []
    for index, decision in enumerate(decisions):
        if decision["side"] != candidate_role:
            continue
        request = decision.get("request")
        if not isinstance(request, dict):
            raise ValueError(f"Missing request evidence at decision {index}")
        if request.get("wait") or request.get("teamPreview") or any(request.get("forceSwitch", [])):
            continue
        if "active" not in request:
            raise ValueError(f"Missing active evidence at decision {index}")
        actions = [a.strip() for a in decision["choice"].split(",")]
        pokemon = request.get("side", {}).get("pokemon", [])
        active_slots = get_active_unfainted_slots(request)
        # Showdown accepts compact choices when a fainted active slot cannot act.
        if len(actions) == len(active_slots) < len(request["active"]):
            expanded = ["pass"] * len(request["active"])
            for (slot, _), action in zip(active_slots, actions, strict=True):
                expanded[slot] = action
            actions = expanded
        for slot, active in active_slots:
            if slot >= len(pokemon) or slot >= len(actions) or not pokemon[slot].get("ident"):
                raise ValueError(f"Incomplete slot evidence at decision {index}")
            if "ragefist" not in pokemon[slot].get("moves", []):
                continue
            legal = get_legal_slot_choices(active, pokemon, slot)
            reserved = {a for i, a in enumerate(actions) if i != slot and a.startswith("switch ")}
            switches = [a for a in legal if a.startswith("switch ") and a not in reserved]
            stays = [a for a in legal if a.startswith("move ")]
            if not switches or not stays:
                continue
            if actions[slot] not in switches + stays:
                raise ValueError(f"Unsupported or illegal choice at decision {index}, slot {slot}")
            stay_actions = actions.copy()
            # Prespecified comparator avoids selecting the largest noisy rollout gain.
            stay_actions[slot] = stays[0]
            opportunities.append(
                SwitchOpportunity(
                    index,
                    decision["turn"],
                    slot,
                    pokemon[slot]["ident"],
                    decision["choice"],
                    ", ".join(stay_actions),
                    actions[slot].startswith("switch "),
                )
            )
    return opportunities


def _ratio_interval(games: list[dict[str, Any]], seed: int) -> tuple[float, float] | None:
    """Resample whole games, preserving within-game decision dependence."""
    if not games or not sum(g["eligible_opportunities"] for g in games):
        return None
    rng = random.Random(seed)
    ratios: list[float] = []
    for _ in range(1000):
        sample = rng.choices(games, k=len(games))
        denominator = sum(g["eligible_opportunities"] for g in sample)
        if denominator:
            ratios.append(sum(g["total_cost"] for g in sample) / denominator)
    ratios.sort()
    return ratios[int(len(ratios) * 0.025)], ratios[min(int(len(ratios) * 0.975), len(ratios) - 1)]


def estimate_switch_costs(
    replay_paths: Sequence[Path],
    candidate_role: str,
    trials: int = 20,
    seed_base: int = 1000,
    max_turns: int = 100,
    showdown_dir: Path | str | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Estimate signed stay-minus-switch points, normalized by all opportunities.

    Reports each format and opponent separately. Continuations use a fresh
    HeuristicAgent; RandomBaseline is freshly seeded for each paired branch.
    Intervals per decision describe rollout uncertainty. Aggregate intervals
    resample games and describe coverage of this replay cohort only.
    """
    if not replay_paths or trials < 2 or max_turns < 1:
        raise ValueError("Need replays, at least two trials, and a positive turn limit")
    resolved = [p.resolve() for p in replay_paths]
    if len(set(resolved)) != len(resolved):
        raise ValueError("Duplicate replay paths would double-count opportunities")
    # Validate the entire cohort before starting expensive rollouts.
    inputs: list[tuple[Path, dict[str, Any], list[SwitchOpportunity]]] = []
    for path in replay_paths:
        replay = read_replay_file(path)
        if replay["format_id"] not in FORMATS:
            raise ValueError("Switch costs require a Study R single-factor format")
        if not isinstance(replay.get("battle_seed"), list) or len(replay["battle_seed"]) != 4:
            raise ValueError("Replay must record its four-part battle seed")
        opportunities = switch_opportunities(replay["decisions"], candidate_role)
        if any(o.turn >= max_turns for o in opportunities if o.chose_switch):
            raise ValueError("Turn limit must exceed every evaluated switch turn")
        inputs.append((path, replay, opportunities))

    rng = random.Random(seed_base)
    games: list[dict[str, Any]] = []
    for path, replay, opportunities in inputs:
        for policy in POLICIES:
            evidence: list[dict[str, Any]] = []
            for opportunity in opportunities:
                if not opportunity.chose_switch:
                    continue
                paired_trials: list[dict[str, Any]] = []
                deltas: list[float] = []
                for trial in range(trials):
                    seed = (
                        rng.randrange(65536),
                        rng.randrange(65536),
                        rng.randrange(65536),
                        rng.randrange(65536),
                    )
                    points: list[float] = []
                    end_reasons: list[str] = []
                    for choice in (opportunity.actual_choice, opportunity.stay_choice):
                        opponent = (
                            HeuristicAgent(name=policy)
                            if policy == "HeuristicBaseline"
                            else RandomAgent(name=policy, seed=seed[0])
                        )
                        result = execute_rollout_trial(
                            replay,
                            opportunity.decision_index,
                            choice,
                            seed,
                            HeuristicAgent(),
                            opponent,
                            candidate_role,
                            trial,
                            max_turns=max_turns,
                            showdown_dir=showdown_dir,
                        )
                        if result.end_reason == "stalled":
                            raise RuntimeError("Switch rollout stalled; refusing a fabricated tie")
                        points.append(result.points)
                        end_reasons.append(result.end_reason)
                    deltas.append(points[1] - points[0])
                    paired_trials.append(
                        {
                            "seed": seed,
                            "switch_points": points[0],
                            "stay_points": points[1],
                            "switch_end_reason": end_reasons[0],
                            "stay_end_reason": end_reasons[1],
                        }
                    )
                interval = bootstrap_ci(deltas, seed=seed_base)
                evidence.append(
                    {
                        **asdict(opportunity),
                        "cost": sum(deltas) / trials,
                        "ci_95": interval,
                        "costly": interval[0] > 0,
                        "paired_trials": paired_trials,
                    }
                )
            games.append(
                {
                    "replay": str(path),
                    "format_id": replay["format_id"],
                    "battle_seed": replay["battle_seed"],
                    "players": replay["players"],
                    "opponent_policy": policy,
                    "eligible_opportunities": len(opportunities),
                    "opportunities": [asdict(o) for o in opportunities],
                    "switches": len(evidence),
                    "total_cost": sum(e["cost"] for e in evidence),
                    "costly_switches": sum(e["costly"] for e in evidence),
                    "rollouts": len(evidence) * trials * 2,
                    "turn_limited_rollouts": sum(
                        trial[key] == "turn_limit"
                        for event in evidence
                        for trial in event["paired_trials"]
                        for key in ("switch_end_reason", "stay_end_reason")
                    ),
                    "evidence": evidence,
                }
            )

    summaries: list[dict[str, Any]] = []
    for format_id in FORMATS:
        for policy in POLICIES:
            cohort = [
                g for g in games if g["format_id"] == format_id and g["opponent_policy"] == policy
            ]
            if not cohort:
                continue
            count = sum(g["eligible_opportunities"] for g in cohort)
            switches = sum(g["switches"] for g in cohort)
            cost = sum(g["total_cost"] for g in cohort)
            costly = sum(g["costly_switches"] for g in cohort)
            summaries.append(
                {
                    "format_id": format_id,
                    "opponent_policy": policy,
                    "games": len(cohort),
                    "rollouts": sum(g["rollouts"] for g in cohort),
                    "turn_limited_rollouts": sum(g["turn_limited_rollouts"] for g in cohort),
                    "eligible_opportunities": count,
                    "switches": switches,
                    "switch_rate": switches / count if count else None,
                    "costly_switches": costly,
                    "costly_switch_rate": costly / count if count else None,
                    "total_cost": cost,
                    "cost_per_opportunity": cost / count if count else None,
                    "cost_per_switch": cost / switches if switches else None,
                    "cost_per_opportunity_ci_95": _ratio_interval(cohort, seed_base),
                }
            )
    report = {
        "schema_version": 1,
        "candidate_role": candidate_role,
        "config": {
            "trials": trials,
            "seed_base": seed_base,
            "max_turns": max_turns,
            "opponent_policies": POLICIES,
            "continuation_policy": "HeuristicBaseline",
            "stay_comparator": "first legal move in request order; partner action fixed",
            "cost": "mean(stay points - switch points); signed, no clipping",
            "scoring": "win=1, loss=0, tie or turn limit=0.5",
            "aggregate_ci": "95% percentile bootstrap over whole replay games",
        },
        "limitations": [
            "A fixed stay comparator is not an optimal-action regret estimate.",
            "Rollouts condition on recorded simulator state, not sampled hidden information.",
            "Format cohorts are descriptive; their difference is not a causal mechanic effect.",
            "Game intervals exclude rollout noise and do not represent training-seed uncertainty.",
            "Costly flags are per-decision intervals without multiple-comparison correction.",
        ],
        "summaries": summaries,
        "games": games,
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
