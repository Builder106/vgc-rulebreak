"""CLI commands for specification checks and mechanics verification."""

import argparse
import dataclasses
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from vgc_rulebreak.fixtures.mechanics import verify_all_mechanics
from vgc_rulebreak.spec import validate_spec


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
        choices=["heuristic", "random"],
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

        try:
            summary = run_evaluation_suite(
                spec=spec,
                manifest=manifest,
                candidate=args.agent,
                opponent_policies=target_opponents,
                evaluation_seeds=target_seeds,
                variants=target_variants,
                pairs_per_matchup=args.pairs,
                showdown_dir=args.showdown_dir,
            )
        except Exception as e:
            print(f"Evaluation error: {e}", file=sys.stderr)
            return 2

        print(json.dumps(dataclasses.asdict(summary), indent=2))
        return 0

    return 0
