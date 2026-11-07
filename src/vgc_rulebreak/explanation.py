"""Replay explanation with repeated-rollout evidence for Study P.

Given an evaluated game's replay and a target decision (such as a Protect choice or
candidate mistake), this module:
1. Reconstructs the exact board state up to the decision point under the pinned rules.
2. Identifies the observable actual choice and enumerates legal alternatives.
3. Reseeds the simulator PRNG and runs repeated paired rollouts across multiple
   reference opponent policies (e.g. HeuristicBaseline and RandomBaseline).
4. Estimates the outcome difference (delta win rate and PPG) with 95% bootstrap
   confidence intervals.
5. Produces a structured explanation report grounded strictly in observable board
   state and rollout evidence without inferring unrecorded internal beliefs.
"""

import gzip
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vgc_rulebreak.agents.base import (
    BattleAgent,
    get_active_unfainted_slots,
    get_legal_slot_choices,
)
from vgc_rulebreak.agents.heuristic import HeuristicAgent
from vgc_rulebreak.agents.random import RandomAgent
from vgc_rulebreak.agents.trained import checkpoint_agent
from vgc_rulebreak.mistakes import _chooses_protect, candidate_mistakes
from vgc_rulebreak.pilot import _check_protect_depleted
from vgc_rulebreak.protect_multi_seed import bootstrap_ci
from vgc_rulebreak.simulator.battle import BattleSession
from vgc_rulebreak.simulator.process import ShowdownProcess

EXPLANATION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class RolloutTrialResult:
    """Individual rollout trial result."""

    trial: int
    seed: tuple[int, int, int, int]
    opponent_policy: str
    choice: str
    winner: str | None
    candidate_won: bool
    points: float
    turns: int
    protect_depleted: bool


def read_replay_file(path: Path) -> dict[str, Any]:
    """Read a battle replay from a gzipped or plain JSON file."""
    raw = path.read_bytes()
    if path.suffix == ".gz" or raw[:2] == b"\x1f\x8b":
        data: dict[str, Any] = json.loads(gzip.decompress(raw))
        return data
    data = json.loads(raw.decode("utf-8"))
    return data


def extract_board_state(
    request: dict[str, Any],
    log: list[str] | None = None,
) -> dict[str, Any]:
    """Extract observable board condition, active Pokémon, and Protect PP."""
    active_slots = request.get("active", [])
    pokemon_list = request.get("side", {}).get("pokemon", [])
    side_name = request.get("side", {}).get("name", "candidate")

    active_pokemon: list[dict[str, Any]] = []
    protect_pp_summary: dict[str, dict[str, int]] = {}

    for slot_idx, slot_data in enumerate(active_slots):
        if slot_data is None or slot_idx >= len(pokemon_list):
            continue
        p = pokemon_list[slot_idx]
        ident = p.get("ident", f"slot{slot_idx}")
        details = p.get("details", "")
        condition = p.get("condition", "0/0")
        fainted = "fnt" in condition or condition.startswith("0/")
        hp = 0
        maxhp = 0
        status = None
        if not fainted:
            parts = condition.split()
            if "/" in parts[0]:
                hp_s, _, max_s = parts[0].partition("/")
                hp = int(hp_s)
                maxhp = int(max_s) if max_s else hp
            status = parts[1] if len(parts) > 1 else None

        moves = slot_data.get("moves", [])
        protect_info = None
        for m in moves:
            if m.get("id") == "protect":
                protect_info = {
                    "current": m.get("pp", 0),
                    "max": m.get("maxpp", 0),
                    "disabled": m.get("disabled", False),
                }
                protect_pp_summary[ident] = {
                    "current": m.get("pp", 0),
                    "max": m.get("maxpp", 0),
                }
                break

        active_pokemon.append(
            {
                "slot": slot_idx,
                "ident": ident,
                "details": details,
                "condition": condition,
                "hp": hp,
                "maxhp": maxhp,
                "status": status,
                "protect_pp": protect_info,
            }
        )

    # Check bench Pokémon Protect PP from side list
    for p in pokemon_list:
        ident = p.get("ident", "")
        if ident not in protect_pp_summary and "protect" in p.get("moves", []):
            protect_pp_summary[ident] = {"current": -1, "max": -1}

    # Extract opponent active Pokémon from log lines if available
    opponent_active: list[dict[str, Any]] = []
    if log:
        opp_side = "p2" if side_name == "p1" else "p1"
        for line in reversed(log):
            if line.startswith(f"|switch|{opp_side}") or line.startswith(f"|drag|{opp_side}"):
                parts = line.split("|")
                if len(parts) >= 4:
                    slot_ident = parts[2]
                    species = parts[3].split(",")[0]
                    cond = parts[4] if len(parts) >= 5 else ""
                    if not any(o["slot_ident"] == slot_ident for o in opponent_active):
                        opponent_active.append(
                            {
                                "slot_ident": slot_ident,
                                "species": species,
                                "condition": cond,
                            }
                        )
                if len(opponent_active) >= 2:
                    break

    scarcity_binds = any(
        info["current"] == 0 and info["max"] > 0 for info in protect_pp_summary.values()
    )

    legal_choices: list[str] = []
    unfainted = get_active_unfainted_slots(request)
    if len(unfainted) == 1:
        slot, sdata = unfainted[0]
        legal_choices = get_legal_slot_choices(sdata, pokemon_list, slot)
    elif len(unfainted) >= 2:
        c0 = get_legal_slot_choices(unfainted[0][1], pokemon_list, unfainted[0][0])
        c1 = get_legal_slot_choices(unfainted[1][1], pokemon_list, unfainted[1][0])
        legal_choices = [f"{a0}, {a1}" for a0 in c0[:4] for a1 in c1[:4]]

    return {
        "active_pokemon": active_pokemon,
        "opponent_active": opponent_active,
        "protect_pp_summary": protect_pp_summary,
        "scarcity_binds_at_decision": scarcity_binds,
        "legal_choices": legal_choices,
    }


