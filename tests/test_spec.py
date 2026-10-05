import json
from pathlib import Path

import pytest

from vgc_rulebreak.cli import main
from vgc_rulebreak.spec import validate_spec

SPEC = Path(__file__).resolve().parents[1] / "experiments" / "protect-pp.json"


def test_draft_reports_remaining_gates() -> None:
    spec = validate_spec(json.loads(SPEC.read_text()))
    assert spec.variants == {"protect-16": 16, "protect-8": 8}
    assert set(spec.pending_gates) == {
        "mechanics_verified",
        "team_manifest",
        "pairs_per_matchup",
        "compute_budget_seconds",
    }


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("simulator_revision", "master"),
        ("information_mode", "omniscient"),
        ("training_seeds", [11, 11, 47]),
        ("training_seeds", [True, 29, 47]),
        ("schema_version", True),
        (
            "variants",
            [
                {"name": "a", "rules": {"protect_max_pp": 16, "rage_fist_reset": True}},
                {"name": "b", "rules": {"protect_max_pp": 8}},
            ],
        ),
        (
            "variants",
            [
                {"name": "a", "rules": {"protect_max_pp": 8}},
                {"name": "b", "rules": {"protect_max_pp": 8}},
            ],
        ),
        (
            "variants",
            [
                {"name": "a", "rules": {"protect_max_pp": 16}},
                {"name": "a", "rules": {"protect_max_pp": 8}},
            ],
        ),
        (
            "readiness",
            {
                "mechanics_verified": False,
                "team_manifest": None,
                "pairs_per_matchup": -1,
                "compute_budget_seconds": None,
            },
        ),
    ],
)
def test_rejects_invalid_controls(field: str, replacement: object) -> None:
    document: dict[str, object] = json.loads(SPEC.read_text())
    document[field] = replacement
    with pytest.raises(ValueError):
        validate_spec(document)


def test_cli_validates_but_refuses_incomplete_readiness(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(SPEC)]) == 0
    assert "No battles or mechanics checks ran" in capsys.readouterr().out
    assert main(["check", str(SPEC), "--require-ready"]) == 1


def test_cli_rejects_missing_or_malformed_input(tmp_path: Path) -> None:
    path = tmp_path / "spec.json"
    assert main(["check", str(path)]) == 2
    path.write_text("{", encoding="utf-8")
    assert main(["check", str(path)]) == 2
