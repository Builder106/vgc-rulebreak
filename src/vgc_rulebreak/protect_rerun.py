"""Rerun training and evaluation on the isolated Protect-only format pair.

This module automates the complete Study P rerun pipeline:
1. Trains source (16 PP), native (8 PP), and adapted (8 PP from source) policies
   exclusively under the paired experimental formats (gen9rulebreakprotect16 and
   gen9rulebreakprotect8).
2. Evaluates the resulting checkpoints against held-out test teams and opponent
   baselines under paired seeds and mirrored seats.
3. Records all per-game decisions, replays, and recovery summaries.
"""

import dataclasses
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from vgc_rulebreak.agents.trained import checkpoint_agent, load_checkpoint
from vgc_rulebreak.evaluation import FORMAT_BY_PP, run_evaluation_suite
from vgc_rulebreak.manifest import TeamManifest, load_manifest
from vgc_rulebreak.records import GameRecorder
from vgc_rulebreak.recovery import summarize_recovery
from vgc_rulebreak.spec import ExperimentSpec, validate_spec
from vgc_rulebreak.training import TrainingConfig, train_protect_policy

DEFAULT_SPEC_PATH = Path("experiments/protect-pp.json")
DEFAULT_MANIFEST_PATH = Path("experiments/teams/protect-pp.json")


@dataclass(frozen=True)
class ProtectRerunConfig:
    training_seed: int = 11
    eval_seed: int = 101
    generations: int = 3
    population: int = 6
    elites: int = 2
    pairs: int = 1
    eval_pairs: int = 1
    workers: int = 4
    eval_all_checkpoints: bool = False
    opponent_policy: str = "HeuristicBaseline"


@dataclass(frozen=True)
class ProtectRerunReport:
    spec: str
    simulator_revision: str
    training_seed: int
    eval_seed: int
    formats: dict[str, str]
    checkpoints: dict[str, list[str]]
    evaluated_checkpoints: tuple[str, ...]
    total_training_games: int
    total_evaluation_games: int
    total_depletions: int
    scarcity_binds: bool
    recovery_series: tuple[dict[str, Any], ...]
    agent_summaries: dict[str, dict[str, Any]]
    findings: dict[str, Any]


def run_protect_rerun(
    output_dir: Path,
    config: ProtectRerunConfig | None = None,
    spec: ExperimentSpec | None = None,
    manifest: TeamManifest | None = None,
    showdown_dir: Path | str | None = None,
) -> ProtectRerunReport:
    """Run full Protect-only training and evaluation rerun across source, native, and adapted."""
    cfg = config or ProtectRerunConfig()

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

    # 1. Train Source Agent under protect-16 (gen9rulebreakprotect16)
    source_cfg = TrainingConfig(
        agent="source",
        training_seed=cfg.training_seed,
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

    # 2. Train Native Agent under protect-8 (gen9rulebreakprotect8)
    native_cfg = TrainingConfig(
        agent="native",
        training_seed=cfg.training_seed,
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

    # 3. Train Adapted Agent under protect-8 starting from final Source checkpoint
    adapted_cfg = TrainingConfig(
        agent="adapted",
        training_seed=cfg.training_seed,
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

    all_ckpts = {
        "source": [str(p) for p in source_ckpts],
        "native": [str(p) for p in native_ckpts],
        "adapted": [str(p) for p in adapted_ckpts],
    }

    # Select checkpoints to evaluate
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

    packed_teams = {team_id: team.packed for team_id, team in manifest.teams.items()}
    agent_summaries: dict[str, dict[str, Any]] = {}
    total_eval_games = 0
    total_depletions = 0
    total_protect_uses = 0
    total_protect_opps = 0

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
                "stage": "protect-rerun",
                "spec": spec.name,
                "simulator_revision": spec.simulator_revision,
                "training_seed": cfg.training_seed,
                "eval_seed": cfg.eval_seed,
                "checkpoint": str(ckpt_path),
            },
            summary=summary_dict,
        )

        agent_summaries[agent.name] = summary_dict
        total_eval_games += summary.total_matches
        total_depletions += sum(m.protect_depleted_matches for m in summary.matchup_summaries)
        total_protect_uses += sum(m.candidate_protect_uses for m in summary.matchup_summaries)
        # Count opportunities across recorder games
        for g in recorder.games:
            total_protect_opps += int(g.get("candidate_protect_opportunities", 0))

    # Summarize recovery series from all evaluation results
    recovery_dataset = summarize_recovery(eval_dir.rglob("results.json"))
    recovery_path = output_dir / "recovery.json"
    recovery_path.write_text(json.dumps(recovery_dataset, indent=2) + "\n", encoding="utf-8")

    # Calculate overall training games
    # 3 agents * generations * population * training_matchups * 2
    training_matchups_count = len(manifest.splits.get("training", ()))
    # 2 training teams -> 3 matchups * 2 mirrored * pairs
    games_per_candidate = (
        (training_matchups_count * (training_matchups_count + 1) // 2) * 2 * cfg.pairs
    )
    total_training_games = 3 * cfg.generations * cfg.population * games_per_candidate

    scarcity_binds = total_depletions > 0
    overall_protect_rate = (
        total_protect_uses / max(total_protect_opps, 1) if total_protect_opps > 0 else 0.0
    )

    findings = {
        "formats_used": expected_formats,
        "scarcity_binds": scarcity_binds,
        "total_depletions": total_depletions,
        "total_protect_uses": total_protect_uses,
        "total_protect_opportunities": total_protect_opps,
        "overall_protect_use_rate": round(overall_protect_rate, 4),
        "conclusion": (
            "scarcity_binds"
            if scarcity_binds
            else "null_result_confirmed_8pp_does_not_bind_without_stall"
        ),
    }

    report = ProtectRerunReport(
        spec=spec.name,
        simulator_revision=spec.simulator_revision,
        training_seed=cfg.training_seed,
        eval_seed=cfg.eval_seed,
        formats=expected_formats,
        checkpoints=all_ckpts,
        evaluated_checkpoints=tuple(checkpoint_agent(p).name for p in eval_targets),
        total_training_games=total_training_games,
        total_evaluation_games=total_eval_games,
        total_depletions=total_depletions,
        scarcity_binds=scarcity_binds,
        recovery_series=tuple(recovery_dataset.get("series", [])),
        agent_summaries=agent_summaries,
        findings=findings,
    )

    summary_file = output_dir / "rerun_summary.json"
    summary_file.write_text(json.dumps(asdict(report), indent=2) + "\n", encoding="utf-8")

    return report
