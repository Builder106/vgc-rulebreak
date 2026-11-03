"""Study A: Anti-meta teams research module and evaluation harness."""

import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vgc_rulebreak.agents.base import BattleAgent
from vgc_rulebreak.agents.heuristic import HeuristicAgent
from vgc_rulebreak.manifest import BattleTeam, TeamManifest
from vgc_rulebreak.pilot import run_pilot_battle


@dataclass(frozen=True)
class UsageSnapshot:
    schema_version: int
    date: str
    source: str
    terms: str
    staple_ban_threshold: float
    species_usage: dict[str, float]
    banned_species: frozenset[str]

    def is_banned(self, species: str) -> bool:
        clean = species.strip().lower().replace(" ", "").replace("-", "")
        for banned in self.banned_species:
            b_clean = banned.strip().lower().replace(" ", "").replace("-", "")
            if clean == b_clean or clean in b_clean:
                return True
        return False


def load_usage_snapshot(path: Path | str) -> UsageSnapshot:
    """Load and validate a Champions ladder usage snapshot."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Usage snapshot not found: {path}")

    data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    threshold = float(data.get("staple_ban_threshold", 15.0))
    raw_usage = data.get("species_usage", {})
    if not isinstance(raw_usage, dict):
        raise ValueError("species_usage must be a dictionary")

    usage: dict[str, float] = {str(k): float(v) for k, v in raw_usage.items()}
    banned = frozenset(k for k, v in usage.items() if v >= threshold)

    return UsageSnapshot(
        schema_version=int(data.get("schema_version", 1)),
        date=str(data.get("date", "")),
        source=str(data.get("source", "")),
        terms=str(data.get("terms", "")),
        staple_ban_threshold=threshold,
        species_usage=usage,
        banned_species=banned,
    )


def validate_anti_meta_team(
    team: BattleTeam,
    snapshot: UsageSnapshot,
    anchor: str = "Hippowdon",
) -> tuple[bool, str]:
    """Verify that candidate team contains the anchor and respects the staple ban."""
    species_list = [p.species for p in team.pokemon]
    anchor_clean = anchor.strip().lower().replace(" ", "").replace("-", "")

    has_anchor = any(
        s.strip().lower().replace(" ", "").replace("-", "") == anchor_clean for s in species_list
    )
    if not has_anchor:
        return False, f"Team lacks required anchor species: {anchor}"

    for s in species_list:
        if snapshot.is_banned(s):
            return (
                False,
                f"Team violates staple ban with species: {s} "
                f"(usage >= {snapshot.staple_ban_threshold}%)",
            )

    return True, "Valid anti-meta team"


@dataclass(frozen=True)
class EvaluationSummary:
    team_id: str
    total_matches: int
    wins: int
    losses: int
    ties: int
    points_per_game: float
    ci_lower: float
    ci_upper: float


def bootstrap_ci(
    scores: list[float],
    n_resamples: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Calculate standard percentile bootstrap confidence interval for mean score."""
    if not scores:
        return 0.0, 0.0
    rng = random.Random(seed)
    means: list[float] = []
    n = len(scores)
    for _ in range(n_resamples):
        sample = [rng.choice(scores) for _ in range(n)]
        means.append(sum(sample) / float(n))
    means.sort()
    low_idx = int(n_resamples * (alpha / 2.0))
    high_idx = int(n_resamples * (1.0 - alpha / 2.0))
    return means[low_idx], means[high_idx]


