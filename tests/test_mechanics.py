import json
from pathlib import Path
from unittest.mock import patch

import pytest

from vgc_rulebreak.cli import main
from vgc_rulebreak.fixtures.mechanics import (
    MechanicsReport,
    ProtectPPVerification,
    RageFistVerification,
    SpeedStatsVerification,
    verify_all_mechanics,
)
from vgc_rulebreak.simulator.process import ShowdownProcess


def _showdown_available() -> bool:
    try:
        ShowdownProcess._resolve_showdown_dir(None)
        return True
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _showdown_available(), reason="Showdown not found in default paths")
def test_verify_all_mechanics_live() -> None:
    report = verify_all_mechanics()
    assert report.all_passed is True
    assert report.protect_pp.passed is True
    assert report.protect_pp.gen9_max_pp == 16
    assert report.protect_pp.champions_max_pp == 8

    assert report.rage_fist.passed is True
    assert report.rage_fist.gen9_hits_after_switch == 1
    assert report.rage_fist.champions_hits_after_switch == 0

    assert report.speed_stats.passed is True


def test_cli_verify_mechanics_mocked(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fake_report = MechanicsReport(
        simulator_revision="9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e",
        protect_pp=ProtectPPVerification(gen9_max_pp=16, champions_max_pp=8, passed=True),
        rage_fist=RageFistVerification(
            gen9_hits_after_switch=1, champions_hits_after_switch=0, passed=True
        ),
        speed_stats=SpeedStatsVerification(
            gen9_spe={"flutter_spe": 405, "ogerpon_spe": 350},
            champions_spe={"flutter_spe": 447, "ogerpon_spe": 420},
            passed=True,
        ),
        all_passed=True,
    )

    spec_file = tmp_path / "spec.json"
    spec_content = {
        "schema_version": 1,
        "name": "protect-pp",
        "question": "How does Protect PP change?",
        "simulator_revision": "9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e",
        "base_format": "gen9doublescustomgame",
        "information_mode": "open",
        "training_seeds": [11, 29, 47],
        "variants": [
            {"name": "protect-16", "rules": {"protect_max_pp": 16}},
            {"name": "protect-8", "rules": {"protect_max_pp": 8}},
        ],
        "readiness": {
            "mechanics_verified": False,
            "team_manifest": None,
            "pairs_per_matchup": None,
            "compute_budget_seconds": None,
        },
    }
    spec_file.write_text(json.dumps(spec_content), encoding="utf-8")

    with patch("vgc_rulebreak.cli.verify_all_mechanics", return_value=fake_report):
        code = main(["verify-mechanics", "--spec", str(spec_file), "--update-spec"])
        assert code == 0

    captured = capsys.readouterr()
    assert '"all_passed": true' in captured.out
    updated_data = json.loads(spec_file.read_text(encoding="utf-8"))
    assert updated_data["readiness"]["mechanics_verified"] is True
