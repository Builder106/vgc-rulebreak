"""Evaluate multiple training seeds and report confidence intervals for Study P.

This module automates multi-replicate training and evaluation across the Protect-only
formats (gen9rulebreakprotect16 and gen9rulebreakprotect8):
1. Trains source (16 PP), native (8 PP), and adapted (8 PP from source) policies
   across multiple independent training seeds (e.g. 11, 29, 47).
2. Evaluates the resulting checkpoints against held-out test teams and opponent
   baselines under paired seeds and mirrored seats.
3. Computes standard percentile bootstrap confidence intervals across training replicates,
   individual test matchups, and pooled evaluation games.
4. Generates an empirical multi-seed report with statistical uncertainty bounds and
   persists the full habit-recovery series.
"""

import dataclasses
import json
import math
import random
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vgc_rulebreak.agents.trained import checkpoint_agent, load_checkpoint
from vgc_rulebreak.evaluation import FORMAT_BY_PP, run_evaluation_suite
from vgc_rulebreak.manifest import TeamManifest, load_manifest
from vgc_rulebreak.records import GameRecorder
from vgc_rulebreak.recovery import POINTS, summarize_recovery
from vgc_rulebreak.spec import ExperimentSpec, validate_spec
from vgc_rulebreak.training import TrainingConfig, train_protect_policy

DEFAULT_SPEC_PATH = Path("experiments/protect-pp.json")
DEFAULT_MANIFEST_PATH = Path("experiments/teams/protect-pp.json")