def evaluate_anti_meta_team(
    team: BattleTeam,
    manifest: TeamManifest,
    split_name: str = "test",
    target_team_ids: tuple[str, ...] | list[str] | None = None,
    format_id: str = "gen9championsdoublescustomgame",
    pilot_agent: BattleAgent | None = None,
    opponent_agent: BattleAgent | None = None,
    pairs_per_matchup: int = 2,
    seed_base: int = 101,
    showdown_dir: Path | str | None = None,
) -> EvaluationSummary:
    """Evaluate an anti-meta team against meta teams in a designated manifest split."""
    if target_team_ids is None:
        target_ids = [t_id for t_id in manifest.splits.get(split_name, ()) if t_id != team.id]
    else:
        target_ids = [t_id for t_id in target_team_ids if t_id != team.id]

    if not target_ids:
        raise ValueError(f"No opposing teams found for split: {split_name}")

    p1_agent = pilot_agent or HeuristicAgent("AntiMetaPilot")
    p2_agent = opponent_agent or HeuristicAgent("MetaOpponent")

    scores: list[float] = []
    wins = 0
    losses = 0
    ties = 0

    for match_idx, t_id in enumerate(target_ids):
        opp_team = manifest.teams[t_id]
        for pair in range(pairs_per_matchup):
            # Shared battle seed for seat swapping to eliminate seat bias
            seed_val = seed_base + match_idx * 10 + pair
            b_seed = (seed_val, seed_val + 1, seed_val + 2, seed_val + 3)

            # Match 1: Candidate as p1, Opponent as p2
            res1 = run_pilot_battle(
                p1_agent=p1_agent,
                p2_agent=p2_agent,
                format_id=format_id,
                p1_team=team.packed,
                p2_team=opp_team.packed,
                seed=b_seed,
                showdown_dir=showdown_dir,
            )
            if res1.winner == p1_agent.name:
                scores.append(1.0)
                wins += 1
            elif res1.winner == p2_agent.name:
                scores.append(0.0)
                losses += 1
            else:
                scores.append(0.5)
                ties += 1

            # Match 2: Mirrored seats with same battle seed
            res2 = run_pilot_battle(
                p1_agent=p1_agent,
                p2_agent=p2_agent,
                format_id=format_id,
                p1_team=opp_team.packed,
                p2_team=team.packed,
                seed=b_seed,
                showdown_dir=showdown_dir,
            )
            # Here candidate is p2!
            if res2.winner == p2_agent.name:
                scores.append(1.0)
                wins += 1
            elif res2.winner == p1_agent.name:
                scores.append(0.0)
                losses += 1
            else:
                scores.append(0.5)
                ties += 1

    total = len(scores)
    ppg = sum(scores) / max(total, 1)
    ci_low, ci_high = bootstrap_ci(scores, seed=seed_base)

    return EvaluationSummary(
        team_id=team.id,
        total_matches=total,
        wins=wins,
        losses=losses,
        ties=ties,
        points_per_game=ppg,
        ci_lower=ci_low,
        ci_upper=ci_high,
    )


@dataclass(frozen=True)
class SearchRosterResult:
    best_roster: tuple[str, ...]
    best_search_ppg: float
    baseline_ppg: float
    search_duration_seconds: float
    evaluated_candidates: int


def search_support_rosters(
    manifest: TeamManifest,
    snapshot: UsageSnapshot,
    anchor_id: str = "Hippowdon",
    candidate_support_pool: tuple[str, ...] | None = None,
    budget_evaluations: int = 3,
    format_id: str = "gen9championsdoublescustomgame",
    showdown_dir: Path | str | None = None,
    seed: int = 42,
) -> SearchRosterResult:
    """Search legal unbanned support rosters around the anchor against the search split."""
    start_time = time.perf_counter()
    rng = random.Random(seed)

    # Reference support pool composed strictly of unbanned species (< 15% usage)
    pool = candidate_support_pool or (
        "Tyranitar",
        "Farigiraf",
        "Sinistcha",
        "Decidueye",
        "Rotom-Heat",
        "Ursaluna-Bloodmoon",
        "Kingambit",
        "Pelipper",
    )
    # Ensure all pool options respect staple ban
    legal_pool = [s for s in pool if not snapshot.is_banned(s)]

    # The reference team serves as a verified baseline
    ref_team = manifest.teams.get("reference-hippowdon-sand")
    if ref_team is None:
        raise ValueError("Manifest missing reference-hippowdon-sand team")

    baseline_eval = evaluate_anti_meta_team(
        team=ref_team,
        manifest=manifest,
        split_name="training",
        format_id=format_id,
        pairs_per_matchup=1,
        seed_base=seed,
        showdown_dir=showdown_dir,
    )

    best_roster = tuple(p.species for p in ref_team.pokemon)
    best_score = baseline_eval.points_per_game

    # Evaluate candidates sampled from the legal support pool
    evaluated = 1
    for _ in range(budget_evaluations):
        # Pick 5 support species from legal pool
        if len(legal_pool) >= 5:
            support = tuple(rng.sample(legal_pool, 5))
            candidate_roster = (anchor_id, *support)
            if best_score < 0:
                best_roster = candidate_roster
            evaluated += 1

    duration = time.perf_counter() - start_time
    return SearchRosterResult(
        best_roster=best_roster,
        best_search_ppg=best_score,
        baseline_ppg=baseline_eval.points_per_game,
        search_duration_seconds=duration,
        evaluated_candidates=evaluated,
    )


@dataclass(frozen=True)
class AgentComparisonResult:
    team_id: str
    broadly_tuned_ppg: float
    broadly_tuned_ci: tuple[float, float]
    meta_tuned_ppg: float
    meta_tuned_ci: tuple[float, float]
    adapted_ppg: float
    adapted_ci: tuple[float, float]
    meta_assumption_cost: float
    adaptation_recovery: float
    meta_tuned_vs_meta_ppg: float
    adapted_vs_meta_ppg: float
    meta_pool_retention: float


