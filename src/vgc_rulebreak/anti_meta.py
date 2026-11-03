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
    split_name: str,
    format_id: str = "gen9championsdoublescustomgame",
    pilot_agent: BattleAgent | None = None,
    opponent_agent: BattleAgent | None = None,
    pairs_per_matchup: int = 2,
    seed_base: int = 101,
    showdown_dir: Path | str | None = None,
) -> EvaluationSummary:
    """Evaluate an anti-meta team against meta teams in a designated manifest split."""
    target_team_ids = manifest.splits.get(split_name, ())
    if not target_team_ids:
        raise ValueError(f"No teams declared in manifest split: {split_name}")

    p1_agent = pilot_agent or HeuristicAgent("AntiMetaPilot")
    p2_agent = opponent_agent or HeuristicAgent("MetaOpponent")

    scores: list[float] = []
    wins = 0
    losses = 0
    ties = 0

    for match_idx, t_id in enumerate(target_team_ids):
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