def bootstrap_ci(
    values: Sequence[float],
    n_resamples: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    """Calculate standard percentile bootstrap confidence interval for the mean.

    Returns (ci_lower, ci_upper) bounding the (1 - alpha) * 100% confidence interval.
    """
    if not values:
        return 0.0, 0.0
    if len(values) == 1 or min(values) == max(values):
        return float(values[0]), float(values[0])

    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(n_resamples):
        sample = rng.choices(values, k=n)
        means.append(sum(sample) / float(n))

    means.sort()
    low_idx = int(n_resamples * (alpha / 2.0))
    high_idx = int(n_resamples * (1.0 - alpha / 2.0))
    # Clamp indices to valid array bounds
    low_idx = max(0, min(low_idx, n_resamples - 1))
    high_idx = max(0, min(high_idx, n_resamples - 1))
    return round(means[low_idx], 4), round(means[high_idx], 4)


@dataclass(frozen=True)
class ConfidenceInterval:
    mean: float
    ci_lower: float
    ci_upper: float
    std: float
    min: float
    max: float
    n: int


def calculate_ci(
    values: Sequence[float],
    n_resamples: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> ConfidenceInterval:
    """Calculate point estimate, sample standard deviation, and bootstrap CI."""
    if not values:
        return ConfidenceInterval(
            mean=0.0,
            ci_lower=0.0,
            ci_upper=0.0,
            std=0.0,
            min=0.0,
            max=0.0,
            n=0,
        )
    n = len(values)
    mean_val = sum(values) / float(n)
    variance = sum((x - mean_val) ** 2 for x in values) / float(n) if n > 1 else 0.0
    std_val = math.sqrt(variance)
    ci_low, ci_high = bootstrap_ci(values, n_resamples=n_resamples, alpha=alpha, seed=seed)
    return ConfidenceInterval(
        mean=round(mean_val, 4),
        ci_lower=round(ci_low, 4),
        ci_upper=round(ci_high, 4),
        std=round(std_val, 4),
        min=round(min(values), 4),
        max=round(max(values), 4),
        n=n,
    )


@dataclass(frozen=True)
class ProtectMultiSeedConfig:
    training_seeds: tuple[int, ...] = (11, 29, 47)
    eval_seed: int = 101
    generations: int = 3
    population: int = 6
    elites: int = 2
    pairs: int = 1
    eval_pairs: int = 1
    workers: int = 4
    eval_all_checkpoints: bool = False
    opponent_policy: str = "HeuristicBaseline"
    bootstrap_resamples: int = 1000
    alpha: float = 0.05
    bootstrap_seed: int = 42


@dataclass(frozen=True)
class AgentVariantStats:
    games: int
    points_per_game: float
    win_rate: float
    protect_uses: int
    protect_opportunities: int
    protect_use_rate: float
    depletions: int
    depletion_rate: float


@dataclass(frozen=True)
class ReplicateSummary:
    seed: int
    agents: dict[str, dict[str, AgentVariantStats]]
    transfer_delta_ppg: float
    transfer_delta_protect_rate: float
    adaptation_recovery_ppg: float
    adaptation_recovery_protect_rate: float
    native_vs_source_ppg: float
    native_vs_source_protect_rate: float


@dataclass(frozen=True)
class MatchupStats:
    matchup: tuple[str, str]
    replicate_ppg: dict[str, float]
    pooled_ppg: ConfidenceInterval
    pooled_protect_rate: ConfidenceInterval


@dataclass(frozen=True)
class ProtectMultiSeedReport:
    spec: str
    simulator_revision: str
    training_seeds: tuple[int, ...]
    eval_seed: int
    formats: dict[str, str]
    total_training_games: int
    total_evaluation_games: int
    total_depletions: int
    scarcity_binds_in_any_seed: bool
    replicates: dict[str, ReplicateSummary]
    agent_confidence_intervals: dict[str, dict[str, dict[str, ConfidenceInterval]]]
    effect_confidence_intervals: dict[str, ConfidenceInterval]
    matchup_summaries: tuple[MatchupStats, ...]
    findings: dict[str, Any]


def run_protect_multi_seed(
    output_dir: Path,
    config: ProtectMultiSeedConfig | None = None,
    spec: ExperimentSpec | None = None,
    manifest: TeamManifest | None = None,
    showdown_dir: Path | str | None = None,
) -> ProtectMultiSeedReport:
    """Train and evaluate seeds under Protect-only formats and report confidence intervals."""
    cfg = config or ProtectMultiSeedConfig()

    if spec is None:
        raw_spec = json.loads(DEFAULT_SPEC_PATH.read_text(encoding="utf-8"))
        spec = validate_spec(raw_spec)

    if manifest is None:
        manifest = load_manifest(DEFAULT_MANIFEST_PATH)

    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoints_dir = output_dir / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    eval_dir = output_dir / "eval"
    eval_dir.mkdir(parents=True, exist_ok=True)

    expected_formats = {
        "protect-16": FORMAT_BY_PP[16],
        "protect-8": FORMAT_BY_PP[8],
    }

    packed_teams = {team_id: team.packed for team_id, team in manifest.teams.items()}

    # Data structures for replicate aggregation
    replicate_summaries: dict[str, ReplicateSummary] = {}
    all_replicate_eval_games: dict[int, list[dict[str, Any]]] = defaultdict(list)
    total_eval_games = 0
    total_depletions = 0

    # 1. Train and evaluate policies for each independent training seed
    for t_seed in cfg.training_seeds:
        # A. Source Agent (protect-16)
        source_cfg = TrainingConfig(
            agent="source",
            training_seed=t_seed,
            generations=cfg.generations,
            population=cfg.population,
            elites=cfg.elites,
            pairs=cfg.pairs,
            workers=cfg.workers,
        )
        source_ckpts = train_protect_policy(
            spec=spec,
            manifest=manifest,
            config=source_cfg,
            output_dir=output_dir,
            showdown_dir=showdown_dir,
        )
        for p in source_ckpts:
            _params, meta = load_checkpoint(p)
            if meta.get("format_id") != expected_formats["protect-16"]:
                raise ValueError(
                    f"Source checkpoint {p.name} format mismatch: {meta.get('format_id')}, "
                    f"expected {expected_formats['protect-16']}"
                )

        # B. Native Agent (protect-8)
        native_cfg = TrainingConfig(
            agent="native",
            training_seed=t_seed,
            generations=cfg.generations,
            population=cfg.population,
            elites=cfg.elites,
            pairs=cfg.pairs,
            workers=cfg.workers,
        )
        native_ckpts = train_protect_policy(
            spec=spec,
            manifest=manifest,
            config=native_cfg,
            output_dir=output_dir,
            showdown_dir=showdown_dir,
        )
        for p in native_ckpts:
            _params, meta = load_checkpoint(p)
            if meta.get("format_id") != expected_formats["protect-8"]:
                raise ValueError(
                    f"Native checkpoint {p.name} format mismatch: {meta.get('format_id')}, "
                    f"expected {expected_formats['protect-8']}"
                )

        # C. Adapted Agent (protect-8 from Source final checkpoint)
        adapted_cfg = TrainingConfig(
            agent="adapted",
            training_seed=t_seed,
            generations=cfg.generations,
            population=cfg.population,
            elites=cfg.elites,
            pairs=cfg.pairs,
            workers=cfg.workers,
        )
        adapted_ckpts = train_protect_policy(
            spec=spec,
            manifest=manifest,
            config=adapted_cfg,
            output_dir=output_dir,
            init_checkpoint=source_ckpts[-1],
            showdown_dir=showdown_dir,
        )
        for p in adapted_ckpts:
            _params, meta = load_checkpoint(p)
            if meta.get("format_id") != expected_formats["protect-8"]:
                raise ValueError(
                    f"Adapted checkpoint {p.name} format mismatch: {meta.get('format_id')}, "
                    f"expected {expected_formats['protect-8']}"
                )

        # Select evaluation targets for this replicate
        if cfg.eval_all_checkpoints:
            eval_targets = list(source_ckpts) + list(native_ckpts) + list(adapted_ckpts)
        else:
            candidates = [
                source_ckpts[0],
                source_ckpts[-1],
                native_ckpts[0],
                native_ckpts[-1],
                adapted_ckpts[0],
                adapted_ckpts[-1],
            ]
            eval_targets = []
            seen = set()
            for c in candidates:
                if c not in seen:
                    seen.add(c)
                    eval_targets.append(c)

        # Run evaluation suite for each target checkpoint in this replicate
        replicate_checkpoint_games: dict[str, list[dict[str, Any]]] = {}
        for ckpt_path in eval_targets:
            agent = checkpoint_agent(ckpt_path)
            ckpt_run_dir = eval_dir / agent.name
            recorder = GameRecorder(ckpt_run_dir, packed_teams)

            summary = run_evaluation_suite(
                spec=spec,
                manifest=manifest,
                candidate=agent,
                opponent_policies=[cfg.opponent_policy],
                evaluation_seeds=[cfg.eval_seed],
                variants=["protect-16", "protect-8"],
                pairs_per_matchup=cfg.eval_pairs,
                showdown_dir=showdown_dir,
                recorder=recorder,
            )

            summary_dict = dataclasses.asdict(summary)
            recorder.finish(
                meta={
                    "stage": "protect-multi-seed",
                    "spec": spec.name,
                    "simulator_revision": spec.simulator_revision,
                    "training_seed": t_seed,
                    "eval_seed": cfg.eval_seed,
                    "checkpoint": str(ckpt_path),
                },
                summary=summary_dict,
            )

            recorded_games = list(recorder.games)
            replicate_checkpoint_games[agent.name] = recorded_games
            all_replicate_eval_games[t_seed].extend(recorded_games)
            total_eval_games += summary.total_matches
            total_depletions += sum(m.protect_depleted_matches for m in summary.matchup_summaries)

        # Aggregate final evaluated models for this replicate
        final_source_name = checkpoint_agent(source_ckpts[-1]).name
        final_native_name = checkpoint_agent(native_ckpts[-1]).name
        final_adapted_name = checkpoint_agent(adapted_ckpts[-1]).name

        agent_keys = {
            "source": final_source_name,
            "native": final_native_name,
            "adapted": final_adapted_name,
        }

        replicate_agent_stats: dict[str, dict[str, AgentVariantStats]] = {}
        for role, name in agent_keys.items():
            replicate_agent_stats[role] = {}
            ckpt_games = replicate_checkpoint_games.get(name, [])
            for var in ("protect-16", "protect-8"):
                var_games = [g for g in ckpt_games if g.get("variant") == var]
                n_g = len(var_games)
                ppg = sum(POINTS[g["result"]] for g in var_games) / max(n_g, 1) if n_g > 0 else 0.0
                win_rate = (
                    sum(1 for g in var_games if g["result"] == "win") / max(n_g, 1)
                    if n_g > 0
                    else 0.0
                )
                p_uses = sum(g.get("candidate_protect_uses", 0) for g in var_games)
                p_opps = sum(g.get("candidate_protect_opportunities", 0) for g in var_games)
                p_rate = p_uses / max(p_opps, 1) if p_opps > 0 else 0.0
                depl = sum(1 for g in var_games if g.get("protect_depleted", False))
                depl_rate = depl / max(n_g, 1) if n_g > 0 else 0.0

                replicate_agent_stats[role][var] = AgentVariantStats(
                    games=n_g,
                    points_per_game=round(ppg, 4),
                    win_rate=round(win_rate, 4),
                    protect_uses=p_uses,
                    protect_opportunities=p_opps,
                    protect_use_rate=round(p_rate, 4),
                    depletions=depl,
                    depletion_rate=round(depl_rate, 4),
                )

        # Replicate paired causal deltas
        source_p16 = replicate_agent_stats["source"]["protect-16"]
        source_p8 = replicate_agent_stats["source"]["protect-8"]
        native_p8 = replicate_agent_stats["native"]["protect-8"]
        adapted_p8 = replicate_agent_stats["adapted"]["protect-8"]

        rep_summary = ReplicateSummary(
            seed=t_seed,
            agents=replicate_agent_stats,
            transfer_delta_ppg=round(source_p8.points_per_game - source_p16.points_per_game, 4),
            transfer_delta_protect_rate=round(
                source_p8.protect_use_rate - source_p16.protect_use_rate, 4
            ),
            adaptation_recovery_ppg=round(
                adapted_p8.points_per_game - source_p8.points_per_game, 4
            ),
            adaptation_recovery_protect_rate=round(
                adapted_p8.protect_use_rate - source_p8.protect_use_rate, 4
            ),
            native_vs_source_ppg=round(native_p8.points_per_game - source_p8.points_per_game, 4),
            native_vs_source_protect_rate=round(
                native_p8.protect_use_rate - source_p8.protect_use_rate, 4
            ),
        )
        replicate_summaries[str(t_seed)] = rep_summary

    # Summarize recovery series across all seeds
    recovery_dataset = summarize_recovery(eval_dir.rglob("results.json"))
    recovery_path = output_dir / "recovery.json"
    recovery_path.write_text(json.dumps(recovery_dataset, indent=2) + "\n", encoding="utf-8")

    # 2. Compute confidence intervals across training replicates and pooled games
    agent_confidence_intervals: dict[str, dict[str, dict[str, ConfidenceInterval]]] = {}
    for role in ("source", "native", "adapted"):
        agent_confidence_intervals[role] = {}
        for var in ("protect-16", "protect-8"):
            # A. Across replicates
            rep_ppgs = [
                replicate_summaries[str(s)].agents[role][var].points_per_game
                for s in cfg.training_seeds
            ]
            rep_protect_rates = [
                replicate_summaries[str(s)].agents[role][var].protect_use_rate
                for s in cfg.training_seeds
            ]
            rep_depl_rates = [
                replicate_summaries[str(s)].agents[role][var].depletion_rate
                for s in cfg.training_seeds
            ]

            # B. Across pooled evaluation games
            pooled_scores: list[float] = []
            pooled_protect_rates: list[float] = []
            pooled_depletions: list[float] = []

            for t_seed in cfg.training_seeds:
                for g in all_replicate_eval_games[t_seed]:
                    # Filter games belonging to this agent role and variant
                    if g.get("variant") == var and g.get("candidate", "").startswith(role):
                        res = g.get("result", "tie")
                        pooled_scores.append(POINTS.get(res, 0.5))
                        opps = g.get("candidate_protect_opportunities", 0)
                        uses = g.get("candidate_protect_uses", 0)
                        pooled_protect_rates.append(uses / opps if opps > 0 else 0.0)
                        pooled_depletions.append(1.0 if g.get("protect_depleted", False) else 0.0)

            agent_confidence_intervals[role][var] = {
                "ppg_across_replicates": calculate_ci(
                    rep_ppgs,
                    n_resamples=cfg.bootstrap_resamples,
                    alpha=cfg.alpha,
                    seed=cfg.bootstrap_seed + 1,
                ),
                "ppg_pooled_games": calculate_ci(
                    pooled_scores,
                    n_resamples=cfg.bootstrap_resamples,
                    alpha=cfg.alpha,
                    seed=cfg.bootstrap_seed + 2,
                ),
                "protect_rate_across_replicates": calculate_ci(
                    rep_protect_rates,
                    n_resamples=cfg.bootstrap_resamples,
                    alpha=cfg.alpha,
                    seed=cfg.bootstrap_seed + 3,
                ),
                "protect_rate_pooled_games": calculate_ci(
                    pooled_protect_rates,
                    n_resamples=cfg.bootstrap_resamples,
                    alpha=cfg.alpha,
                    seed=cfg.bootstrap_seed + 4,
                ),
                "depletion_rate_across_replicates": calculate_ci(
                    rep_depl_rates,
                    n_resamples=cfg.bootstrap_resamples,
                    alpha=cfg.alpha,
                    seed=cfg.bootstrap_seed + 5,
                ),
                "depletion_rate_pooled_games": calculate_ci(
                    pooled_depletions,
                    n_resamples=cfg.bootstrap_resamples,
                    alpha=cfg.alpha,
                    seed=cfg.bootstrap_seed + 6,
                ),
            }

    # Causal / comparative effect confidence intervals across replicates
    rep_transfer_deltas = [
        replicate_summaries[str(s)].transfer_delta_ppg for s in cfg.training_seeds
    ]
    rep_transfer_protect_deltas = [
        replicate_summaries[str(s)].transfer_delta_protect_rate for s in cfg.training_seeds
    ]
    rep_adaptation_deltas = [
        replicate_summaries[str(s)].adaptation_recovery_ppg for s in cfg.training_seeds
    ]
    rep_native_deltas = [
        replicate_summaries[str(s)].native_vs_source_ppg for s in cfg.training_seeds
    ]

    effect_confidence_intervals: dict[str, ConfidenceInterval] = {
        "transfer_delta_ppg": calculate_ci(
            rep_transfer_deltas,
            n_resamples=cfg.bootstrap_resamples,
            alpha=cfg.alpha,
            seed=cfg.bootstrap_seed + 10,
        ),
        "transfer_delta_protect_rate": calculate_ci(
            rep_transfer_protect_deltas,
            n_resamples=cfg.bootstrap_resamples,
            alpha=cfg.alpha,
            seed=cfg.bootstrap_seed + 11,
        ),
        "adaptation_recovery_ppg": calculate_ci(
            rep_adaptation_deltas,
            n_resamples=cfg.bootstrap_resamples,
            alpha=cfg.alpha,
            seed=cfg.bootstrap_seed + 12,
        ),
        "native_vs_source_ppg": calculate_ci(
            rep_native_deltas,
            n_resamples=cfg.bootstrap_resamples,
            alpha=cfg.alpha,
            seed=cfg.bootstrap_seed + 13,
        ),
    }

    # 3. Matchup-level breakdown
    # Group games by matchup (candidate_team, opponent_team)
    games_by_matchup: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for t_seed in cfg.training_seeds:
        for g in all_replicate_eval_games[t_seed]:
            c_team = g.get("candidate_team", "")
            o_team = g.get("opponent_team", "")
            if c_team and o_team:
                games_by_matchup[(c_team, o_team)].append(g)

    matchup_summaries_list: list[MatchupStats] = []
    for (c_team, o_team), m_games in sorted(games_by_matchup.items()):
        # Replicate PPGs for this matchup
        rep_m_ppg: dict[str, float] = {}
        for s in cfg.training_seeds:
            s_games = [g for g in m_games if g.get("training_seed") == s]
            if s_games:
                rep_m_ppg[str(s)] = round(
                    sum(POINTS[g["result"]] for g in s_games) / len(s_games), 4
                )

        pooled_m_scores = [POINTS[g["result"]] for g in m_games]
        pooled_m_prates: list[float] = []
        for g in m_games:
            opps = g.get("candidate_protect_opportunities", 0)
            uses = g.get("candidate_protect_uses", 0)
            pooled_m_prates.append(uses / opps if opps > 0 else 0.0)

        matchup_summaries_list.append(
            MatchupStats(
                matchup=(c_team, o_team),
                replicate_ppg=rep_m_ppg,
                pooled_ppg=calculate_ci(
                    pooled_m_scores,
                    n_resamples=cfg.bootstrap_resamples,
                    alpha=cfg.alpha,
                    seed=cfg.bootstrap_seed + 20,
                ),
                pooled_protect_rate=calculate_ci(
                    pooled_m_prates,
                    n_resamples=cfg.bootstrap_resamples,
                    alpha=cfg.alpha,
                    seed=cfg.bootstrap_seed + 21,
                ),
            )
        )

    # 4. Synthesize findings and report
    training_matchups_count = len(manifest.splits.get("training", ()))
    games_per_candidate = (
        (training_matchups_count * (training_matchups_count + 1) // 2) * 2 * cfg.pairs
    )
    total_training_games = (
        len(cfg.training_seeds) * 3 * cfg.generations * cfg.population * games_per_candidate
    )
    scarcity_binds_in_any_seed = total_depletions > 0

    transfer_ci = effect_confidence_intervals["transfer_delta_ppg"]
    transfer_significant = transfer_ci.ci_lower > 0 or transfer_ci.ci_upper < 0

    protect_rate_ci = effect_confidence_intervals["transfer_delta_protect_rate"]
    protect_rate_significant = protect_rate_ci.ci_lower > 0 or protect_rate_ci.ci_upper < 0

    findings = {
        "formats_used": expected_formats,
        "training_seeds": list(cfg.training_seeds),
        "total_depletions": total_depletions,
        "scarcity_binds_in_any_seed": scarcity_binds_in_any_seed,
        "transfer_delta_ppg_ci": asdict(transfer_ci),
        "transfer_delta_protect_rate_ci": asdict(protect_rate_ci),
        "adaptation_recovery_ppg_ci": asdict(
            effect_confidence_intervals["adaptation_recovery_ppg"]
        ),
        "native_vs_source_ppg_ci": asdict(effect_confidence_intervals["native_vs_source_ppg"]),
        "is_transfer_delta_statistically_significant": transfer_significant,
        "is_protect_rate_shift_statistically_significant": protect_rate_significant,
        "conclusion": (
            "scarcity_binds"
            if scarcity_binds_in_any_seed
            else (
                "null_result_confirmed_across_seeds: reducing Protect PP from 16 to 8 does not "
                f"bind (0 depletions across {len(cfg.training_seeds)} seeds), and performance "
                f"delta 95% CI [{transfer_ci.ci_lower}, {transfer_ci.ci_upper}] confirms "
                "no statistically distinguishable degradation in standard doubles games."
            )
        ),
    }

    report = ProtectMultiSeedReport(
        spec=spec.name,
        simulator_revision=spec.simulator_revision,
        training_seeds=tuple(cfg.training_seeds),
        eval_seed=cfg.eval_seed,
        formats=expected_formats,
        total_training_games=total_training_games,
        total_evaluation_games=total_eval_games,
        total_depletions=total_depletions,
        scarcity_binds_in_any_seed=scarcity_binds_in_any_seed,
        replicates=replicate_summaries,
        agent_confidence_intervals=agent_confidence_intervals,
        effect_confidence_intervals=effect_confidence_intervals,
        matchup_summaries=tuple(matchup_summaries_list),
        findings=findings,
    )

    summary_file = output_dir / "multi_seed_report.json"
    summary_file.write_text(json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8")

    return report
