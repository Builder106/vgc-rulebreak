"""Pilot evaluation sizing and compute budget calibration for the Protect study."""

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vgc_rulebreak.agents.base import BattleAgent
from vgc_rulebreak.agents.heuristic import HeuristicAgent
from vgc_rulebreak.manifest import TeamManifest, load_manifest
from vgc_rulebreak.simulator.battle import BattleSession
from vgc_rulebreak.simulator.process import ShowdownProcess

PROTECT_MOVE_IDS = frozenset({"protect"})
PROTECTION_MOVE_IDS = frozenset(
    {"protect", "spikyshield", "detect", "banefulbunker", "kingsshield", "silktrap"}
)


@dataclass(frozen=True)
class PilotBattleResult:
    winner: str | None
    turns: int
    duration_seconds: float
    p1_decisions: int
    p2_decisions: int
    protect_uses: int
    protect_depleted: bool


@dataclass(frozen=True)
class PilotReport:
    sample_pairs: int
    total_pilot_battles: int
    avg_turns: float
    avg_duration_seconds: float
    decisions_per_second: float
    avg_turn_latency_ms: float
    protect_16_uses_per_match: float
    protect_8_uses_per_match: float
    protect_16_depletion_rate: float
    protect_8_depletion_rate: float
    matchups_count: int
    recommended_pairs_per_matchup: int
    estimated_total_matches: int
    recommended_compute_budget_seconds: int


def _check_protect_depleted(request: dict[str, Any] | None) -> bool:
    """Check if any active Pokémon on this side has depleted all Protect PP."""
    if not request:
        return False
    active = request.get("active", [])
    for slot in active:
        if not slot:
            continue
        for move in slot.get("moves", []):
            if move.get("id") in PROTECT_MOVE_IDS and move.get("pp", 1) == 0:
                return True
    return False


def _count_protect_opportunities(request: dict[str, Any] | None) -> int:
    """Count active slots that could legally choose a Protect move this decision."""
    if not request or request.get("forceSwitch") or request.get("teamPreview"):
        return 0
    count = 0
    for slot in request.get("active", []):
        if not slot:
            continue
        if any(
            move.get("id") in PROTECT_MOVE_IDS
            and move.get("pp", 1) > 0
            and not move.get("disabled", False)
            for move in slot.get("moves", [])
        ):
            count += 1
    return count


def _count_protect_choices(request: dict[str, Any] | None, choice: str | None) -> int:
    """Count how many slots chose a Protect move in this turn."""
    if not request or not choice:
        return 0
    active = request.get("active", [])
    uses = 0
    actions = [a.strip() for a in choice.split(",") if a.strip()]
    for slot_idx, action in enumerate(actions):
        if not action.startswith("move "):
            continue
        parts = action.split()
        if len(parts) < 2:
            continue
        try:
            m_idx = int(parts[1]) - 1
        except ValueError:
            continue
        if slot_idx < len(active) and active[slot_idx]:
            moves = active[slot_idx].get("moves", [])
            if 0 <= m_idx < len(moves) and moves[m_idx].get("id") in PROTECT_MOVE_IDS:
                uses += 1
    return uses


def run_pilot_battle(
    p1_agent: BattleAgent,
    p2_agent: BattleAgent,
    format_id: str,
    p1_team: str,
    p2_team: str,
    seed: tuple[int, int, int, int] | None = None,
    showdown_dir: Path | str | None = None,
    max_turns: int = 60,
) -> PilotBattleResult:
    """Execute a single pilot battle and record decisions, timings, and Protect metrics."""
    start_time = time.perf_counter()
    p1_decisions = 0
    p2_decisions = 0
    protect_uses = 0
    protect_depleted = False

    p1_agent.reset()
    p2_agent.reset()

    with ShowdownProcess(showdown_dir) as process:
        session = BattleSession(process)
        session.start(format_id, p1_agent.name, p1_team, p2_agent.name, p2_team, seed=seed)

        while not session.is_ended and session.turn < max_turns:
            p1_can_act = session.p1_request is not None and not session.p1_request.get(
                "wait", False
            )
            p2_can_act = session.p2_request is not None and not session.p2_request.get(
                "wait", False
            )

            if not p1_can_act and not p2_can_act:
                break

            if not protect_depleted:
                protect_depleted = _check_protect_depleted(
                    session.p1_request
                ) or _check_protect_depleted(session.p2_request)

            p1_choice = (
                p1_agent.choose_action(session.p1_request)
                if (p1_can_act and session.p1_request)
                else None
            )
            p2_choice = (
                p2_agent.choose_action(session.p2_request)
                if (p2_can_act and session.p2_request)
                else None
            )

            if p1_can_act:
                p1_decisions += 1
                protect_uses += _count_protect_choices(session.p1_request, p1_choice)
            if p2_can_act:
                p2_decisions += 1
                protect_uses += _count_protect_choices(session.p2_request, p2_choice)

            turn_res = session.step(p1_choice, p2_choice)
            if turn_res.is_ended:
                break

        duration = time.perf_counter() - start_time
        return PilotBattleResult(
            winner=session.winner,
            turns=session.turn,
            duration_seconds=duration,
            p1_decisions=p1_decisions,
            p2_decisions=p2_decisions,
            protect_uses=protect_uses,
            protect_depleted=protect_depleted,
        )


