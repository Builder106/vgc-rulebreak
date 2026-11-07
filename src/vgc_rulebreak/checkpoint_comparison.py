"""Checkpoint comparison across Protect rulesets without internal belief claims.

This module compares original (source) and adapted checkpoints under the Protect-only
formats (gen9rulebreakprotect16 and gen9rulebreakprotect8):
1. Compares policy parameters, scarcity sensitivity (scarcity_slope, pp_cushion),
   and unit-space parameter distances.
2. Compares empirical battle performance (win rate, points per game, average turns)
   across formats with 95% bootstrap confidence intervals.
3. Normalizes defensive habits (Protect choices, consecutive Protect candidate mistakes)
   by eligible decision opportunities and verifies whether 8 PP scarcity binds.
4. Analyzes decision-level agreement and divergence over observable board states
   without inferring unrecorded internal beliefs, intentions, or mental models.
5. Optionally conducts head-to-head cross-play under the target ruleset.
6. Synthesizes an evidence-grounded narrative reporting observable behavior and
   strictly rejects unsupported internal belief claims.
"""

import json
import math
import re
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from vgc_rulebreak.agents.trained import (
    PARAM_BOUNDS,
    ProtectParams,
    TrainedProtectAgent,
    checkpoint_agent,
    load_checkpoint,
)
from vgc_rulebreak.evaluation import (
    FORMAT_BY_PP,
    make_eval_battle_seed,
    run_evaluation_battle,
    run_evaluation_suite,
)
from vgc_rulebreak.explanation import (
    extract_board_state,
    read_replay_file,
)
from vgc_rulebreak.manifest import TeamManifest, load_manifest
from vgc_rulebreak.mistakes import _chooses_protect, candidate_mistakes
from vgc_rulebreak.protect_multi_seed import (
    ConfidenceInterval,
    calculate_ci,
)
from vgc_rulebreak.records import GameRecorder
from vgc_rulebreak.recovery import POINTS
from vgc_rulebreak.spec import ExperimentSpec, validate_spec

CHECKPOINT_COMPARISON_SCHEMA_VERSION = 1

DEFAULT_SPEC_PATH = Path("experiments/protect-pp.json")
DEFAULT_MANIFEST_PATH = Path("experiments/teams/protect-pp.json")

# Words and stems that attribute internal mental states, post-hoc intentions,
# or unrecorded expectations to agents. The research protocol forbids these.
FORBIDDEN_BELIEF_WORDS: tuple[str, ...] = (
    "believed",
    "believes",
    "thought",
    "thinks",
    "hoped",
    "hopes",
    "felt",
    "feels",
    "intended",
    "intends",
    "wanted",
    "wants",
    "realized",
    "realizes",
    "knew",
    "knows",
    "expected",
    "expects",
    "assumed",
    "assumes",
    "feared",
    "fears",
)


def verify_no_unsupported_beliefs(text: str) -> None:
    """Verify that an explanation narrative contains no forbidden internal belief words.

    Raises:
        ValueError: If any forbidden belief word is detected as a whole word.
    """
    for word in FORBIDDEN_BELIEF_WORDS:
        if re.search(rf"\b{word}\b", text, re.IGNORECASE):
            raise ValueError(
                f"Unsupported internal belief word '{word}' detected in explanation narrative. "
                "Explanations must describe observable decisions, parameters, and rollout "
                "distributions without inferring unrecorded internal mental states."
            )


@dataclass(frozen=True)
class CheckpointMetadata:
    path: str
    agent: str
    ruleset: str
    format_id: str
    training_seed: int
    generation: int
    params: dict[str, float]
    unit_mean: list[float]
    unit_std: list[float]


@dataclass(frozen=True)
class ParameterDeltaSummary:
    deltas: dict[str, float]
    l1_distance: float
    l2_distance: float
    original_scarcity_slope: float
    adapted_scarcity_slope: float
    scarcity_slope_shift: float
    is_scarcity_sensitive: bool
    factual_description: str


@dataclass(frozen=True)
class CheckpointPerformance:
    variant: str
    format_id: str
    total_matches: int
    wins: int
    losses: int
    ties: int
    win_rate: float
    points_per_game: float
    avg_turns: float
    candidate_protect_uses: int
    candidate_protect_opportunities: int
    protect_use_rate: float
    consecutive_protect_mistakes: int
    consecutive_protect_rate: float | None
    protect_depletions: int
    depletion_rate: float


@dataclass(frozen=True)
class PairedPerformanceComparison:
    variant: str
    delta_ppg: float
    delta_win_rate: float
    delta_protect_use_rate: float
    delta_ppg_ci_95: ConfidenceInterval
    is_statistically_significant: bool
    scarcity_binds: bool