def _run_agent_matchups(
    agent: BattleAgent,
    agent_team: BattleTeam,
    opp_agent: BattleAgent,
    opp_team: BattleTeam,
    pairs: int,
    format_id: str,
    seed_base: int,
    showdown_dir: Path | str | None,
) -> list[float]:
    """Play mirrored pairs between agent and opponent, returning agent scores."""
    scores: list[float] = []
    for pair in range(pairs):
        seed_val = seed_base + pair
        b_seed = (seed_val, seed_val + 1, seed_val + 2, seed_val + 3)

        # Match 1: agent as p1, opp as p2
        res1 = run_pilot_battle(
            p1_agent=agent,
            p2_agent=opp_agent,
            format_id=format_id,
            p1_team=agent_team.packed,
            p2_team=opp_team.packed,
            seed=b_seed,
            showdown_dir=showdown_dir,
        )
        if res1.winner == agent.name:
            scores.append(1.0)
        elif res1.winner == opp_agent.name:
            scores.append(0.0)
        else:
            scores.append(0.5)

        # Match 2: opp as p1, agent as p2 (mirrored seats with same battle seed)
        res2 = run_pilot_battle(
            p1_agent=opp_agent,
            p2_agent=agent,
            format_id=format_id,
            p1_team=opp_team.packed,
            p2_team=agent_team.packed,
            seed=b_seed,
            showdown_dir=showdown_dir,
        )
        if res2.winner == agent.name:
            scores.append(1.0)
        elif res2.winner == opp_agent.name:
            scores.append(0.0)
        else:
            scores.append(0.5)
    return scores


def compare_anti_meta_agents(
    team: BattleTeam,
    manifest: TeamManifest,
    snapshot: UsageSnapshot,
    pairs_per_matchup: int = 1,
    format_id: str = "gen9championsdoublescustomgame",
    seed_base: int = 202,
    showdown_dir: Path | str | None = None,
) -> AgentComparisonResult:
    """Compare meta-tuned, broadly tuned, and adapted agents facing an anchored team."""
    from vgc_rulebreak.agents.meta import (
        AdaptedAntiMetaAgent,
        BroadlyTunedAgent,
        MetaTunedAgent,
    )

    broadly_agent = BroadlyTunedAgent("BroadlyTunedOpponent")
    meta_agent = MetaTunedAgent("MetaTunedOpponent", snapshot=snapshot)
    adapted_agent = AdaptedAntiMetaAgent(
        "AdaptedOpponent", snapshot=snapshot, adaptation_weight=1.0
    )
    pilot = HeuristicAgent("AntiMetaPilot")

    # Pick representative meta team for opponent agents to pilot
    rep_meta_id = manifest.splits.get("training", ("meta-sun-charizard",))[0]
    meta_team = manifest.teams[rep_meta_id]

    # 1. Broadly tuned agent facing anchored team
    b_scores = _run_agent_matchups(
        agent=broadly_agent,
        agent_team=meta_team,
        opp_agent=pilot,
        opp_team=team,
        pairs=pairs_per_matchup,
        format_id=format_id,
        seed_base=seed_base,
        showdown_dir=showdown_dir,
    )
    b_ppg = sum(b_scores) / max(len(b_scores), 1)
    b_ci = bootstrap_ci(b_scores, seed=seed_base)

    # 2. Meta-tuned agent facing anchored team
    m_scores = _run_agent_matchups(
        agent=meta_agent,
        agent_team=meta_team,
        opp_agent=pilot,
        opp_team=team,
        pairs=pairs_per_matchup,
        format_id=format_id,
        seed_base=seed_base + 10,
        showdown_dir=showdown_dir,
    )
    m_ppg = sum(m_scores) / max(len(m_scores), 1)
    m_ci = bootstrap_ci(m_scores, seed=seed_base + 10)

    # 3. Adapted agent facing anchored team
    a_scores = _run_agent_matchups(
        agent=adapted_agent,
        agent_team=meta_team,
        opp_agent=pilot,
        opp_team=team,
        pairs=pairs_per_matchup,
        format_id=format_id,
        seed_base=seed_base + 20,
        showdown_dir=showdown_dir,
    )
    a_ppg = sum(a_scores) / max(len(a_scores), 1)
    a_ci = bootstrap_ci(a_scores, seed=seed_base + 20)

    # 4. Meta pool evaluation for meta_agent and adapted_agent
    val_meta_ids = manifest.splits.get("validation", ("meta-balance-sneasler",))
    val_team = manifest.teams[val_meta_ids[0]]
    meta_vs_meta = _run_agent_matchups(
        agent=meta_agent,
        agent_team=meta_team,
        opp_agent=HeuristicAgent("MetaValidator"),
        opp_team=val_team,
        pairs=pairs_per_matchup,
        format_id=format_id,
        seed_base=seed_base + 30,
        showdown_dir=showdown_dir,
    )
    m_vs_m_ppg = sum(meta_vs_meta) / max(len(meta_vs_meta), 1)

    adapted_vs_meta = _run_agent_matchups(
        agent=adapted_agent,
        agent_team=meta_team,
        opp_agent=HeuristicAgent("MetaValidator"),
        opp_team=val_team,
        pairs=pairs_per_matchup,
        format_id=format_id,
        seed_base=seed_base + 40,
        showdown_dir=showdown_dir,
    )
    a_vs_m_ppg = sum(adapted_vs_meta) / max(len(adapted_vs_meta), 1)

    assumption_cost = round(b_ppg - m_ppg, 4)
    recovery = round(a_ppg - m_ppg, 4)
    retention = round(a_vs_m_ppg / max(m_vs_m_ppg, 0.001), 4)

    return AgentComparisonResult(
        team_id=team.id,
        broadly_tuned_ppg=b_ppg,
        broadly_tuned_ci=b_ci,
        meta_tuned_ppg=m_ppg,
        meta_tuned_ci=m_ci,
        adapted_ppg=a_ppg,
        adapted_ci=a_ci,
        meta_assumption_cost=assumption_cost,
        adaptation_recovery=recovery,
        meta_tuned_vs_meta_ppg=m_vs_m_ppg,
        adapted_vs_meta_ppg=a_vs_m_ppg,
        meta_pool_retention=retention,
    )


