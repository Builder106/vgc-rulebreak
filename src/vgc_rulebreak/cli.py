"""CLI commands for specification checks and mechanics verification."""

import argparse
import dataclasses
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vgc_rulebreak.fixtures.mechanics import verify_all_mechanics
from vgc_rulebreak.spec import ExperimentSpec, validate_spec

if TYPE_CHECKING:
    from vgc_rulebreak.manifest import TeamManifest
    from vgc_rulebreak.records import GameRecorder


def make_recorder(output_dir: Path | None, manifest: "TeamManifest") -> "GameRecorder | None":
    """Create a per-game recorder when an output directory was requested."""
    if output_dir is None:
        return None
    from vgc_rulebreak.records import GameRecorder

    packed = {team_id: team.packed for team_id, team in manifest.teams.items()}
    return GameRecorder(output_dir, packed)


def finish_recorder(
    recorder: "GameRecorder",
    command: str,
    spec: ExperimentSpec,
    args: argparse.Namespace,
    summary: dict[str, Any],
) -> None:
    """Write results.json with the run's provenance and report where it went."""
    options = {
        key: str(value) if isinstance(value, Path) else value
        for key, value in vars(args).items()
        if key not in {"command", "showdown_dir", "output_dir"}
    }
    meta = {
        "command": command,
        "spec": spec.name,
        "simulator_revision": spec.simulator_revision,
        "options": options,
    }
    path = recorder.finish(meta, summary)
    print(f"Wrote {len(recorder.games)} games to {path}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    # Subcommand: check
    check = subcommands.add_parser("check", help="validate a Protect study specification")
    check.add_argument("spec", type=Path)
    check.add_argument(
        "--require-ready", action="store_true", help="fail if readiness declarations are missing"
    )

    # Subcommand: verify-mechanics
    verify = subcommands.add_parser(
        "verify-mechanics",
        help="run deterministic mechanics verification fixtures against Showdown",
    )
    verify.add_argument(
        "--showdown-dir",
        type=Path,
        default=None,
        help="path to local pokemon-showdown checkout",
    )
    verify.add_argument(
        "--spec",
        type=Path,
        default=None,
        help="optional experiment spec to validate simulator revision against",
    )
    verify.add_argument(
        "--update-spec",
        action="store_true",
        help="update spec readiness.mechanics_verified to true if all fixtures pass",
    )

    # Subcommand: benchmark-agent
    bench = subcommands.add_parser(
        "benchmark-agent",
        help="evaluate competent baseline agent against random baseline and record costs",
    )
    bench.add_argument("--matches", type=int, default=5, help="number of evaluation matches")
    bench.add_argument(
        "--showdown-dir", type=Path, default=None, help="path to local pokemon-showdown checkout"
    )
    bench.add_argument(
        "--min-win-rate", type=float, default=0.8, help="minimum acceptable win rate"
    )

    # Subcommand: pilot-eval
    pilot = subcommands.add_parser(
        "pilot-eval",
        help="run pilot evaluation to calibrate sample size and compute budget",
    )
    pilot.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/teams/protect-pp.json"),
        help="path to Open Team Sheet manifest",
    )
    pilot.add_argument(
        "--spec",
        type=Path,
        default=None,
        help="optional experiment spec to update with calibrated budget",
    )
    pilot.add_argument(
        "--sample-pairs",
        type=int,
        default=3,
        help="number of mirrored pilot pairs per matchup",
    )
    pilot.add_argument(
        "--showdown-dir",
        type=Path,
        default=None,
        help="path to local pokemon-showdown checkout",
    )
    pilot.add_argument(
        "--update-spec",
        action="store_true",
        help="update spec readiness with calibrated pairs_per_matchup and compute_budget_seconds",
    )
    pilot.add_argument(
        "--scarcity",
        action="store_true",
        help="run behavioral scarcity pilot on held-out teams to check if Protect 8 PP binds",
    )

    # Subcommand: anti-meta-check
    am_check = subcommands.add_parser(
        "anti-meta-check",
        help="validate Champions regulation, staple ban, and anti-meta team manifest",
    )
    am_check.add_argument(
        "--regulation",
        type=Path,
        default=Path("experiments/champions-regulation.json"),
        help="path to Champions regulation JSON",
    )
    am_check.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/teams/anti-meta.json"),
        help="path to anti-meta teams manifest",
    )
    am_check.add_argument(
        "--verify-simulator",
        action="store_true",
        help="verify simulator support for Champions mechanics",
    )
    am_check.add_argument(
        "--showdown-dir",
        type=Path,
        default=None,
        help="path to local pokemon-showdown checkout",
    )

    # Subcommand: anti-meta-eval
    am_eval = subcommands.add_parser(
        "anti-meta-eval",
        help="evaluate anti-meta anchored team against meta pool splits with confidence intervals",
    )
    am_eval.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/teams/anti-meta.json"),
        help="path to anti-meta teams manifest",
    )
    am_eval.add_argument(
        "--team",
        type=str,
        default="reference-hippowdon-sand",
        help="team ID to evaluate",
    )
    am_eval.add_argument(
        "--split",
        type=str,
        default="test",
        choices=["training", "validation", "test"],
        help="meta pool split to evaluate against",
    )
    am_eval.add_argument(
        "--pairs",
        type=int,
        default=2,
        help="mirrored pairs per matchup",
    )
    am_eval.add_argument(
        "--seed",
        type=int,
        default=101,
        help="evaluation seed",
    )
    am_eval.add_argument(
        "--showdown-dir",
        type=Path,
        default=None,
        help="path to local pokemon-showdown checkout",
    )

    # Subcommand: anti-meta-search
    am_search = subcommands.add_parser(
        "anti-meta-search",
        help="search legal support rosters around anchor against the meta search split",
    )
    am_search.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/teams/anti-meta.json"),
        help="path to anti-meta teams manifest",
    )
    am_search.add_argument(
        "--regulation",
        type=Path,
        default=Path("experiments/champions-regulation.json"),
        help="path to Champions regulation JSON",
    )
    am_search.add_argument(
        "--budget",
        type=int,
        default=3,
        help="number of candidate support rosters to evaluate",
    )
    am_search.add_argument(
        "--seed",
        type=int,
        default=42,
        help="random seed for candidate roster sampling",
    )
    am_search.add_argument(
        "--showdown-dir",
        type=Path,
        default=None,
        help="path to local pokemon-showdown checkout",
    )

    # Subcommand: anti-meta-compare
    am_comp = subcommands.add_parser(
        "anti-meta-compare",
        help="compare meta-tuned and broadly tuned agents against the anchored team",
    )
    am_comp.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/teams/anti-meta.json"),
        help="path to anti-meta teams manifest",
    )
    am_comp.add_argument(
        "--regulation",
        type=Path,
        default=Path("experiments/champions-regulation.json"),
        help="path to Champions regulation JSON",
    )
    am_comp.add_argument(
        "--team",
        type=str,
        default="reference-hippowdon-sand",
        help="team identifier to test",
    )
    am_comp.add_argument(
        "--pairs",
        type=int,
        default=1,
        help="number of mirrored battle pairs per agent comparison",
    )
    am_comp.add_argument(
        "--seed",
        type=int,
        default=202,
        help="base random seed for battle evaluation",
    )
    am_comp.add_argument(
        "--showdown-dir",
        type=Path,
        default=None,
        help="path to local pokemon-showdown checkout",
    )

    # Subcommand: anti-meta-shift
    am_shift = subcommands.add_parser(
        "anti-meta-shift",
        help="evaluate anchored team across initial and shifted ladder usage snapshots",
    )
    am_shift.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/teams/anti-meta.json"),
        help="path to anti-meta teams manifest",
    )
    am_shift.add_argument(
        "--initial-snapshot",
        type=Path,
        default=Path("experiments/champions-usage-2026-06.json"),
        help="path to initial usage snapshot JSON",
    )
    am_shift.add_argument(
        "--shifted-snapshot",
        type=Path,
        default=Path("experiments/champions-usage-2026-07.json"),
        help="path to shifted usage snapshot JSON",
    )
    am_shift.add_argument(
        "--team",
        type=str,
        default="reference-hippowdon-sand",
        help="team identifier to test",
    )
    am_shift.add_argument(
        "--pairs",
        type=int,
        default=1,
        help="number of mirrored battle pairs per split",
    )
    am_shift.add_argument(
        "--seed",
        type=int,
        default=303,
        help="base random seed for battle evaluation",
    )
    am_shift.add_argument(
        "--showdown-dir",
        type=Path,
        default=None,
        help="path to local pokemon-showdown checkout",
    )

    # Subcommand: evaluate
    eval_cmd = subcommands.add_parser(
        "evaluate",
        help="evaluate an agent against frozen test teams, opponent policies, and seeds",
    )
    eval_cmd.add_argument(
        "--spec",
        type=Path,
        default=Path("experiments/protect-pp.json"),
        help="path to experiment spec",
    )
    eval_cmd.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/teams/protect-pp.json"),
        help="path to Open Team Sheet manifest",
    )
    eval_cmd.add_argument(
        "--agent",
        type=str,
        default="heuristic",
        choices=["heuristic", "random", "source", "adapted", "native"],
        help="candidate agent to evaluate",
    )
    eval_cmd.add_argument(
        "--opponent",
        type=str,
        default=None,
        choices=["HeuristicBaseline", "RandomBaseline"],
        help="specific opponent policy (defaults to all frozen opponent policies)",
    )
    eval_cmd.add_argument(
        "--variant",
        type=str,
        default=None,
        choices=["protect-16", "protect-8"],
        help="specific variant (defaults to all variants)",
    )
    eval_cmd.add_argument(
        "--seed",
        type=int,
        default=None,
        help="specific evaluation seed (defaults to all frozen evaluation seeds)",
    )
    eval_cmd.add_argument(
        "--pairs",
        type=int,
        default=None,
        help="mirrored pairs per matchup (defaults to 1 for ad-hoc, or full spec budget)",
    )
    eval_cmd.add_argument(
        "--check-only",
        action="store_true",
        help="validate frozen evaluation setup without running battles",
    )
    eval_cmd.add_argument(
        "--showdown-dir",
        type=Path,
        default=None,
        help="path to local pokemon-showdown checkout",
    )
    eval_cmd.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="write results.json and one replay per game here (for example runs/<name>)",
    )
    eval_cmd.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="evaluate a trained Protect policy checkpoint instead of --agent",
    )

    # Subcommand: train
    train_cmd = subcommands.add_parser(
        "train",
        help="train the Protect policy's parameters against game outcomes on training teams",
    )
    train_cmd.add_argument("--agent", required=True, choices=["source", "native", "adapted"])
    train_cmd.add_argument(
        "--seed", type=int, required=True, help="one of the spec's training seeds"
    )
    train_cmd.add_argument("--output-dir", type=Path, required=True)
    train_cmd.add_argument(
        "--init", type=Path, default=None, help="source checkpoint to adapt from (adapted only)"
    )
    train_cmd.add_argument("--generations", type=int, default=12)
    train_cmd.add_argument("--population", type=int, default=12)
    train_cmd.add_argument("--elites", type=int, default=4)
    train_cmd.add_argument("--pairs", type=int, default=1, help="mirrored pairs per matchup")
    train_cmd.add_argument("--workers", type=int, default=4, help="parallel battle processes")
    train_cmd.add_argument("--spec", type=Path, default=Path("experiments/protect-pp.json"))
    train_cmd.add_argument(
        "--manifest", type=Path, default=Path("experiments/teams/protect-pp.json")
    )
    train_cmd.add_argument("--showdown-dir", type=Path, default=None)

    # Subcommand: summarize-recovery
    recovery_cmd = subcommands.add_parser(
        "summarize-recovery",
        help="group checkpoint evaluations into habit-recovery series",
    )
    recovery_cmd.add_argument(
        "--runs", type=Path, required=True, help="directory searched for results.json files"
    )
    recovery_cmd.add_argument("--output", type=Path, required=True)

    # Subcommand: export-showcase
    showcase_cmd = subcommands.add_parser(
        "export-showcase",
        help="export evaluated games and recovery series as static data for the showcase",
    )
    showcase_cmd.add_argument(
        "--runs", type=Path, required=True, help="directory searched for results.json files"
    )
    showcase_cmd.add_argument("--output", type=Path, required=True, help="output directory")
    showcase_cmd.add_argument(
        "--showdown-dir", type=Path, default=None, help="path to local pokemon-showdown checkout"
    )

    # Subcommand: compare-agents
    comp_cmd = subcommands.add_parser(
        "compare-agents",
        help="compare unchanged source, adapted, and target-native agents across Protect rulesets",
    )
    comp_cmd.add_argument(
        "--spec",
        type=Path,
        default=Path("experiments/protect-pp.json"),
        help="path to experiment spec",
    )
    comp_cmd.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/teams/protect-pp.json"),
        help="path to Open Team Sheet manifest",
    )
    comp_cmd.add_argument(
        "--opponent",
        type=str,
        default="RandomBaseline",
        choices=["RandomBaseline", "HeuristicBaseline"],
        help="reference opponent baseline for performance anchoring",
    )
    comp_cmd.add_argument(
        "--pairs",
        type=int,
        default=1,
        help="number of mirrored pairs per matchup (defaults to 1)",
    )
    comp_cmd.add_argument(
        "--seed",
        type=int,
        default=101,
        help="evaluation seed to use (defaults to 101)",
    )
    comp_cmd.add_argument(
        "--quick",
        action="store_true",
        help="run cross-matchup only for rapid verification",
    )
    comp_cmd.add_argument(
        "--showdown-dir",
        type=Path,
        default=None,
        help="path to local pokemon-showdown checkout",
    )
    comp_cmd.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="write results.json and one replay per game here (for example runs/<name>)",
    )

    # Subcommand: protect-rerun
    rerun_cmd = subcommands.add_parser(
        "protect-rerun",
        help="rerun training and evaluation pipeline on the paired Protect-only formats",
    )
    rerun_cmd.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="directory to save checkpoints, evaluations, and recovery results",
    )
    rerun_cmd.add_argument(
        "--training-seed",
        type=int,
        default=11,
        help="seed for training parameter sampling and mirrored battle pairs",
    )
    rerun_cmd.add_argument(
        "--eval-seed",
        type=int,
        default=101,
        help="seed for held-out evaluation battles",
    )
    rerun_cmd.add_argument(
        "--generations",
        type=int,
        default=3,
        help="number of training generations per agent",
    )
    rerun_cmd.add_argument(
        "--population",
        type=int,
        default=6,
        help="population size per generation",
    )
    rerun_cmd.add_argument(
        "--elites",
        type=int,
        default=2,
        help="number of elite candidates to refit each generation",
    )
    rerun_cmd.add_argument(
        "--pairs",
        type=int,
        default=1,
        help="mirrored pairs per matchup in training",
    )
    rerun_cmd.add_argument(
        "--eval-pairs",
        type=int,
        default=1,
        help="mirrored pairs per matchup in evaluation",
    )
    rerun_cmd.add_argument(
        "--workers",
        type=int,
        default=4,
        help="parallel battle worker processes",
    )
    rerun_cmd.add_argument(
        "--eval-all-checkpoints",
        action="store_true",
        help="evaluate every generation checkpoint instead of initial and final checkpoints",
    )
    rerun_cmd.add_argument(
        "--quick",
        action="store_true",
        help="rapid rerun with 1 generation and minimal population for testing",
    )
    rerun_cmd.add_argument(
        "--spec",
        type=Path,
        default=Path("experiments/protect-pp.json"),
        help="path to experiment specification",
    )
    rerun_cmd.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/teams/protect-pp.json"),
        help="path to Open Team Sheet manifest",
    )
    rerun_cmd.add_argument(
        "--showdown-dir",
        type=Path,
        default=None,
        help="path to local pokemon-showdown checkout",
    )

    # Subcommand: protect-multi-seed
    multi_seed_cmd = subcommands.add_parser(
        "protect-multi-seed",
        help="evaluate multiple training seeds and report confidence intervals for Study P",
    )
    multi_seed_cmd.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="directory to save checkpoints, evaluations, recovery results, and multi-seed report",
    )
    multi_seed_cmd.add_argument(
        "--training-seeds",
        type=int,
        nargs="+",
        default=[11, 29, 47],
        help="training seeds to train and evaluate (defaults to 11 29 47)",
    )
    multi_seed_cmd.add_argument(
        "--eval-seed",
        type=int,
        default=101,
        help="seed for held-out evaluation battles (defaults to 101)",
    )
    multi_seed_cmd.add_argument(
        "--generations",
        type=int,
        default=3,
        help="number of training generations per agent",
    )
    multi_seed_cmd.add_argument(
        "--population",
        type=int,
        default=6,
        help="population size per generation",
    )
    multi_seed_cmd.add_argument(
        "--elites",
        type=int,
        default=2,
        help="number of elite candidates to refit each generation",
    )
    multi_seed_cmd.add_argument(
        "--pairs",
        type=int,
        default=1,
        help="mirrored pairs per matchup in training",
    )
    multi_seed_cmd.add_argument(
        "--eval-pairs",
        type=int,
        default=1,
        help="mirrored pairs per matchup in evaluation",
    )
    multi_seed_cmd.add_argument(
        "--workers",
        type=int,
        default=4,
        help="parallel battle worker processes",
    )
    multi_seed_cmd.add_argument(
        "--eval-all-checkpoints",
        action="store_true",
        help="evaluate every generation checkpoint instead of initial and final checkpoints",
    )
    multi_seed_cmd.add_argument(
        "--quick",
        action="store_true",
        help="rapid rerun with 1 generation and minimal population for testing",
    )
    multi_seed_cmd.add_argument(
        "--opponent",
        type=str,
        default="HeuristicBaseline",
        choices=["HeuristicBaseline", "RandomBaseline"],
        help="opponent policy for evaluation",
    )
    multi_seed_cmd.add_argument(
        "--bootstrap-resamples",
        type=int,
        default=1000,
        help="number of bootstrap resamples for confidence interval estimation",
    )
    multi_seed_cmd.add_argument(
        "--alpha",
        type=float,
        default=0.05,
        help="significance level alpha for confidence interval (defaults to 0.05 for 95% CI)",
    )
    multi_seed_cmd.add_argument(
        "--bootstrap-seed",
        type=int,
        default=42,
        help="PRNG seed for bootstrap resampling",
    )
    multi_seed_cmd.add_argument(
        "--spec",
        type=Path,
        default=Path("experiments/protect-pp.json"),
        help="path to experiment specification",
    )
    multi_seed_cmd.add_argument(
        "--manifest",
        type=Path,
        default=Path("experiments/teams/protect-pp.json"),
        help="path to Open Team Sheet manifest",
    )
    multi_seed_cmd.add_argument(
        "--showdown-dir",
        type=Path,
        default=None,
        help="path to local pokemon-showdown checkout",
    )

    # Subcommand: explain-replay
    explain_cmd = subcommands.add_parser(
        "explain-replay",
        help="produce a replay explanation with repeated-rollout evidence for a battle decision",
    )
    explain_cmd.add_argument(
        "--replay",
        type=Path,
        required=True,
        help="path to replay file (.json.gz or .json)",
    )
    explain_cmd.add_argument(
        "--decision-index",
        type=int,
        default=None,
        help="index of decision to explain (defaults to auto-detecting candidate Protect decision)",
    )
    explain_cmd.add_argument(
        "--actual-choice",
        type=str,
        default=None,
        help="override choice string for the candidate at the target decision",
    )
    explain_cmd.add_argument(
        "--alternative",
        type=str,
        action="append",
        default=None,
        help="specific alternative choice string to evaluate (can be repeated)",
    )
    explain_cmd.add_argument(
        "--trials",
        type=int,
        default=10,
        help="number of rollout trials per alternative per opponent policy (default: 10)",
    )
    explain_cmd.add_argument(
        "--opponent-policies",
        type=str,
        default="HeuristicBaseline,RandomBaseline",
        help="comma-separated opponent policies (default: HeuristicBaseline,RandomBaseline)",
    )
    explain_cmd.add_argument(
        "--checkpoint",
        type=Path,
        default=None,
        help="path to trained candidate checkpoint JSON",
    )
    explain_cmd.add_argument(
        "--seed-base",
        type=int,
        default=1000,
        help="base seed for rollout PRNG reseeding (default: 1000)",
    )
    explain_cmd.add_argument(
        "--output",
        type=Path,
        default=None,
        help="output JSON path to save the explanation artifact",
    )
    explain_cmd.add_argument(
        "--showdown-dir",
        type=Path,
        default=None,
        help="path to local pokemon-showdown checkout",
    )

    args = parser.parse_args(argv)

    if args.command == "check":
        try:
            data: object = json.loads(args.spec.read_text(encoding="utf-8"))
            spec = validate_spec(data)
        except (OSError, UnicodeError, ValueError) as error:
            print(f"Invalid specification: {error}", file=sys.stderr)
            return 2
        payload: dict[str, Any] = {
            "name": spec.name,
            "simulator_revision": spec.simulator_revision,
            "information_mode": spec.information_mode,
            "training_seeds": spec.training_seeds,
            "variants": spec.variants,
            "pending_gates": spec.pending_gates,
            "scope": "Specification validation only. No battles or mechanics checks ran.",
        }
        if spec.evaluation is not None:
            payload["evaluation"] = dataclasses.asdict(spec.evaluation)
        print(json.dumps(payload, indent=2))
        if args.require_ready and spec.pending_gates:
            return 1
        return 0

    if args.command == "verify-mechanics":
        expected_rev = "9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e"
        spec_data: dict[str, Any] | None = None
        if args.spec:
            try:
                raw_spec: object = json.loads(args.spec.read_text(encoding="utf-8"))
                checked = validate_spec(raw_spec)
                expected_rev = checked.simulator_revision
                if isinstance(raw_spec, dict):
                    spec_data = raw_spec
            except Exception as e:
                print(f"Failed to load spec {args.spec}: {e}", file=sys.stderr)
                return 2

        try:
            report = verify_all_mechanics(
                showdown_dir=args.showdown_dir,
                expected_revision=expected_rev,
            )
        except Exception as e:
            print(f"Mechanics verification error: {e}", file=sys.stderr)
            return 2

        report_dict = dataclasses.asdict(report)
        print(json.dumps(report_dict, indent=2))

        if not report.all_passed:
            return 1

        if args.update_spec and args.spec and spec_data is not None:
            readiness = spec_data.get("readiness")
            if isinstance(readiness, dict):
                readiness["mechanics_verified"] = True
                args.spec.write_text(json.dumps(spec_data, indent=2) + "\n", encoding="utf-8")
                print(f"Updated {args.spec}: mechanics_verified = True")

        return 0

    if args.command == "benchmark-agent":
        from vgc_rulebreak.agents.benchmark import benchmark_agent_pair
        from vgc_rulebreak.agents.heuristic import HeuristicAgent
        from vgc_rulebreak.agents.random import RandomAgent

        p1 = HeuristicAgent("HeuristicBaseline")
        p2 = RandomAgent("RandomBaseline", seed=42)
        try:
            bench_report = benchmark_agent_pair(
                p1_agent=p1,
                p2_agent=p2,
                matches=args.matches,
                showdown_dir=args.showdown_dir,
            )
        except Exception as e:
            print(f"Benchmark error: {e}", file=sys.stderr)
            return 2

        print(json.dumps(dataclasses.asdict(bench_report), indent=2))
        if bench_report.p1_win_rate < args.min_win_rate:
            print(
                f"Agent win rate {bench_report.p1_win_rate:.2%} below "
                f"threshold {args.min_win_rate:.2%}",
                file=sys.stderr,
            )
            return 1
        return 0

    if args.command == "pilot-eval":
        if getattr(args, "scarcity", False):
            from vgc_rulebreak.pilot import run_scarcity_pilot

            try:
                scarcity_report = run_scarcity_pilot(
                    manifest_path=args.manifest,
                    pairs=args.sample_pairs,
                    showdown_dir=args.showdown_dir,
                )
            except Exception as e:
                print(f"Scarcity pilot error: {e}", file=sys.stderr)
                return 2

            print(json.dumps(dataclasses.asdict(scarcity_report), indent=2))
            return 0

        from vgc_rulebreak.pilot import run_pilot_evaluation, update_spec_with_pilot

        try:
            pilot_report = run_pilot_evaluation(
                manifest_path=args.manifest,
                sample_pairs=args.sample_pairs,
                showdown_dir=args.showdown_dir,
            )
        except Exception as e:
            print(f"Pilot evaluation error: {e}", file=sys.stderr)
            return 2

        print(json.dumps(dataclasses.asdict(pilot_report), indent=2))

        if args.update_spec and args.spec:
            try:
                update_spec_with_pilot(args.spec, pilot_report)
                print(
                    f"Updated {args.spec}: pairs_per_matchup="
                    f"{pilot_report.recommended_pairs_per_matchup}, "
                    f"compute_budget_seconds={pilot_report.recommended_compute_budget_seconds}"
                )
            except Exception as e:
                print(f"Failed to update spec {args.spec}: {e}", file=sys.stderr)
                return 2

        return 0

    if args.command == "evaluate":
        from vgc_rulebreak.evaluation import (
            get_evaluation_plan,
            run_evaluation_suite,
            verify_frozen_evaluation,
        )
        from vgc_rulebreak.manifest import load_manifest

        try:
            raw_spec = json.loads(args.spec.read_text(encoding="utf-8"))
            spec = validate_spec(raw_spec)
        except Exception as e:
            print(f"Failed to load spec {args.spec}: {e}", file=sys.stderr)
            return 2

        try:
            manifest = load_manifest(args.manifest)
        except Exception as e:
            print(f"Failed to load manifest {args.manifest}: {e}", file=sys.stderr)
            return 2

        try:
            verify_frozen_evaluation(spec, manifest)
        except Exception as e:
            print(f"Evaluation setup error: {e}", file=sys.stderr)
            return 2

        if args.check_only:
            plan = get_evaluation_plan(spec, manifest, pairs_override=args.pairs)
            print(json.dumps(plan, indent=2))
            return 0

        target_opponents = [args.opponent] if args.opponent else None
        target_variants = [args.variant] if args.variant else None
        target_seeds = [args.seed] if args.seed else None
        recorder = make_recorder(args.output_dir, manifest)
        candidate: Any = args.agent
        if args.checkpoint is not None:
            from vgc_rulebreak.agents.trained import checkpoint_agent

            try:
                candidate = checkpoint_agent(args.checkpoint)
            except Exception as e:
                print(f"Failed to load checkpoint {args.checkpoint}: {e}", file=sys.stderr)
                return 2

        try:
            summary = run_evaluation_suite(
                spec=spec,
                manifest=manifest,
                candidate=candidate,
                opponent_policies=target_opponents,
                evaluation_seeds=target_seeds,
                variants=target_variants,
                pairs_per_matchup=args.pairs,
                showdown_dir=args.showdown_dir,
                recorder=recorder,
            )
        except Exception as e:
            print(f"Evaluation error: {e}", file=sys.stderr)
            return 2

        summary_dict = dataclasses.asdict(summary)
        if recorder is not None:
            finish_recorder(recorder, "evaluate", spec, args, summary_dict)
        print(json.dumps(summary_dict, indent=2))
        return 0

    if args.command == "train":
        from vgc_rulebreak.manifest import load_manifest
        from vgc_rulebreak.training import TrainingConfig, train_protect_policy

        try:
            spec = validate_spec(json.loads(args.spec.read_text(encoding="utf-8")))
            manifest = load_manifest(args.manifest)
        except Exception as e:
            print(f"Failed to load spec or manifest: {e}", file=sys.stderr)
            return 2

        config = TrainingConfig(
            agent=args.agent,
            training_seed=args.seed,
            generations=args.generations,
            population=args.population,
            elites=args.elites,
            pairs=args.pairs,
            workers=args.workers,
        )
        try:
            paths = train_protect_policy(
                spec,
                manifest,
                config,
                args.output_dir,
                init_checkpoint=args.init,
                showdown_dir=args.showdown_dir,
            )
        except ValueError as e:
            print(f"Training setup error: {e}", file=sys.stderr)
            return 2
        except Exception as e:
            print(f"Training error: {e}", file=sys.stderr)
            return 1

        print(json.dumps({"checkpoints": [str(p) for p in paths]}, indent=2))
        return 0

    if args.command == "summarize-recovery":
        from vgc_rulebreak.recovery import summarize_recovery

        dataset = summarize_recovery(args.runs.rglob("results.json"))
        if not dataset["series"]:
            print(f"No checkpoint evaluations found under {args.runs}", file=sys.stderr)
            return 2
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(dataset, indent=2) + "\n", encoding="utf-8")
        points = sum(len(s["points"]) for s in dataset["series"])
        print(f"Wrote {len(dataset['series'])} series, {points} points to {args.output}")
        return 0

    if args.command == "export-showcase":
        from vgc_rulebreak.showcase import export_showcase, load_dex_names
        from vgc_rulebreak.simulator.process import ShowdownProcess

        try:
            showdown_dir = ShowdownProcess._resolve_showdown_dir(args.showdown_dir)
        except FileNotFoundError as exc:
            print(exc, file=sys.stderr)
            return 2
        meta = export_showcase(
            args.runs, args.output, lambda ids: load_dex_names(showdown_dir, ids)
        )
        if not meta["games"]:
            print(f"No checkpoint evaluations found under {args.runs}", file=sys.stderr)
            return 2
        print(f"Wrote {meta['games']} battles from {meta['checkpoints']} runs to {args.output}")
        return 0

    if args.command == "compare-agents":
        from vgc_rulebreak.evaluation import compare_study_agents
        from vgc_rulebreak.manifest import load_manifest

        try:
            raw_spec = json.loads(args.spec.read_text(encoding="utf-8"))
            spec = validate_spec(raw_spec)
        except Exception as e:
            print(f"Failed to load spec {args.spec}: {e}", file=sys.stderr)
            return 2

        try:
            manifest = load_manifest(args.manifest)
        except Exception as e:
            print(f"Failed to load manifest {args.manifest}: {e}", file=sys.stderr)
            return 2

        recorder = make_recorder(args.output_dir, manifest)
        try:
            comp_report = compare_study_agents(
                spec=spec,
                manifest=manifest,
                opponent_policy=args.opponent,
                eval_seed=args.seed,
                pairs=args.pairs,
                quick=args.quick,
                showdown_dir=args.showdown_dir,
                recorder=recorder,
            )
        except Exception as e:
            print(f"Agent comparison error: {e}", file=sys.stderr)
            return 2

        report_dict = dataclasses.asdict(comp_report)
        if recorder is not None:
            finish_recorder(recorder, "compare-agents", spec, args, report_dict)
        print(json.dumps(report_dict, indent=2))
        return 0

    if args.command == "anti-meta-check":
        from vgc_rulebreak.anti_meta import load_usage_snapshot, validate_anti_meta_team
        from vgc_rulebreak.champions import load_champions_regulation, validate_champions_ruleset
        from vgc_rulebreak.manifest import load_manifest

        try:
            reg = load_champions_regulation(args.regulation)
            manifest = load_manifest(args.manifest)
            snapshot = load_usage_snapshot(reg.usage_snapshot_path)
        except Exception as e:
            print(f"Check error: {e}", file=sys.stderr)
            return 2

        ref_team = manifest.teams.get("reference-hippowdon-sand")
        if ref_team is None:
            print("Missing reference-hippowdon-sand in manifest", file=sys.stderr)
            return 1

        valid, reason = validate_anti_meta_team(ref_team, snapshot)
        if not valid:
            print(f"Reference team validation failed: {reason}", file=sys.stderr)
            return 1

        sim_passed = True
        if args.verify_simulator:
            sim_passed = validate_champions_ruleset(reg, showdown_dir=args.showdown_dir)
            if not sim_passed:
                print("Champions simulator mechanics verification failed", file=sys.stderr)
                return 1

        print(
            json.dumps(
                {
                    "regulation_id": reg.regulation_id,
                    "staple_ban_threshold": reg.staple_ban_threshold,
                    "banned_species_count": len(snapshot.banned_species),
                    "reference_team_valid": valid,
                    "simulator_verified": sim_passed,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "anti-meta-eval":
        from vgc_rulebreak.anti_meta import evaluate_anti_meta_team
        from vgc_rulebreak.manifest import load_manifest

        try:
            manifest = load_manifest(args.manifest)
        except Exception as e:
            print(f"Failed to load manifest: {e}", file=sys.stderr)
            return 2

        team = manifest.teams.get(args.team)
        if team is None:
            print(f"Team {args.team} not found in manifest", file=sys.stderr)
            return 1

        try:
            am_summary = evaluate_anti_meta_team(
                team=team,
                manifest=manifest,
                split_name=args.split,
                pairs_per_matchup=args.pairs,
                seed_base=args.seed,
                showdown_dir=args.showdown_dir,
            )
        except Exception as e:
            print(f"Anti-meta evaluation error: {e}", file=sys.stderr)
            return 2

        print(json.dumps(dataclasses.asdict(am_summary), indent=2))
        return 0

    if args.command == "anti-meta-search":
        from vgc_rulebreak.anti_meta import load_usage_snapshot, search_support_rosters
        from vgc_rulebreak.champions import load_champions_regulation
        from vgc_rulebreak.manifest import load_manifest

        try:
            reg = load_champions_regulation(args.regulation)
            manifest = load_manifest(args.manifest)
            snapshot = load_usage_snapshot(reg.usage_snapshot_path)
        except Exception as e:
            print(f"Anti-meta search load error: {e}", file=sys.stderr)
            return 2

        try:
            res = search_support_rosters(
                manifest=manifest,
                snapshot=snapshot,
                budget_evaluations=args.budget,
                seed=args.seed,
                showdown_dir=args.showdown_dir,
            )
        except Exception as e:
            print(f"Anti-meta search execution error: {e}", file=sys.stderr)
            return 2

        print(json.dumps(dataclasses.asdict(res), indent=2))
        return 0

    if args.command == "anti-meta-compare":
        from vgc_rulebreak.anti_meta import (
            compare_anti_meta_agents,
            load_usage_snapshot,
        )
        from vgc_rulebreak.champions import load_champions_regulation
        from vgc_rulebreak.manifest import load_manifest

        try:
            reg = load_champions_regulation(args.regulation)
            manifest = load_manifest(args.manifest)
            snapshot = load_usage_snapshot(reg.usage_snapshot_path)
        except Exception as e:
            print(f"Anti-meta compare load error: {e}", file=sys.stderr)
            return 2

        team = manifest.teams.get(args.team)
        if team is None:
            print(f"Team {args.team} not found in manifest", file=sys.stderr)
            return 1

        try:
            comp_res = compare_anti_meta_agents(
                team=team,
                manifest=manifest,
                snapshot=snapshot,
                pairs_per_matchup=args.pairs,
                seed_base=args.seed,
                showdown_dir=args.showdown_dir,
            )
        except Exception as e:
            print(f"Anti-meta compare execution error: {e}", file=sys.stderr)
            return 2

        print(json.dumps(dataclasses.asdict(comp_res), indent=2))
        return 0

    if args.command == "anti-meta-shift":
        from vgc_rulebreak.anti_meta import (
            evaluate_meta_shift,
            load_usage_snapshot,
        )
        from vgc_rulebreak.manifest import load_manifest

        try:
            manifest = load_manifest(args.manifest)
            init_snap = load_usage_snapshot(args.initial_snapshot)
            shift_snap = load_usage_snapshot(args.shifted_snapshot)
        except Exception as e:
            print(f"Anti-meta shift load error: {e}", file=sys.stderr)
            return 2

        team = manifest.teams.get(args.team)
        if team is None:
            print(f"Team {args.team} not found in manifest", file=sys.stderr)
            return 1

        try:
            shift_res = evaluate_meta_shift(
                team=team,
                manifest=manifest,
                initial_snapshot=init_snap,
                shifted_snapshot=shift_snap,
                pairs_per_matchup=args.pairs,
                seed_base=args.seed,
                showdown_dir=args.showdown_dir,
            )
        except Exception as e:
            print(f"Anti-meta shift execution error: {e}", file=sys.stderr)
            return 2

        print(json.dumps(dataclasses.asdict(shift_res), indent=2))
        return 0

    if args.command == "protect-rerun":
        from vgc_rulebreak.manifest import load_manifest
        from vgc_rulebreak.protect_rerun import ProtectRerunConfig, run_protect_rerun

        try:
            spec = validate_spec(json.loads(args.spec.read_text(encoding="utf-8")))
            manifest = load_manifest(args.manifest)
        except Exception as e:
            print(f"Failed to load spec or manifest: {e}", file=sys.stderr)
            return 2

        generations = 1 if args.quick else args.generations
        population = 2 if args.quick else args.population
        elites = 1 if args.quick else args.elites

        rerun_config = ProtectRerunConfig(
            training_seed=args.training_seed,
            eval_seed=args.eval_seed,
            generations=generations,
            population=population,
            elites=elites,
            pairs=args.pairs,
            eval_pairs=args.eval_pairs,
            workers=args.workers,
            eval_all_checkpoints=args.eval_all_checkpoints,
        )

        try:
            rerun_report = run_protect_rerun(
                output_dir=args.output_dir,
                config=rerun_config,
                spec=spec,
                manifest=manifest,
                showdown_dir=args.showdown_dir,
            )
        except Exception as e:
            print(f"Protect rerun error: {e}", file=sys.stderr)
            return 1

        print(json.dumps(dataclasses.asdict(rerun_report), indent=2))
        return 0

    if args.command == "protect-multi-seed":
        from vgc_rulebreak.manifest import load_manifest
        from vgc_rulebreak.protect_multi_seed import (
            ProtectMultiSeedConfig,
            run_protect_multi_seed,
        )

        try:
            spec = validate_spec(json.loads(args.spec.read_text(encoding="utf-8")))
            manifest = load_manifest(args.manifest)
        except Exception as e:
            print(f"Failed to load spec or manifest: {e}", file=sys.stderr)
            return 2

        generations = 1 if args.quick else args.generations
        population = 2 if args.quick else args.population
        elites = 1 if args.quick else args.elites

        multi_config = ProtectMultiSeedConfig(
            training_seeds=tuple(args.training_seeds),
            eval_seed=args.eval_seed,
            generations=generations,
            population=population,
            elites=elites,
            pairs=args.pairs,
            eval_pairs=args.eval_pairs,
            workers=args.workers,
            eval_all_checkpoints=args.eval_all_checkpoints,
            opponent_policy=args.opponent,
            bootstrap_resamples=args.bootstrap_resamples,
            alpha=args.alpha,
            bootstrap_seed=args.bootstrap_seed,
        )

        try:
            multi_report = run_protect_multi_seed(
                output_dir=args.output_dir,
                config=multi_config,
                spec=spec,
                manifest=manifest,
                showdown_dir=args.showdown_dir,
            )
        except Exception as e:
            print(f"Protect multi-seed error: {e}", file=sys.stderr)
            return 1

        print(json.dumps(dataclasses.asdict(multi_report), indent=2))
        return 0

    if args.command == "explain-replay":
        from vgc_rulebreak.explanation import produce_replay_explanation

        policies = tuple(p.strip() for p in args.opponent_policies.split(",") if p.strip())
        alts = None
        if args.alternative:
            alts = [(a, f"Custom alternative: {a}") for a in args.alternative]

        try:
            explanation = produce_replay_explanation(
                replay_path=args.replay,
                decision_index=args.decision_index,
                candidate_choice_override=args.actual_choice,
                alternative_choices=alts,
                trials_per_action=args.trials,
                opponent_policies=policies,
                checkpoint_path=args.checkpoint,
                seed_base=args.seed_base,
                showdown_dir=args.showdown_dir,
                output_path=args.output,
            )
        except Exception as e:
            print(f"Explain replay error: {e}", file=sys.stderr)
            return 1

        print(json.dumps(explanation, indent=2))
        return 0

    return 0
