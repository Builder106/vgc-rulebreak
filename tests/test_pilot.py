"""Unit tests for pilot evaluation sizing and compute budget calibration."""

import json
from pathlib import Path

from vgc_rulebreak.manifest import load_manifest
from vgc_rulebreak.pilot import (
    PilotReport,
    _check_protect_depleted,
    _count_protect_choices,
    build_manifest_matchups,
    calculate_sample_size,
    update_spec_with_pilot,
)
from vgc_rulebreak.spec import validate_spec


def test_build_manifest_matchups() -> None:
    manifest_path = Path("experiments/teams/protect-pp.json")
    manifest = load_manifest(manifest_path)
    matchups = build_manifest_matchups(manifest)
    # 6 archetypes -> 6 * 5 / 2 = 15 unique pairwise matchups
    assert len(matchups) == 15
    for t1_id, t1_packed, t2_id, t2_packed in matchups:
        assert t1_id != t2_id
        assert t1_packed
        assert t2_packed


def test_calculate_sample_size() -> None:
    n1 = calculate_sample_size(0.20, min_detectable_effect=0.08)
    assert isinstance(n1, int)
    assert n1 >= 50

    n2 = calculate_sample_size(0.50, min_detectable_effect=0.05)
    assert isinstance(n2, int)
    assert n2 > n1


def test_check_protect_depleted() -> None:
    assert not _check_protect_depleted(None)
    assert not _check_protect_depleted({})

    active_with_pp = {
        "active": [
            {
                "moves": [
                    {"move": "Protect", "id": "protect", "pp": 3},
                    {"move": "Tackle", "id": "tackle", "pp": 10},
                ]
            }
        ]
    }
    assert not _check_protect_depleted(active_with_pp)

    active_depleted = {
        "active": [
            {
                "moves": [
                    {"move": "Protect", "id": "protect", "pp": 0},
                    {"move": "Tackle", "id": "tackle", "pp": 10},
                ]
            }
        ]
    }
    assert _check_protect_depleted(active_depleted)


def test_count_protect_choices() -> None:
    assert _count_protect_choices(None, None) == 0

    req = {
        "active": [
            {"moves": [{"id": "protect"}, {"id": "tackle"}]},
            {"moves": [{"id": "heatwave"}, {"id": "spikyshield"}]},
        ]
    }

    # Slot 0 uses move 1 (protect), slot 1 uses move 1 (heatwave) -> 1 protect use
    assert _count_protect_choices(req, "move 1, move 1") == 1

    # Slot 0 uses move 1 (protect), slot 1 uses move 2 (spikyshield) -> 2 protect uses
    assert _count_protect_choices(req, "move 1, move 2") == 2

    # Both use attacking moves -> 0 protect uses
    assert _count_protect_choices(req, "move 2, move 1") == 0


def test_update_spec_with_pilot(tmp_path: Path) -> None:
    spec_src = Path("experiments/protect-pp.json")
    spec_dest = tmp_path / "protect-pp.json"
    spec_dest.write_text(spec_src.read_text(encoding="utf-8"), encoding="utf-8")

    dummy_report = PilotReport(
        sample_pairs=3,
        total_pilot_battles=12,
        avg_turns=8.5,
        avg_duration_seconds=2.8,
        decisions_per_second=6.5,
        avg_turn_latency_ms=330.0,
        protect_16_uses_per_match=2.5,
        protect_8_uses_per_match=2.2,
        protect_16_depletion_rate=0.0,
        protect_8_depletion_rate=0.15,
        matchups_count=15,
        recommended_pairs_per_matchup=20,
        estimated_total_matches=1800,
        recommended_compute_budget_seconds=6300,
    )

    update_spec_with_pilot(spec_dest, dummy_report)

    # Validate updated spec
    raw_spec = json.loads(spec_dest.read_text(encoding="utf-8"))
    checked = validate_spec(raw_spec)
    assert checked.pending_gates == ()
    assert raw_spec["readiness"]["pairs_per_matchup"] == 20
    assert raw_spec["readiness"]["compute_budget_seconds"] == 6300