def detect_candidate_decision(
    replay: dict[str, Any],
    candidate_role: str,
    decision_index: int | None = None,
) -> tuple[int, dict[str, Any]]:
    """Locate the target decision index to explain in a replay."""
    decisions = replay.get("decisions", [])
    if not decisions:
        raise ValueError("Replay contains no recorded decisions.")

    if decision_index is not None:
        if not (0 <= decision_index < len(decisions)):
            raise ValueError(
                f"decision_index {decision_index} out of range [0, {len(decisions) - 1}]."
            )
        dec = decisions[decision_index]
        if dec.get("side") != candidate_role:
            side = dec.get("side")
            raise ValueError(
                f"Decision at index {decision_index} belongs to {side}, expected {candidate_role}."
            )
        return decision_index, dec

    # 1. Look for candidate mistakes detected by consecutive_protect detector
    mistakes = candidate_mistakes(decisions, candidate_role)
    if mistakes and "consecutive_protect" in mistakes:
        evidence = mistakes["consecutive_protect"].get("evidence", [])
        if evidence:
            first_idx = int(evidence[0]["decision_index"])
            return first_idx, decisions[first_idx]

    # 2. Look for the first decision where candidate chose Protect
    for idx, dec in enumerate(decisions):
        if dec.get("side") != candidate_role:
            continue
        req = dec.get("request")
        if not req or req.get("wait") or req.get("teamPreview"):
            continue
        active = req.get("active", [])
        actions = [a.strip() for a in dec.get("choice", "").split(",")]
        for slot, act in enumerate(active):
            if slot < len(actions) and _chooses_protect(actions[slot], act.get("moves", [])):
                return idx, dec

    # 3. Fallback: first active turn decision for candidate
    for idx, dec in enumerate(decisions):
        if dec.get("side") == candidate_role:
            req = dec.get("request")
            if req and not req.get("wait") and not req.get("teamPreview"):
                return idx, dec

    raise ValueError(f"No eligible decision found for candidate role {candidate_role}.")


def _describe_slot_action(action: str, moves: list[dict[str, Any]]) -> str:
    """Format an action into a readable description."""
    parts = action.split()
    if not parts:
        return action
    if parts[0] == "move":
        try:
            m_idx = int(parts[1]) - 1
            if 0 <= m_idx < len(moves):
                name = moves[m_idx].get("move", parts[1])
                target = f" on target {parts[2]}" if len(parts) > 2 else ""
                return f"{name}{target}"
        except (ValueError, IndexError):
            pass
        return action
    if parts[0] == "switch":
        return f"switch to slot {parts[1]}" if len(parts) > 1 else action
    return action


