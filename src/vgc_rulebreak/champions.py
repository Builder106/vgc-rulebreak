"""Pinned Champions regulation specification and validator."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vgc_rulebreak.fixtures.mechanics import verify_all_mechanics


@dataclass(frozen=True)
class ChampionsRegulation:
    schema_version: int
    regulation_id: str
    name: str
    season: str
    base_format: str
    ruleset: dict[str, Any]
    usage_snapshot_path: Path
    staple_ban_threshold: float


def load_champions_regulation(path: Path | str) -> ChampionsRegulation:
    """Load and validate a Champions regulation definition."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Champions regulation file not found: {path}")

    data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1:
        raise ValueError("Champions regulation schema_version must be 1")

    regulation_id = str(data.get("regulation_id", "")).strip()
    if not regulation_id:
        raise ValueError("regulation_id must be a non-empty string")

    name = str(data.get("name", "")).strip()
    season = str(data.get("season", "")).strip()
    base_format = str(data.get("base_format", "")).strip()
    if not base_format:
        raise ValueError("base_format must be specified")

    ruleset = data.get("ruleset")
    if not isinstance(ruleset, dict):
        raise ValueError("ruleset must be a dictionary")

    # Validate mandatory ruleset declarations
    required_rules = {
        "protect_max_pp",
        "rage_fist_switch_reset",
        "champions_speed_stats",
        "mega_evolution",
        "open_team_sheets",
    }
    if not required_rules.issubset(set(ruleset.keys())):
        missing = required_rules - set(ruleset.keys())
        raise ValueError(f"ruleset missing required mechanics: {', '.join(sorted(missing))}")

    if ruleset["protect_max_pp"] != 8:
        raise ValueError("Champions regulation must mandate 8 Protect max PP")
    if not ruleset["rage_fist_switch_reset"]:
        raise ValueError("Champions regulation must reset Rage Fist hit counter upon switch")
    if not ruleset["champions_speed_stats"]:
        raise ValueError("Champions regulation must specify champions speed stat calculation")
    if not ruleset["mega_evolution"]:
        raise ValueError("Champions regulation must enable Mega Evolution")
    if not ruleset["open_team_sheets"]:
        raise ValueError("Champions regulation must require Open Team Sheets (OTS)")

    raw_snapshot = data.get("usage_snapshot")
    if not raw_snapshot:
        raise ValueError("usage_snapshot path must be provided")
    snapshot_path = Path(raw_snapshot)
    if not snapshot_path.is_absolute():
        snapshot_path = p.parent / snapshot_path

    threshold = float(data.get("staple_ban_threshold", 15.0))
    if threshold <= 0.0 or threshold >= 100.0:
        raise ValueError("staple_ban_threshold must be between 0.0 and 100.0 percent")

    return ChampionsRegulation(
        schema_version=1,
        regulation_id=regulation_id,
        name=name,
        season=season,
        base_format=base_format,
        ruleset=ruleset,
        usage_snapshot_path=snapshot_path,
        staple_ban_threshold=threshold,
    )


def validate_champions_ruleset(
    regulation: ChampionsRegulation,
    showdown_dir: Path | str | None = None,
) -> bool:
    """Verify that the simulator environment supports all pinned Champions rules."""
    report = verify_all_mechanics(showdown_dir=showdown_dir)
    return report.all_passed