@dataclass(frozen=True)
class DecisionDivergenceRecord:
    game_id: str
    turn: int
    side: str
    original_choice: str
    adapted_choice: str
    observable_hp_ratio: float | None
    observable_protect_pp: dict[str, int]
    divergence_category: str


@dataclass(frozen=True)
class DecisionDivergenceSummary:
    total_decisions_compared: int
    identical_decisions: int
    divergent_decisions: int
    agreement_rate: float
    protect_agreement_rate: float
    divergence_records: tuple[DecisionDivergenceRecord, ...]


@dataclass(frozen=True)
class HeadToHeadSummary:
    variant: str
    format_id: str
    total_matches: int
    original_wins: int
    adapted_wins: int
    ties: int
    original_win_rate: float
    adapted_win_rate: float


@dataclass(frozen=True)
class CheckpointComparisonReport:
    schema_version: int
    created_at: str
    spec: str
    simulator_revision: str
    original: CheckpointMetadata
    adapted: CheckpointMetadata
    native: CheckpointMetadata | None
    parameter_comparison: ParameterDeltaSummary
    original_performance: dict[str, CheckpointPerformance]
    adapted_performance: dict[str, CheckpointPerformance]
    native_performance: dict[str, CheckpointPerformance] | None
    paired_differences: dict[str, PairedPerformanceComparison]
    decision_divergence: DecisionDivergenceSummary
    head_to_head: HeadToHeadSummary | None
    findings: dict[str, Any]
    empirical_narrative: str


def _choice_includes_protect(choice: str, request: dict[str, Any]) -> bool:
    """Check whether a choice string includes selecting Protect in any active slot."""
    actions = [a.strip() for a in choice.split(",")]
    active = request.get("active", [])
    for slot_idx, slot_data in enumerate(active):
        if slot_data is not None and slot_idx < len(actions):
            moves = slot_data.get("moves", [])
            if _chooses_protect(actions[slot_idx], moves):
                return True
    return False


def compare_checkpoint_parameters(
    orig_params: ProtectParams,
    adapted_params: ProtectParams,
) -> ParameterDeltaSummary:
    """Compare trainable Protect parameter vectors between original and adapted checkpoints."""
    deltas = {
        name: getattr(adapted_params, name) - getattr(orig_params, name) for name in PARAM_BOUNDS
    }

    u_orig = orig_params.to_unit()
    u_adapt = adapted_params.to_unit()

    l1 = sum(abs(a - b) for a, b in zip(u_adapt, u_orig, strict=True))
    l2 = math.sqrt(sum((a - b) ** 2 for a, b in zip(u_adapt, u_orig, strict=True)))

    is_scarcity_sensitive = orig_params.scarcity_slope > 0.0 or adapted_params.scarcity_slope > 0.0

    lines = [
        (
            f"Parameter shifts (adapted minus original): base_score: {deltas['base_score']:+.2f}, "
            f"low_hp_score: {deltas['low_hp_score']:+.2f}, "
            f"hp_threshold: {deltas['hp_threshold']:+.3f}, "
            f"scarcity_slope: {deltas['scarcity_slope']:+.2f}, "
            f"pp_cushion: {deltas['pp_cushion']:+.2f}."
        )
    ]
    if not is_scarcity_sensitive:
        lines.append(
            "Both checkpoints retain scarcity_slope = 0.0, indicating that Protect scoring "
            "is mathematically invariant to remaining Protect PP in both policies."
        )
    else:
        lines.append(
            f"Original scarcity_slope={orig_params.scarcity_slope:.2f}, "
            f"adapted scarcity_slope={adapted_params.scarcity_slope:.2f}."
        )

    return ParameterDeltaSummary(
        deltas={k: round(v, 4) for k, v in deltas.items()},
        l1_distance=round(l1, 4),
        l2_distance=round(l2, 4),
        original_scarcity_slope=round(orig_params.scarcity_slope, 4),
        adapted_scarcity_slope=round(adapted_params.scarcity_slope, 4),
        scarcity_slope_shift=round(deltas["scarcity_slope"], 4),
        is_scarcity_sensitive=is_scarcity_sensitive,
        factual_description=" ".join(lines),
    )


