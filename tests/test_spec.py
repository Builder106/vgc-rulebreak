import json
from pathlib import Path

import pytest

from vgc_rulebreak.cli import main
from vgc_rulebreak.spec import validate_spec

SPEC = Path(__file__).resolve().parents[1] / "experiments" / "protect-pp.json"


def test_spec_all_readiness_gates_complete() -> None:
    spec = validate_spec(json.loads(SPEC.read_text()))
    assert spec.variants == {"protect-16": 16, "protect-8": 8}
    assert spec.pending_gates == ()


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


def test_cli_accepts_ready_spec(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["check", str(SPEC)]) == 0
    assert "No battles or mechanics checks ran" in capsys.readouterr().out
    assert main(["check", str(SPEC), "--require-ready"]) == 0


def test_cli_refuses_incomplete_readiness(tmp_path: Path) -> None:
    draft = json.loads(SPEC.read_text())
    draft["readiness"]["pairs_per_matchup"] = None
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(draft), encoding="utf-8")
    assert main(["check", str(path), "--require-ready"]) == 1


def test_cli_rejects_missing_or_malformed_input(tmp_path: Path) -> None:
    path = tmp_path / "spec.json"
    assert main(["check", str(path)]) == 2
    path.write_text("{", encoding="utf-8")
    assert main(["check", str(path)]) == 2
