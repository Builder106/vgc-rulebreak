import json
from pathlib import Path

import pytest

from vgc_rulebreak.manifest import load_manifest, validate_manifest

MANIFEST_PATH = Path(__file__).resolve().parents[1] / "experiments" / "teams" / "protect-pp.json"


def test_load_protect_pp_manifest() -> None:
    manifest = load_manifest(MANIFEST_PATH)
    assert manifest.schema_version == 1
    assert manifest.name == "protect-pp-teams"
    assert manifest.base_format == "gen9doublescustomgame"
    assert set(manifest.splits.keys()) == {"training", "validation", "test"}

    # Verify distinct teams across splits
    all_teams: list[str] = []
    for split_teams in manifest.splits.values():
        all_teams.extend(split_teams)
    assert len(all_teams) == len(set(all_teams))

    # Verify each team has 6 members and valid packed string
    for team_id, team in manifest.teams.items():
        assert len(team.pokemon) == 6
        assert len(team.packed) > 0
        assert team.id == team_id


def test_rejects_duplicate_team_id_across_splits() -> None:
    raw: dict[str, object] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw["splits"] = {
        "training": ["team-a"],
        "validation": ["team-a"],
        "test": ["team-b"],
    }
    with pytest.raises(ValueError, match="duplicate team ID across splits"):
        validate_manifest(raw)


def test_rejects_missing_split_team_definition() -> None:
    raw: dict[str, object] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    raw["splits"] = {
        "training": ["team-a"],
        "validation": ["team-b"],
        "test": ["nonexistent-team"],
    }
    with pytest.raises(ValueError, match="missing definitions for"):
        validate_manifest(raw)