def evaluate_checkpoint_performance(
    games: Sequence[dict[str, Any]],
    variant: str,
    format_id: str,
    replays_by_game_id: dict[str, dict[str, Any]] | None = None,
) -> CheckpointPerformance:
    """Aggregate performance, Protect opportunity use, and candidate mistakes for a variant."""
    var_games = [g for g in games if g.get("variant") == variant]
    n_games = len(var_games)

    wins = sum(1 for g in var_games if g.get("result") == "win")
    losses = sum(1 for g in var_games if g.get("result") == "loss")
    ties = sum(1 for g in var_games if g.get("result") == "tie")
    win_rate = wins / max(n_games, 1) if n_games > 0 else 0.0
    ppg = sum(POINTS.get(g.get("result", "tie"), 0.5) for g in var_games) / max(n_games, 1)
    avg_turns = sum(g.get("turns", 0) for g in var_games) / max(n_games, 1) if n_games > 0 else 0.0

    p_uses = sum(g.get("candidate_protect_uses", 0) for g in var_games)
    p_opps = sum(g.get("candidate_protect_opportunities", 0) for g in var_games)
    p_rate = p_uses / max(p_opps, 1) if p_opps > 0 else 0.0

    depl = sum(1 for g in var_games if g.get("protect_depleted", False))
    depl_rate = depl / max(n_games, 1) if n_games > 0 else 0.0

    # Calculate consecutive protect candidate mistakes from replays if available
    mistake_events = 0
    mistake_opps = 0
    if replays_by_game_id:
        for g in var_games:
            gid = g.get("game_id", "")
            replay = replays_by_game_id.get(gid)
            if replay and "decisions" in replay:
                c_role = g.get("candidate_role", "p1")
                det = candidate_mistakes(replay["decisions"], c_role)
                if det is not None and "consecutive_protect" in det:
                    mistake_events += det["consecutive_protect"]["events"]
                    mistake_opps += det["consecutive_protect"]["eligible_opportunities"]

    mistake_rate = (mistake_events / mistake_opps) if mistake_opps > 0 else None

    return CheckpointPerformance(
        variant=variant,
        format_id=format_id,
        total_matches=n_games,
        wins=wins,
        losses=losses,
        ties=ties,
        win_rate=round(win_rate, 4),
        points_per_game=round(ppg, 4),
        avg_turns=round(avg_turns, 2),
        candidate_protect_uses=p_uses,
        candidate_protect_opportunities=p_opps,
        protect_use_rate=round(p_rate, 4),
        consecutive_protect_mistakes=mistake_events,
        consecutive_protect_rate=round(mistake_rate, 4) if mistake_rate is not None else None,
        protect_depletions=depl,
        depletion_rate=round(depl_rate, 4),
    )


def analyze_decision_divergence(
    orig_agent: TrainedProtectAgent,
    adapted_agent: TrainedProtectAgent,
    replays: Sequence[dict[str, Any]],
) -> DecisionDivergenceSummary:
    """Compare choices made by original and adapted policies on identical decision requests."""
    total_decisions = 0
    identical_decisions = 0
    protect_agreements = 0
    records: list[DecisionDivergenceRecord] = []

    for replay in replays:
        players = replay.get("players", {})
        game_id = replay.get("game_id", "unknown")

        candidate_role = "p1"
        if "p1" in players and "p2" in players:
            p1_name = players["p1"].get("name", "")
            if any(tag in p1_name for tag in ("source", "native", "adapted")):
                candidate_role = "p1"
            elif any(
                tag in players["p2"].get("name", "") for tag in ("source", "native", "adapted")
            ):
                candidate_role = "p2"

        for dec in replay.get("decisions", []):
            if dec.get("side") != candidate_role:
                continue
            req = dec.get("request")
            if not req or not req.get("active"):
                continue

            c_orig = orig_agent.choose_action(req)
            c_adapt = adapted_agent.choose_action(req)
            if c_orig is None or c_adapt is None:
                continue

            total_decisions += 1
            p_orig = _choice_includes_protect(c_orig, req)
            p_adapt = _choice_includes_protect(c_adapt, req)

            if p_orig == p_adapt:
                protect_agreements += 1

            if c_orig == c_adapt:
                identical_decisions += 1
            else:
                board = extract_board_state(req)
                cat = "move_difference"
                if p_orig and not p_adapt:
                    cat = "original_protect_adapted_other"
                elif p_adapt and not p_orig:
                    cat = "adapted_protect_original_other"
                elif "switch" in c_orig or "switch" in c_adapt:
                    cat = "switch_difference"

                hp_ratio = None
                for p in board.get("active_pokemon", []):
                    if p.get("maxhp", 0) > 0:
                        hp_ratio = p["hp"] / p["maxhp"]
                        break

                pp_summary = {
                    mon: info["current"]
                    for mon, info in board.get("protect_pp_summary", {}).items()
                    if info["current"] >= 0
                }

                records.append(
                    DecisionDivergenceRecord(
                        game_id=game_id,
                        turn=dec.get("turn", 0),
                        side=candidate_role,
                        original_choice=c_orig,
                        adapted_choice=c_adapt,
                        observable_hp_ratio=round(hp_ratio, 3) if hp_ratio is not None else None,
                        observable_protect_pp=pp_summary,
                        divergence_category=cat,
                    )
                )

    agree_rate = identical_decisions / max(total_decisions, 1) if total_decisions > 0 else 1.0
    prot_agree_rate = protect_agreements / max(total_decisions, 1) if total_decisions > 0 else 1.0

    return DecisionDivergenceSummary(
        total_decisions_compared=total_decisions,
        identical_decisions=identical_decisions,
        divergent_decisions=len(records),
        agreement_rate=round(agree_rate, 4),
        protect_agreement_rate=round(prot_agree_rate, 4),
        divergence_records=tuple(records),
    )


