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

    args = parser.parse_args(argv)

    if args.command == "check":
        try:
            data: object = json.loads(args.spec.read_text(encoding="utf-8"))
            spec = validate_spec(data)
        except (OSError, UnicodeError, ValueError) as error:
            print(f"Invalid specification: {error}", file=sys.stderr)
            return 2
        print(
            json.dumps(
                {
                    "name": spec.name,
                    "simulator_revision": spec.simulator_revision,
                    "information_mode": spec.information_mode,
                    "training_seeds": spec.training_seeds,
                    "variants": spec.variants,
                    "pending_gates": spec.pending_gates,
                    "scope": "Specification validation only. No battles or mechanics checks ran.",
                },
                indent=2,
            )
        )
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

    return 0