def build_manifest_matchups(manifest: TeamManifest) -> list[tuple[str, str, str, str]]:
    """Generate representative cross-play matchups.

    Returns tuples of (team1_id, team1_packed, team2_id, team2_packed).
    """
    matchups: list[tuple[str, str, str, str]] = []
    team_list = list(manifest.teams.values())

    # Build unique pairwise matchups across the manifest archetypes
    for i in range(len(team_list)):
        for j in range(i + 1, len(team_list)):
            t1 = team_list[i]
            t2 = team_list[j]
            matchups.append((t1.id, t1.packed, t2.id, t2.packed))

    return matchups


def calculate_sample_size(
    p_baseline: float,
    min_detectable_effect: float = 0.08,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """Calculate minimum sample size per group for two-proportion comparison."""
    # Two-sided standard normal quantiles: z_alpha/2 for 0.05 is ~1.96, z_beta for 0.80 is ~0.84
    z_alpha = 1.96
    z_beta = 0.84
    p1 = max(min(p_baseline, 0.95), 0.05)
    p2 = max(min(p1 + min_detectable_effect, 0.95), 0.05)
    p_bar = (p1 + p2) / 2.0

    numerator = (
        z_alpha * math.sqrt(2 * p_bar * (1 - p_bar))
        + z_beta * math.sqrt(p1 * (1 - p1) + p2 * (1 - p2))
    ) ** 2
    denominator = (p1 - p2) ** 2
    if denominator <= 0:
        return 200
    n = math.ceil(numerator / denominator)
    return max(n, 50)


def run_pilot_evaluation(
    manifest_path: Path | str,
    sample_pairs: int = 3,
    showdown_dir: Path | str | None = None,
    p1_agent: BattleAgent | None = None,
    p2_agent: BattleAgent | None = None,
) -> PilotReport:
    """Run pilot evaluation across Protect variants and calibrate sample size and compute budget."""
    manifest = load_manifest(manifest_path)
    matchups = build_manifest_matchups(manifest)

    agent_a = p1_agent or HeuristicAgent("PilotHeuristicA")
    agent_b = p2_agent or HeuristicAgent("PilotHeuristicB")

    # Run pilot battles on a subset of matchups to calibrate timings and Protect metrics
    pilot_matchups = matchups[: min(len(matchups), 3)]

    tot_battles = 0
    tot_turns = 0
    tot_duration = 0.0
    tot_decisions = 0

    p16_protect_uses = 0
    p16_depletions = 0
    p16_battles = 0

    p8_protect_uses = 0
    p8_depletions = 0
    p8_battles = 0

    for m_idx, (_t1_id, t1_packed, _t2_id, t2_packed) in enumerate(pilot_matchups):
        for pair in range(sample_pairs):
            seed_base = 10000 + m_idx * 100 + pair * 10

            # 1. Gen 9 with standard Protect PP
            # Match A (t1 vs t2)
            res16_a = run_pilot_battle(
                p1_agent=agent_a,
                p2_agent=agent_b,
                format_id="gen9rulebreakprotect16",
                p1_team=t1_packed,
                p2_team=t2_packed,
                seed=(seed_base, seed_base + 1, seed_base + 2, seed_base + 3),
                showdown_dir=showdown_dir,
            )
            # Match B (t2 vs t1 - mirrored)
            res16_b = run_pilot_battle(
                p1_agent=agent_a,
                p2_agent=agent_b,
                format_id="gen9rulebreakprotect16",
                p1_team=t2_packed,
                p2_team=t1_packed,
                seed=(seed_base + 4, seed_base + 5, seed_base + 6, seed_base + 7),
                showdown_dir=showdown_dir,
            )

            p16_battles += 2
            p16_protect_uses += res16_a.protect_uses + res16_b.protect_uses
            if res16_a.protect_depleted:
                p16_depletions += 1
            if res16_b.protect_depleted:
                p16_depletions += 1

            # 2. The same Gen 9 rules with only Protect PP reduced
            # Match A (t1 vs t2)
            res8_a = run_pilot_battle(
                p1_agent=agent_a,
                p2_agent=agent_b,
                format_id="gen9rulebreakprotect8",
                p1_team=t1_packed,
                p2_team=t2_packed,
                seed=(seed_base, seed_base + 1, seed_base + 2, seed_base + 3),
                showdown_dir=showdown_dir,
            )
            # Match B (t2 vs t1 - mirrored)
            res8_b = run_pilot_battle(
                p1_agent=agent_a,
                p2_agent=agent_b,
                format_id="gen9rulebreakprotect8",
                p1_team=t2_packed,
                p2_team=t1_packed,
                seed=(seed_base + 4, seed_base + 5, seed_base + 6, seed_base + 7),
                showdown_dir=showdown_dir,
            )

            p8_battles += 2
            p8_protect_uses += res8_a.protect_uses + res8_b.protect_uses
            if res8_a.protect_depleted:
                p8_depletions += 1
            if res8_b.protect_depleted:
                p8_depletions += 1

            for r in (res16_a, res16_b, res8_a, res8_b):
                tot_battles += 1
                tot_turns += r.turns
                tot_duration += r.duration_seconds
                tot_decisions += r.p1_decisions + r.p2_decisions

    avg_turns = tot_turns / max(tot_battles, 1)
    avg_duration = tot_duration / max(tot_battles, 1)
    dps = tot_decisions / max(tot_duration, 0.001)
    avg_latency = (tot_duration / max(tot_turns, 1)) * 1000.0

    p16_use_rate = p16_protect_uses / max(p16_battles, 1)
    p8_use_rate = p8_protect_uses / max(p8_battles, 1)
    p16_dep_rate = p16_depletions / max(p16_battles, 1)
    p8_dep_rate = p8_depletions / max(p8_battles, 1)

    # Power analysis: calculate sample size required to resolve effect size with 80% power
    total_matchups = len(matchups)
    # Estimate required battles per variant:
    # Target of ~25 pairs (50 battles per matchup) yields 750 matches per variant
    # across 15 matchups, reliably detecting a difference in proportion of ~0.05-0.08.
    required_per_variant = calculate_sample_size(
        p_baseline=max(p8_dep_rate, 0.20), min_detectable_effect=0.08
    )
    # Convert required sample size across matchups to mirrored pairs per matchup
    rec_pairs = max(math.ceil(required_per_variant / max(total_matchups * 2, 1)), 10)
    # Clamp to a statistically robust range [10, 50]
    rec_pairs = min(max(rec_pairs, 10), 50)

    # Calculate total study battles across:
    # total_matchups * 2 (mirrored pair) * rec_pairs * 2 variants * 3 training seeds
    num_variants = 2
    num_seeds = 3
    est_total_matches = total_matchups * 2 * rec_pairs * num_variants * num_seeds
    # Buffer compute budget by 25% for setup, process initialization, and variance
    rec_budget_seconds = math.ceil(est_total_matches * avg_duration * 1.25)

    return PilotReport(
        sample_pairs=sample_pairs,
        total_pilot_battles=tot_battles,
        avg_turns=avg_turns,
        avg_duration_seconds=avg_duration,
        decisions_per_second=dps,
        avg_turn_latency_ms=avg_latency,
        protect_16_uses_per_match=p16_use_rate,
        protect_8_uses_per_match=p8_use_rate,
        protect_16_depletion_rate=p16_dep_rate,
        protect_8_depletion_rate=p8_dep_rate,
        matchups_count=total_matchups,
        recommended_pairs_per_matchup=rec_pairs,
        estimated_total_matches=est_total_matches,
        recommended_compute_budget_seconds=rec_budget_seconds,
    )


def update_spec_with_pilot(spec_path: Path | str, report: PilotReport) -> None:
    """Update experiments spec with calibrated pairs_per_matchup and compute_budget_seconds."""
    path = Path(spec_path)
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    readiness = data.get("readiness")
    if not isinstance(readiness, dict):
        raise ValueError(f"Spec {spec_path} is missing readiness object")

    readiness["pairs_per_matchup"] = report.recommended_pairs_per_matchup
    readiness["compute_budget_seconds"] = report.recommended_compute_budget_seconds

    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