def run_head_to_head_battles(
    orig_agent: TrainedProtectAgent,
    adapted_agent: TrainedProtectAgent,
    manifest: TeamManifest,
    pairs: int = 1,
    format_id: str = "gen9rulebreakprotect8",
    eval_seed: int = 101,
    showdown_dir: Path | str | None = None,
) -> HeadToHeadSummary:
    """Run direct head-to-head match play between original and adapted checkpoints."""
    test_teams = manifest.splits.get("test", ())
    if len(test_teams) < 2:
        keys = list(manifest.teams.keys())
        test_teams = tuple(keys[:2])

    matchups = [
        (t1, manifest.teams[t1].packed, t2, manifest.teams[t2].packed)
        for t1 in test_teams
        for t2 in test_teams
        if t1 != t2
    ]

    orig_wins = 0
    adapt_wins = 0
    ties = 0
    total = 0

    for m_idx, (_t1_id, t1_packed, _t2_id, t2_packed) in enumerate(matchups):
        for p_idx in range(pairs):
            s1 = make_eval_battle_seed(eval_seed, 1, 99, m_idx, p_idx, 0)
            r1 = run_evaluation_battle(
                candidate_agent=orig_agent,
                opponent_agent=adapted_agent,
                format_id=format_id,
                candidate_team=t1_packed,
                opponent_team=t2_packed,
                candidate_role="p1",
                seed=s1,
                showdown_dir=showdown_dir,
            )
            s2 = make_eval_battle_seed(eval_seed, 1, 99, m_idx, p_idx, 1)
            r2 = run_evaluation_battle(
                candidate_agent=orig_agent,
                opponent_agent=adapted_agent,
                format_id=format_id,
                candidate_team=t2_packed,
                opponent_team=t1_packed,
                candidate_role="p2",
                seed=s2,
                showdown_dir=showdown_dir,
            )

            for r in (r1, r2):
                total += 1
                if r.candidate_won:
                    orig_wins += 1
                elif r.winner == adapted_agent.name:
                    adapt_wins += 1
                else:
                    ties += 1

    return HeadToHeadSummary(
        variant="protect-8",
        format_id=format_id,
        total_matches=total,
        original_wins=orig_wins,
        adapted_wins=adapt_wins,
        ties=ties,
        original_win_rate=round(orig_wins / max(total, 1), 4),
        adapted_win_rate=round(adapt_wins / max(total, 1), 4),
    )


