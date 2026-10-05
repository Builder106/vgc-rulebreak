"""Check a study specification without running battles."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from vgc_rulebreak.spec import validate_spec


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    check = subcommands.add_parser("check", help="validate a Protect study specification")
    check.add_argument("spec", type=Path)
    check.add_argument(
        "--require-ready", action="store_true", help="fail if readiness declarations are missing"
    )
    args = parser.parse_args(argv)
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