def determine_alternatives(
    request: dict[str, Any],
    actual_choice: str,
    target_slot: int | None = None,
) -> list[tuple[str, str]]:
    """Generate legal alternative choices for the candidate.

    Returns a list of (choice_string, description) tuples.
    """
    active = request.get("active", [])
    pokemon = request.get("side", {}).get("pokemon", [])
    actual_actions = [a.strip() for a in actual_choice.split(",")]

    # If target slot not given, identify slot where Protect was chosen, or slot 1
    if target_slot is None:
        for slot, act in enumerate(active):
            if slot < len(actual_actions) and _chooses_protect(
                actual_actions[slot], act.get("moves", [])
            ):
                target_slot = slot
                break
        if target_slot is None:
            target_slot = 0

    if target_slot >= len(active) or target_slot >= len(actual_actions):
        return []

    slot_active = active[target_slot]
    moves = slot_active.get("moves", [])
    legal_slot_choices = get_legal_slot_choices(slot_active, pokemon, target_slot)

    alternatives: list[tuple[str, str]] = []
    actual_slot_action = actual_actions[target_slot]

    for alt_slot_action in legal_slot_choices:
        if alt_slot_action == actual_slot_action:
            continue
        new_actions = list(actual_actions)
        new_actions[target_slot] = alt_slot_action
        full_choice = ", ".join(new_actions)

        desc = _describe_slot_action(alt_slot_action, moves)
        mon_name = pokemon[target_slot].get("ident", f"slot {target_slot}")
        label = f"{mon_name}: {desc} (alternative)"
        alternatives.append((full_choice, label))

    return alternatives


def replay_prefix_to_decision(
    session: BattleSession,
    decisions: list[dict[str, Any]],
    target_decision_index: int,
) -> int:
    """Step the battle session through the replay prefix up to the target decision."""
    d_idx = 0
    while d_idx < target_decision_index and not session.is_ended:
        p1_can = session.p1_request is not None and not session.p1_request.get("wait", False)
        p2_can = session.p2_request is not None and not session.p2_request.get("wait", False)

        c1: str | None = None
        c2: str | None = None
        if p1_can and d_idx < target_decision_index and decisions[d_idx]["side"] == "p1":
            c1 = decisions[d_idx]["choice"]
            d_idx += 1
        if p2_can and d_idx < target_decision_index and decisions[d_idx]["side"] == "p2":
            c2 = decisions[d_idx]["choice"]
            d_idx += 1
        session.step(c1, c2)

    return d_idx


def execute_rollout_trial(
    replay_data: dict[str, Any],
    decision_index: int,
    candidate_choice: str,
    reseed: tuple[int, int, int, int],
    candidate_agent: BattleAgent,
    opponent_agent: BattleAgent,
    candidate_role: str,
    trial_number: int,
    max_turns: int = 60,
    showdown_dir: Path | str | None = None,
) -> RolloutTrialResult:
    """Execute a single branched rollout trial in Showdown."""
    candidate_agent.reset()
    opponent_agent.reset()

    format_id = replay_data["format_id"]
    players = replay_data["players"]
    p1_info = players["p1"]
    p2_info = players["p2"]
    original_seed = tuple(replay_data["battle_seed"])

    with ShowdownProcess(showdown_dir) as process:
        session = BattleSession(process)
        session.start(
            format_id,
            p1_info["name"],
            p1_info["team"],
            p2_info["name"],
            p2_info["team"],
            seed=original_seed,
        )

        replay_prefix_to_decision(session, replay_data["decisions"], decision_index)

        if session.is_ended:
            raise RuntimeError("Battle ended before reaching target decision.")

        # Reseed simulator PRNG for branching stochasticity
        s_str = ",".join(map(str, reseed))
        session.stream.send(f">reseed {s_str}")

        # Execute target decision step
        opp_request = session.p2_request if candidate_role == "p1" else session.p1_request

        opp_choice = (
            opponent_agent.choose_action(opp_request)
            if opp_request and not opp_request.get("wait", False)
            else None
        )
        c1 = candidate_choice if candidate_role == "p1" else opp_choice
        c2 = opp_choice if candidate_role == "p1" else candidate_choice

        session.step(c1, c2)

        depleted = False
        while not session.is_ended and session.turn < max_turns:
            p1_can = session.p1_request is not None and not session.p1_request.get("wait", False)
            p2_can = session.p2_request is not None and not session.p2_request.get("wait", False)
            if not p1_can and not p2_can:
                break

            if not depleted:
                depleted = _check_protect_depleted(session.p1_request) or _check_protect_depleted(
                    session.p2_request
                )

            p1_c = (
                (
                    candidate_agent.choose_action(session.p1_request)
                    if candidate_role == "p1"
                    else opponent_agent.choose_action(session.p1_request)
                )
                if p1_can and session.p1_request
                else None
            )

            p2_c = (
                (
                    opponent_agent.choose_action(session.p2_request)
                    if candidate_role == "p1"
                    else candidate_agent.choose_action(session.p2_request)
                )
                if p2_can and session.p2_request
                else None
            )

            session.step(p1_c, p2_c)

        winner = session.winner
        cand_name = players[candidate_role]["name"]
        candidate_won = winner == cand_name
        is_tie = winner is None
        points = 1.0 if candidate_won else (0.5 if is_tie else 0.0)

        return RolloutTrialResult(
            trial=trial_number,
            seed=reseed,
            opponent_policy=opponent_agent.name,
            choice=candidate_choice,
            winner=winner,
            candidate_won=candidate_won,
            points=points,
            turns=session.turn,
            protect_depleted=depleted,
        )