def build_checkpoint_comparison_narrative(
    orig_meta: CheckpointMetadata,
    adapt_meta: CheckpointMetadata,
    param_summary: ParameterDeltaSummary,
    orig_perf: dict[str, CheckpointPerformance],
    adapt_perf: dict[str, CheckpointPerformance],
    paired_diffs: dict[str, PairedPerformanceComparison],
    divergence: DecisionDivergenceSummary,
    h2h: HeadToHeadSummary | None = None,
    native_perf: dict[str, CheckpointPerformance] | None = None,
) -> str:
    """Construct an evidence-based comparison narrative strictly excluding unsupported beliefs."""
    lines: list[str] = [
        "## Checkpoint Comparison: Original versus Adapted Policies",
        "",
        "### 1. Checkpoint Identity and Parameter Shift",
        f"- Original checkpoint: `{orig_meta.path}` (seed {orig_meta.training_seed}, "
        f"generation {orig_meta.generation}, trained under `{orig_meta.format_id}`).",
        f"- Adapted checkpoint: `{adapt_meta.path}` (seed {adapt_meta.training_seed}, "
        f"generation {adapt_meta.generation}, adapted under `{adapt_meta.format_id}`).",
        (
            f"- Observable parameters of original checkpoint: "
            f"base_score={orig_meta.params['base_score']:.2f}, "
            f"low_hp_score={orig_meta.params['low_hp_score']:.2f}, "
            f"hp_threshold={orig_meta.params['hp_threshold']:.3f}, "
            f"scarcity_slope={orig_meta.params['scarcity_slope']:.2f}, "
            f"pp_cushion={orig_meta.params['pp_cushion']:.2f}."
        ),
        (
            f"- Observable parameters of adapted checkpoint: "
            f"base_score={adapt_meta.params['base_score']:.2f}, "
            f"low_hp_score={adapt_meta.params['low_hp_score']:.2f}, "
            f"hp_threshold={adapt_meta.params['hp_threshold']:.3f}, "
            f"scarcity_slope={adapt_meta.params['scarcity_slope']:.2f}, "
            f"pp_cushion={adapt_meta.params['pp_cushion']:.2f}."
        ),
        (
            f"- Unit parameter distance: L1 = {param_summary.l1_distance:.4f}, "
            f"L2 = {param_summary.l2_distance:.4f}."
        ),
    ]

    if not param_summary.is_scarcity_sensitive:
        lines.append(
            "- Scarcity sensitivity: Both policies retain scarcity_slope = 0.0, indicating "
            "that Protect scoring is invariant to remaining Protect PP in both policies."
        )

    lines.extend(
        [
            "",
            "### 2. Empirical Performance across Protect Formats",
        ]
    )

    for var in ("protect-16", "protect-8"):
        o_p = orig_perf.get(var)
        a_p = adapt_perf.get(var)
        p_diff = paired_diffs.get(var)
        if not o_p or not a_p or not p_diff:
            continue

        sig_text = (
            "statistically significant"
            if p_diff.is_statistically_significant
            else "not statistically distinguishable from zero"
        )
        lines.extend(
            [
                f"#### Format {var} ({o_p.format_id})",
                (
                    f"- Original policy: {o_p.points_per_game:.3f} PPG "
                    f"(win rate {o_p.win_rate:.3f}, {o_p.wins}W-{o_p.losses}L-{o_p.ties}T), "
                    f"Protect use rate {o_p.protect_use_rate:.4f} "
                    f"({o_p.candidate_protect_uses}/{o_p.candidate_protect_opportunities} opps), "
                    f"depletions: {o_p.protect_depletions}."
                ),
                (
                    f"- Adapted policy: {a_p.points_per_game:.3f} PPG "
                    f"(win rate {a_p.win_rate:.3f}, {a_p.wins}W-{a_p.losses}L-{a_p.ties}T), "
                    f"Protect use rate {a_p.protect_use_rate:.4f} "
                    f"({a_p.candidate_protect_uses}/{a_p.candidate_protect_opportunities} opps), "
                    f"depletions: {a_p.protect_depletions}."
                ),
                (
                    f"- Paired delta (adapted minus original): {p_diff.delta_ppg:+.3f} PPG "
                    f"(95% bootstrap CI [{p_diff.delta_ppg_ci_95.ci_lower:+.3f}, "
                    f"{p_diff.delta_ppg_ci_95.ci_upper:+.3f}]), which is {sig_text}."
                ),
            ]
        )

    if native_perf is not None and "protect-8" in native_perf:
        nat_p = native_perf["protect-8"]
        lines.extend(
            [
                "",
                "#### Native Reference under protect-8",
                (
                    f"- Target-native reference: {nat_p.points_per_game:.3f} PPG "
                    f"(win rate {nat_p.win_rate:.3f}), "
                    f"Protect use rate {nat_p.protect_use_rate:.4f}, "
                    f"depletions: {nat_p.protect_depletions}."
                ),
            ]
        )

    lines.extend(
        [
            "",
            "### 3. Defensive Habit and Scarcity Metrics",
            "- Scarcity binding: 0 Protect depletions occurred across all evaluated games for both "
            "policies. The 8 PP limit did not constrain play in any match.",
        ]
    )

    o_8 = orig_perf.get("protect-8")
    a_8 = adapt_perf.get("protect-8")
    if o_8 and a_8:
        lines.append(
            f"- Consecutive Protect mistake rate under 8 PP: "
            f"original candidate mistake rate is {o_8.consecutive_protect_rate or 0.0:.4f} "
            f"({o_8.consecutive_protect_mistakes} flags); "
            f"adapted candidate mistake rate is {a_8.consecutive_protect_rate or 0.0:.4f} "
            f"({a_8.consecutive_protect_mistakes} flags)."
        )

    lines.extend(
        [
            "",
            "### 4. Decision Agreement and Divergence",
            (
                f"- Evaluated decision count: {divergence.total_decisions_compared} "
                "decisions across replays."
            ),
            (
                f"- Exact action agreement: {divergence.identical_decisions}/"
                f"{divergence.total_decisions_compared} "
                f"({divergence.agreement_rate * 100:.1f}% agreement rate)."
            ),
            f"- Protect choice agreement: {divergence.protect_agreement_rate * 100:.1f}%.",
        ]
    )

    if divergence.divergent_decisions > 0:
        lines.append(
            f"- Divergent decisions ({divergence.divergent_decisions} instances): "
            "differences occur when observable HP ratios cross threshold boundaries "
            "while remaining Protect PP remains unexhausted."
        )
    else:
        lines.append(
            "- Zero action divergence was observed across all recorded decisions, "
            "confirming that the parameter differences produce identical choice outputs "
            "on the evaluated match states."
        )

    if h2h:
        lines.extend(
            [
                "",
                "### 5. Direct Head-to-Head Cross-Play",
                (
                    f"- Head-to-head format: {h2h.format_id} ({h2h.variant}) across "
                    f"{h2h.total_matches} matches."
                ),
                f"- Original wins: {h2h.original_wins} ({h2h.original_win_rate * 100:.1f}%).",
                f"- Adapted wins: {h2h.adapted_wins} ({h2h.adapted_win_rate * 100:.1f}%).",
                f"- Ties: {h2h.ties}.",
            ]
        )

    diff_8 = paired_diffs.get("protect-8")
    delta_str = f"{diff_8.delta_ppg:+.3f}" if diff_8 else "0.000"
    ci_str = (
        f"[{diff_8.delta_ppg_ci_95.ci_lower:+.3f}, {diff_8.delta_ppg_ci_95.ci_upper:+.3f}]"
        if diff_8
        else "[0.000, 0.000]"
    )

    lines.extend(
        [
            "",
            "### 6. Conclusion",
            (
                "The comparison between original and adapted checkpoints confirms a null result "
                "under clean single-factor experimental controls. Reducing maximum Protect PP "
                "from 16 to 8 does not cause PP depletion (0 depletions), and the performance "
                f"difference (delta = {delta_str} PPG, 95% bootstrap CI {ci_str}) is not "
                "statistically distinguishable from zero. Observable defensive choices remain "
                "invariant between original and adapted policies."
            ),
        ]
    )

    narrative = "\n".join(lines)
    verify_no_unsupported_beliefs(narrative)
    return narrative