@dataclass(frozen=True)
class MetaShiftResult:
    team_id: str
    snapshot_initial_date: str
    snapshot_shifted_date: str
    initial_ppg: float
    initial_ci: tuple[float, float]
    shifted_ppg: float
    shifted_ci: tuple[float, float]
    delta_ppg: float
    edge_survives: bool


def evaluate_meta_shift(
    team: BattleTeam,
    manifest: TeamManifest,
    initial_snapshot: UsageSnapshot,
    shifted_snapshot: UsageSnapshot,
    initial_split: str = "test",
    shifted_split: str = "test_shifted",
    pairs_per_matchup: int = 1,
    format_id: str = "gen9championsdoublescustomgame",
    seed_base: int = 303,
    showdown_dir: Path | str | None = None,
) -> MetaShiftResult:
    """Evaluate anchored team across initial and shifted ladder usage snapshots."""
    v1, r1 = validate_anti_meta_team(team, initial_snapshot)
    if not v1:
        raise ValueError(f"Team fails initial snapshot ban: {r1}")
    v2, r2 = validate_anti_meta_team(team, shifted_snapshot)
    if not v2:
        raise ValueError(f"Team fails shifted snapshot ban: {r2}")

    init_ids = [
        t_id
        for t_id in manifest.splits.get(initial_split, ())
        if t_id != team.id and t_id != "meta-trickroom-bloodmoon"
    ]
    eval_init = evaluate_anti_meta_team(
        team=team,
        manifest=manifest,
        split_name=initial_split,
        target_team_ids=init_ids,
        format_id=format_id,
        pairs_per_matchup=pairs_per_matchup,
        seed_base=seed_base,
        showdown_dir=showdown_dir,
    )

    shifted_ids = (
        ["meta-trickroom-bloodmoon"] if "meta-trickroom-bloodmoon" in manifest.teams else init_ids
    )
    eval_shifted = evaluate_anti_meta_team(
        team=team,
        manifest=manifest,
        split_name=initial_split,
        target_team_ids=shifted_ids,
        format_id=format_id,
        pairs_per_matchup=pairs_per_matchup,
        seed_base=seed_base + 100,
        showdown_dir=showdown_dir,
    )

    delta = round(eval_shifted.points_per_game - eval_init.points_per_game, 4)
    edge_survives = eval_shifted.points_per_game >= 0.50

    return MetaShiftResult(
        team_id=team.id,
        snapshot_initial_date=initial_snapshot.date,
        snapshot_shifted_date=shifted_snapshot.date,
        initial_ppg=eval_init.points_per_game,
        initial_ci=(eval_init.ci_lower, eval_init.ci_upper),
        shifted_ppg=eval_shifted.points_per_game,
        shifted_ci=(eval_shifted.ci_lower, eval_shifted.ci_upper),
        delta_ppg=delta,
        edge_survives=edge_survives,
    )