def build_explanation_narrative(
    match_meta: dict[str, Any],
    board_state: dict[str, Any],
    actual_choice: str,
    action_summaries: list[dict[str, Any]],
    outcome_differences: list[dict[str, Any]],
) -> str:
    """Generate an evidence-grounded explanation narrative without internal belief claims."""
    turn = match_meta.get("turn")
    game_id = match_meta.get("game_id")
    candidate = match_meta.get("candidate")
    format_id = match_meta.get("format_id")
    pp_summary = board_state.get("protect_pp_summary", {})

    pp_details = []
    for mon, p_info in pp_summary.items():
        if p_info["max"] > 0:
            pp_details.append(f"{mon}: {p_info['current']}/{p_info['max']} PP remaining")
    pp_text = ", ".join(pp_details) if pp_details else "no active Protect slots"

    lines = [
        (
            f"In game {game_id} ({format_id}), agent {candidate} chose '{actual_choice}' "
            f"on turn {turn}."
        ),
        f"Observable Protect PP status at this decision: {pp_text}.",
    ]

    scarcity_binds = board_state.get("scarcity_binds_at_decision", False)
    if not scarcity_binds:
        lines.append(
            "Protect scarcity was not binding: no active Pokémon had exhausted Protect PP, "
            "matching the aggregate Study P finding that 8 PP limits do not constrain "
            "standard matches."
        )

    for diff in outcome_differences:
        alt = diff["alternative_choice"]
        delta = diff["delta_ppg"]
        ci = diff["delta_ci_95"]
        sig = diff["is_statistically_significant"]
        verdict = (
            "statistically significant" if sig else "not statistically distinguishable from zero"
        )
        lines.append(
            f"Repeated rollouts comparing alternative '{alt}' against actual choice "
            f"'{actual_choice}' estimate a performance difference of {delta:+.3f} PPG "
            f"(95% bootstrap CI [{ci['ci_lower']:+.3f}, {ci['ci_upper']:+.3f}]), "
            f"which is {verdict}."
        )

    lines.append(
        "Conclusion: Tactical outcome differences are evaluated empirically via repeated "
        "rollouts from the branched state, without inferring unrecorded internal beliefs "
        "or post-hoc intentions."
    )
    return " ".join(lines)