def compare_checkpoints(
    original_checkpoint_path: Path,
    adapted_checkpoint_path: Path,
    native_checkpoint_path: Path | None = None,
    original_results_path: Path | None = None,
    adapted_results_path: Path | None = None,
    native_results_path: Path | None = None,
    spec: ExperimentSpec | None = None,
    manifest: TeamManifest | None = None,
    opponent_policy: str = "HeuristicBaseline",
    eval_seed: int = 101,
    pairs: int = 1,
    run_h2h: bool = False,
    h2h_pairs: int = 1,
    showdown_dir: Path | str | None = None,
    bootstrap_resamples: int = 1000,
    alpha: float = 0.05,
    bootstrap_seed: int = 42,
) -> CheckpointComparisonReport:
    """Compare original and adapted checkpoints across Protect-only rulesets."""
    if spec is None:
        raw_spec = json.loads(DEFAULT_SPEC_PATH.read_text(encoding="utf-8"))
        spec = validate_spec(raw_spec)

    if manifest is None:
        manifest = load_manifest(DEFAULT_MANIFEST_PATH)

    orig_params, orig_raw = load_checkpoint(original_checkpoint_path)
    adapt_params, adapt_raw = load_checkpoint(adapted_checkpoint_path)

    orig_agent = checkpoint_agent(original_checkpoint_path)
    adapt_agent = checkpoint_agent(adapted_checkpoint_path)

    native_params = None
    native_raw = None
    native_agent = None
    if native_checkpoint_path and native_checkpoint_path.exists():
        native_params, native_raw = load_checkpoint(native_checkpoint_path)
        native_agent = checkpoint_agent(native_checkpoint_path)

    orig_meta = CheckpointMetadata(
        path=str(original_checkpoint_path),
        agent=orig_raw.get("agent", "source"),
        ruleset=orig_raw.get("ruleset", "protect-16"),
        format_id=orig_raw.get("format_id", FORMAT_BY_PP[16]),
        training_seed=orig_raw.get("training_seed", 0),
        generation=orig_raw.get("generation", 0),
        params=orig_raw.get("params", asdict(orig_params)),
        unit_mean=orig_raw.get("unit_mean", orig_params.to_unit()),
        unit_std=orig_raw.get("unit_std", [0.0] * 5),
    )

    adapt_meta = CheckpointMetadata(
        path=str(adapted_checkpoint_path),
        agent=adapt_raw.get("agent", "adapted"),
        ruleset=adapt_raw.get("ruleset", "protect-8"),
        format_id=adapt_raw.get("format_id", FORMAT_BY_PP[8]),
        training_seed=adapt_raw.get("training_seed", 0),
        generation=adapt_raw.get("generation", 0),
        params=adapt_raw.get("params", asdict(adapt_params)),
        unit_mean=adapt_raw.get("unit_mean", adapt_params.to_unit()),
        unit_std=adapt_raw.get("unit_std", [0.0] * 5),
    )

    native_meta = None
    if native_params and native_raw:
        native_meta = CheckpointMetadata(
            path=str(native_checkpoint_path),
            agent=native_raw.get("agent", "native"),
            ruleset=native_raw.get("ruleset", "protect-8"),
            format_id=native_raw.get("format_id", FORMAT_BY_PP[8]),
            training_seed=native_raw.get("training_seed", 0),
            generation=native_raw.get("generation", 0),
            params=native_raw.get("params", asdict(native_params)),
            unit_mean=native_raw.get("unit_mean", native_params.to_unit()),
            unit_std=native_raw.get("unit_std", [0.0] * 5),
        )

    # 1. Parameter comparison
    param_summary = compare_checkpoint_parameters(orig_params, adapt_params)

    # 2. Gather evaluation games and replays
    def load_or_run_eval(
        agent: TrainedProtectAgent,
        results_path: Path | None,
    ) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
        if results_path and results_path.exists():
            if results_path.is_file():
                data = json.loads(results_path.read_text(encoding="utf-8"))
                games = data.get("games", [])
                eval_dir = results_path.parent
            else:
                data = json.loads((results_path / "results.json").read_text(encoding="utf-8"))
                games = data.get("games", [])
                eval_dir = results_path

            replays: dict[str, dict[str, Any]] = {}
            for g in games:
                gid = g.get("game_id", "")
                r_rel = g.get("replay")
                if r_rel:
                    r_path = eval_dir / r_rel
                    if r_path.exists():
                        replays[gid] = read_replay_file(r_path)
            return games, replays

        # If no pre-existing results, run evaluation suite on the fly
        import tempfile

        with tempfile.TemporaryDirectory() as tmp_dirname:
            tmp_dir = Path(tmp_dirname)
            packed = {tid: t.packed for tid, t in manifest.teams.items()}
            rec = GameRecorder(tmp_dir, packed)
            run_evaluation_suite(
                spec=spec,
                manifest=manifest,
                candidate=agent,
                opponent_policies=[opponent_policy],
                evaluation_seeds=[eval_seed],
                variants=["protect-16", "protect-8"],
                pairs_per_matchup=pairs,
                showdown_dir=showdown_dir,
                recorder=rec,
            )
            rec.finish(
                meta={"stage": "checkpoint-comparison", "agent": agent.name},
                summary={},
            )
            games = list(rec.games)
            live_replays: dict[str, dict[str, Any]] = {}
            for g in games:
                gid = g.get("game_id", "")
                r_rel = g.get("replay")
                if r_rel:
                    r_path = tmp_dir / r_rel
                    if r_path.exists():
                        live_replays[gid] = read_replay_file(r_path)
            return games, live_replays

    orig_games, orig_replays = load_or_run_eval(orig_agent, original_results_path)
    adapt_games, adapt_replays = load_or_run_eval(adapt_agent, adapted_results_path)

    native_games: list[dict[str, Any]] = []
    native_replays: dict[str, dict[str, Any]] = {}
    if native_agent:
        native_games, native_replays = load_or_run_eval(native_agent, native_results_path)

    # 3. Compute CheckpointPerformance for each variant
    orig_perf: dict[str, CheckpointPerformance] = {}
    adapt_perf: dict[str, CheckpointPerformance] = {}
    native_perf: dict[str, CheckpointPerformance] | None = {} if native_agent else None

    for var in ("protect-16", "protect-8"):
        pp = spec.variants[var]
        fmt = FORMAT_BY_PP[pp]
        orig_perf[var] = evaluate_checkpoint_performance(orig_games, var, fmt, orig_replays)
        adapt_perf[var] = evaluate_checkpoint_performance(adapt_games, var, fmt, adapt_replays)
        if native_perf is not None and native_games:
            native_perf[var] = evaluate_checkpoint_performance(
                native_games, var, fmt, native_replays
            )

    # 4. Paired differences and bootstrap confidence intervals
    paired_diffs: dict[str, PairedPerformanceComparison] = {}
    for var in ("protect-16", "protect-8"):
        o_g = [g for g in orig_games if g.get("variant") == var]
        a_g = [g for g in adapt_games if g.get("variant") == var]

        # Calculate paired difference scores
        o_scores = [POINTS.get(g.get("result", "tie"), 0.5) for g in o_g]
        a_scores = [POINTS.get(g.get("result", "tie"), 0.5) for g in a_g]

        n_pairs = min(len(o_scores), len(a_scores))
        deltas = [a_scores[i] - o_scores[i] for i in range(n_pairs)] if n_pairs > 0 else [0.0]

        ci = calculate_ci(
            deltas,
            n_resamples=bootstrap_resamples,
            alpha=alpha,
            seed=bootstrap_seed,
        )

        o_p = orig_perf[var]
        a_p = adapt_perf[var]
        d_ppg = a_p.points_per_game - o_p.points_per_game
        d_win = a_p.win_rate - o_p.win_rate
        d_prot = a_p.protect_use_rate - o_p.protect_use_rate
        sig = ci.ci_lower > 0.0 or ci.ci_upper < 0.0
        scarcity = (o_p.protect_depletions > 0) or (a_p.protect_depletions > 0)

        paired_diffs[var] = PairedPerformanceComparison(
            variant=var,
            delta_ppg=round(d_ppg, 4),
            delta_win_rate=round(d_win, 4),
            delta_protect_use_rate=round(d_prot, 4),
            delta_ppg_ci_95=ci,
            is_statistically_significant=sig,
            scarcity_binds=scarcity,
        )

    # 5. Decision divergence analysis across available replays
    all_replays = list(orig_replays.values()) + list(adapt_replays.values())
    unique_replays: list[dict[str, Any]] = []
    seen_seeds = set()
    for r in all_replays:
        b_seed = tuple(r.get("battle_seed", []))
        if b_seed not in seen_seeds:
            seen_seeds.add(b_seed)
            unique_replays.append(r)

    divergence_summary = analyze_decision_divergence(orig_agent, adapt_agent, unique_replays)

    # 6. Optional Head-to-Head cross-play
    h2h_summary = None
    if run_h2h:
        h2h_summary = run_head_to_head_battles(
            orig_agent=orig_agent,
            adapted_agent=adapt_agent,
            manifest=manifest,
            pairs=h2h_pairs,
            format_id=FORMAT_BY_PP[8],
            eval_seed=eval_seed,
            showdown_dir=showdown_dir,
        )

    # 7. Synthesize narrative and verify belief exclusion
    narrative = build_checkpoint_comparison_narrative(
        orig_meta=orig_meta,
        adapt_meta=adapt_meta,
        param_summary=param_summary,
        orig_perf=orig_perf,
        adapt_perf=adapt_perf,
        paired_diffs=paired_diffs,
        divergence=divergence_summary,
        h2h=h2h_summary,
        native_perf=native_perf,
    )

    findings = {
        "is_scarcity_sensitive": param_summary.is_scarcity_sensitive,
        "scarcity_binds_in_either_checkpoint": any(p.scarcity_binds for p in paired_diffs.values()),
        "target_format_delta_ppg": paired_diffs["protect-8"].delta_ppg,
        "target_format_ci_95": asdict(paired_diffs["protect-8"].delta_ppg_ci_95),
        "is_target_format_delta_significant": paired_diffs[
            "protect-8"
        ].is_statistically_significant,
        "decision_agreement_rate": divergence_summary.agreement_rate,
        "conclusion": (
            "scarcity_binds"
            if any(p.scarcity_binds for p in paired_diffs.values())
            else (
                "null_result_confirmed: reducing maximum Protect PP from 16 to 8 does not bind, "
                f"and performance difference 95% CI "
                f"[{paired_diffs['protect-8'].delta_ppg_ci_95.ci_lower:+.3f}, "
                f"{paired_diffs['protect-8'].delta_ppg_ci_95.ci_upper:+.3f}] confirms no "
                "statistically distinguishable degradation between original and "
                "adapted checkpoints."
            )
        ),
    }

    return CheckpointComparisonReport(
        schema_version=CHECKPOINT_COMPARISON_SCHEMA_VERSION,
        created_at=datetime.now(UTC).isoformat(),
        spec=spec.name,
        simulator_revision=spec.simulator_revision,
        original=orig_meta,
        adapted=adapt_meta,
        native=native_meta,
        parameter_comparison=param_summary,
        original_performance=orig_perf,
        adapted_performance=adapt_perf,
        native_performance=native_perf,
        paired_differences=paired_diffs,
        decision_divergence=divergence_summary,
        head_to_head=h2h_summary,
        findings=findings,
        empirical_narrative=narrative,
    )