def produce_replay_explanation(
    replay_path: Path,
    decision_index: int | None = None,
    candidate_choice_override: str | None = None,
    alternative_choices: Sequence[tuple[str, str]] | None = None,
    trials_per_action: int = 10,
    opponent_policies: Sequence[str] = ("HeuristicBaseline", "RandomBaseline"),
    checkpoint_path: Path | None = None,
    seed_base: int = 1000,
    showdown_dir: Path | str | None = None,
    output_path: Path | None = None,
    runner: Callable[..., RolloutTrialResult] | None = None,
) -> dict[str, Any]:
    """Produce a complete replay explanation with repeated-rollout evidence."""
    replay_data = read_replay_file(replay_path)
    players = replay_data.get("players", {})

    candidate_role = "p1"
    if "p1" in players and "p2" in players:
        p1_name = players["p1"].get("name", "")
        if any(tag in p1_name for tag in ("source", "native", "adapted")):
            candidate_role = "p1"
        elif any(tag in players["p2"].get("name", "") for tag in ("source", "native", "adapted")):
            candidate_role = "p2"

    d_idx, target_decision = detect_candidate_decision(replay_data, candidate_role, decision_index)
    actual_choice = candidate_choice_override or target_decision.get("choice", "")
    req = target_decision.get("request", {})
    turn = target_decision.get("turn", 0)

    board_state = extract_board_state(req, replay_data.get("log"))

    alts = (
        list(alternative_choices)
        if alternative_choices
        else determine_alternatives(req, actual_choice)
    )
    valid_alts = [(choice, desc) for choice, desc in alts if choice != actual_choice]

    def get_candidate_agent() -> BattleAgent:
        if checkpoint_path and checkpoint_path.exists():
            return checkpoint_agent(checkpoint_path)
        return HeuristicAgent("CandidatePolicy")

    def get_opponent_agent(policy_name: str, seed: int) -> BattleAgent:
        if policy_name == "RandomBaseline":
            return RandomAgent("RandomBaseline", seed=seed)
        return HeuristicAgent("HeuristicBaseline")

    run_trial_fn = runner or execute_rollout_trial

    actions_to_test: list[tuple[str, str]] = [
        (actual_choice, f"Actual choice: {actual_choice}"),
        *valid_alts,
    ]

    trial_records: dict[str, dict[str, list[RolloutTrialResult]]] = {
        choice: {pol: [] for pol in opponent_policies} for choice, _ in actions_to_test
    }

    trial_counter = 0
    for pol_idx, pol_name in enumerate(opponent_policies):
        for t in range(trials_per_action):
            trial_counter += 1
            rollout_seed = (
                seed_base + pol_idx * 1000 + t * 17 + 1,
                seed_base + pol_idx * 1000 + t * 17 + 3,
                seed_base + pol_idx * 1000 + t * 17 + 7,
                seed_base + pol_idx * 1000 + t * 17 + 11,
            )
            opp_seed = seed_base + pol_idx * 1000 + t * 31 + 5

            for choice, _ in actions_to_test:
                cand_agent = get_candidate_agent()
                opp_agent = get_opponent_agent(pol_name, seed=opp_seed)
                res = run_trial_fn(
                    replay_data=replay_data,
                    decision_index=d_idx,
                    candidate_choice=choice,
                    reseed=rollout_seed,
                    candidate_agent=cand_agent,
                    opponent_agent=opp_agent,
                    candidate_role=candidate_role,
                    trial_number=trial_counter,
                    showdown_dir=showdown_dir,
                )
                trial_records[choice][pol_name].append(res)

    action_summaries: list[dict[str, Any]] = []
    for choice, label in actions_to_test:
        all_trials: list[RolloutTrialResult] = []
        by_opponent: dict[str, Any] = {}
        for pol, trials in trial_records[choice].items():
            all_trials.extend(trials)
            wins = sum(1 for t in trials if t.candidate_won)
            pts = [t.points for t in trials]
            ci_low, ci_high = bootstrap_ci(pts, seed=seed_base + 10)
            avg_turns = round(sum(t.turns for t in trials) / len(trials), 2) if trials else 0.0
            by_opponent[pol] = {
                "trials": len(trials),
                "wins": wins,
                "win_rate": round(wins / len(trials), 4) if trials else 0.0,
                "points_per_game": round(sum(pts) / len(pts), 4) if pts else 0.0,
                "ci_95": {"ci_lower": ci_low, "ci_upper": ci_high},
                "avg_turns": avg_turns,
            }

        total_trials = len(all_trials)
        total_wins = sum(1 for t in all_trials if t.candidate_won)
        total_losses = sum(1 for t in all_trials if not t.candidate_won and t.points == 0.0)
        total_ties = sum(1 for t in all_trials if t.points == 0.5)
        pooled_pts = [t.points for t in all_trials]
        pooled_ci_low, pooled_ci_high = bootstrap_ci(pooled_pts, seed=seed_base + 11)
        pooled_ppg = round(sum(pooled_pts) / total_trials, 4) if total_trials else 0.0

        action_summaries.append(
            {
                "choice": choice,
                "description": label,
                "trials": total_trials,
                "wins": total_wins,
                "losses": total_losses,
                "ties": total_ties,
                "win_rate": round(total_wins / total_trials, 4) if total_trials else 0.0,
                "points_per_game": pooled_ppg,
                "ci_95": {"ci_lower": pooled_ci_low, "ci_upper": pooled_ci_high},
                "avg_turns": round(sum(t.turns for t in all_trials) / total_trials, 2)
                if total_trials
                else 0.0,
                "by_opponent": by_opponent,
            }
        )

    actual_trials_by_pol = trial_records[actual_choice]
    outcome_differences: list[dict[str, Any]] = []

    for alt_choice, _ in valid_alts:
        alt_trials_by_pol = trial_records[alt_choice]
        paired_deltas: list[float] = []
        by_opp_diff: dict[str, Any] = {}

        for pol in opponent_policies:
            act_list = actual_trials_by_pol[pol]
            alt_list = alt_trials_by_pol[pol]
            pol_deltas = [
                alt.points - act.points for alt, act in zip(alt_list, act_list, strict=False)
            ]
            paired_deltas.extend(pol_deltas)
            ci_l, ci_u = bootstrap_ci(pol_deltas, seed=seed_base + 20)
            by_opp_diff[pol] = {
                "delta_ppg": round(sum(pol_deltas) / len(pol_deltas), 4) if pol_deltas else 0.0,
                "ci_95": {"ci_lower": ci_l, "ci_upper": ci_u},
            }

        delta_ppg = round(sum(paired_deltas) / len(paired_deltas), 4) if paired_deltas else 0.0
        delta_ci_l, delta_ci_u = bootstrap_ci(paired_deltas, seed=seed_base + 25)
        is_sig = delta_ci_l > 0.0 or delta_ci_u < 0.0

        outcome_differences.append(
            {
                "actual_choice": actual_choice,
                "alternative_choice": alt_choice,
                "delta_ppg": delta_ppg,
                "delta_win_rate": delta_ppg,
                "delta_ci_95": {"ci_lower": delta_ci_l, "ci_upper": delta_ci_u},
                "is_statistically_significant": is_sig,
                "by_opponent": by_opp_diff,
            }
        )

    match_meta = {
        "game_id": replay_data.get("game_id", "unknown"),
        "replay_path": str(replay_path),
        "format_id": replay_data.get("format_id", "unknown"),
        "variant": ("protect-8" if "8" in replay_data.get("format_id", "") else "protect-16"),
        "candidate": players.get(candidate_role, {}).get("name", "candidate"),
        "candidate_role": candidate_role,
        "opponent": players.get("p2" if candidate_role == "p1" else "p1", {}).get(
            "name", "opponent"
        ),
        "decision_index": d_idx,
        "turn": turn,
        "battle_seed": replay_data.get("battle_seed"),
    }

    explanation_text = build_explanation_narrative(
        match_meta=match_meta,
        board_state=board_state,
        actual_choice=actual_choice,
        action_summaries=action_summaries,
        outcome_differences=outcome_differences,
    )

    explanation_id = f"exp-{match_meta['game_id']}-t{turn:02d}"
    total_rollouts = len(actions_to_test) * len(opponent_policies) * trials_per_action
    depletions_count = sum(
        1
        for choice in trial_records
        for pol in trial_records[choice]
        for t in trial_records[choice][pol]
        if t.protect_depleted
    )

    result: dict[str, Any] = {
        "schema_version": EXPLANATION_SCHEMA_VERSION,
        "explanation_id": explanation_id,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "match": match_meta,
        "board_state": board_state,
        "decision": {
            "actual_choice": actual_choice,
            "turn": turn,
            "candidate_role": candidate_role,
        },
        "rollout_config": {
            "trials_per_action": trials_per_action,
            "opponent_policies": list(opponent_policies),
            "seed_base": seed_base,
            "total_rollouts_executed": total_rollouts,
        },
        "action_summaries": action_summaries,
        "outcome_differences": outcome_differences,
        "findings": {
            "actual_choice_is_harmful": any(
                d["is_statistically_significant"] and d["delta_ppg"] > 0
                for d in outcome_differences
            ),
            "protect_depleted_in_rollouts": depletions_count,
            "scarcity_binds_at_decision": board_state.get("scarcity_binds_at_decision", False),
        },
        "explanation_text": explanation_text,
    }

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

    return result
