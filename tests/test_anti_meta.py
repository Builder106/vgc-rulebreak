from pathlib import Path

from vgc_rulebreak.anti_meta import (
    bootstrap_ci,
    load_usage_snapshot,
    validate_anti_meta_team,
)
from vgc_rulebreak.champions import load_champions_regulation
from vgc_rulebreak.manifest import load_manifest
from vgc_rulebreak.pilot import _min_protect_pp

REGULATION_PATH = Path(__file__).resolve().parents[1] / "experiments" / "champions-regulation.json"
USAGE_PATH = Path(__file__).resolve().parents[1] / "experiments" / "champions-usage-2026-06.json"
TEAMS_PATH = Path(__file__).resolve().parents[1] / "experiments" / "teams" / "anti-meta.json"


def test_load_champions_regulation() -> None:
    reg = load_champions_regulation(REGULATION_PATH)
    assert reg.schema_version == 1
    assert reg.regulation_id == "champions-reg-2026-06"
    assert reg.base_format == "gen9championsdoublescustomgame"
    assert reg.ruleset["protect_max_pp"] == 8
    assert reg.ruleset["mega_evolution"] is True
    assert reg.ruleset["open_team_sheets"] is True
    assert reg.staple_ban_threshold == 15.0


def test_load_usage_snapshot() -> None:
    snapshot = load_usage_snapshot(USAGE_PATH)
    assert snapshot.schema_version == 1
    assert snapshot.date == "2026-06-15"
    assert snapshot.staple_ban_threshold == 15.0

    # Top staples must be marked banned (usage >= 15%)
    assert snapshot.is_banned("Incineroar")
    assert snapshot.is_banned("Mega Charizard Y")
    assert snapshot.is_banned("Mega Floette")
    assert snapshot.is_banned("Archaludon")
    assert snapshot.is_banned("Sneasler")
    assert snapshot.is_banned("Basculegion")

    # Anchor and off-meta supports must not be banned (< 15%)
    assert not snapshot.is_banned("Hippowdon")
    assert not snapshot.is_banned("Farigiraf")
    assert not snapshot.is_banned("Tyranitar")
    assert not snapshot.is_banned("Sinistcha")
    assert not snapshot.is_banned("Decidueye")
    assert not snapshot.is_banned("Rotom-Heat")


def test_validate_anti_meta_team() -> None:
    snapshot = load_usage_snapshot(USAGE_PATH)
    manifest = load_manifest(TEAMS_PATH)

    # Reference Hippowdon team must be completely valid
    ref_team = manifest.teams["reference-hippowdon-sand"]
    valid, reason = validate_anti_meta_team(ref_team, snapshot)
    assert valid is True
    assert reason == "Valid anti-meta team"

    # Sun team containing Incineroar and Charizard Y must fail staple ban
    sun_team = manifest.teams["meta-sun-charizard"]
    valid_sun, reason_sun = validate_anti_meta_team(sun_team, snapshot)
    assert valid_sun is False
    assert "anchor" in reason_sun.lower() or "staple ban" in reason_sun.lower()


def test_bootstrap_ci() -> None:
    scores = [1.0, 1.0, 1.0, 0.5, 0.0, 1.0, 0.5, 1.0]
    ci_low, ci_high = bootstrap_ci(scores, n_resamples=500, seed=42)
    assert 0.0 <= ci_low <= ci_high <= 1.0
    assert ci_low >= 0.4
    assert ci_high <= 1.0


def test_min_protect_pp_helper() -> None:
    from typing import Any

    req_empty: dict[str, Any] = {}
    assert _min_protect_pp(req_empty) == 99

    req = {
        "active": [
            {
                "moves": [
                    {"id": "protect", "pp": 6},
                    {"id": "tackle", "pp": 35},
                ]
            },
            {
                "moves": [
                    {"id": "protect", "pp": 3},
                    {"id": "earthquake", "pp": 10},
                ]
            },
        ]
    }
    assert _min_protect_pp(req) == 3


def test_shifted_usage_snapshot() -> None:
    shifted_path = (
        Path(__file__).resolve().parents[1] / "experiments" / "champions-usage-2026-07.json"
    )
    snapshot = load_usage_snapshot(shifted_path)
    assert snapshot.schema_version == 1
    assert snapshot.date == "2026-07-15"
    assert snapshot.staple_ban_threshold == 15.0

    # In shifted meta, Pelipper and Ursaluna-Bloodmoon crossed into banned staples
    assert snapshot.is_banned("Pelipper")
    assert snapshot.is_banned("Ursaluna-Bloodmoon")
    assert snapshot.is_banned("Archaludon")

    # Torkoal and Chien-Pao fell below threshold
    assert not snapshot.is_banned("Torkoal")
    assert not snapshot.is_banned("Chien-Pao")

    # Anti-meta anchor and reference supports remain completely legal
    assert not snapshot.is_banned("Hippowdon")
    assert not snapshot.is_banned("Tyranitar")
    assert not snapshot.is_banned("Farigiraf")
    assert not snapshot.is_banned("Sinistcha")


def test_meta_agents_target_scoring() -> None:
    from vgc_rulebreak.agents.meta import (
        AdaptedAntiMetaAgent,
        BroadlyTunedAgent,
        MetaTunedAgent,
    )

    snapshot = load_usage_snapshot(USAGE_PATH)

    broad = BroadlyTunedAgent()
    meta = MetaTunedAgent(snapshot=snapshot, anchor="Hippowdon")
    adapted = AdaptedAntiMetaAgent(snapshot=snapshot, anchor="Hippowdon")

    # Broadly tuned agent is neutral
    assert broad.score_target_bonus("Charizard", target_slot=1, slot_idx=0) == 0.0
    assert broad.score_target_bonus("Hippowdon", target_slot=2, slot_idx=0) == 0.0

    # Meta-tuned agent prioritizes meta sweepers and discounts anchor
    assert meta.score_target_bonus("Charizard", target_slot=1, slot_idx=0) == 25.0
    assert meta.score_target_bonus("Hippowdon", target_slot=2, slot_idx=0) == -25.0

    # Adapted agent prioritizes anchor shutdown and support interruption
    assert adapted.score_target_bonus("Hippowdon", target_slot=2, slot_idx=0) == 35.0
    assert adapted.score_target_bonus("Farigiraf", target_slot=1, slot_idx=0) == 20.0


def test_agent_message_observation() -> None:
    from vgc_rulebreak.agents.meta import MetaTunedAgent
    from vgc_rulebreak.simulator.protocol import ParsedMessage

    agent = MetaTunedAgent()
    agent.reset()

    # Observe opponent switch
    msg_switch = ParsedMessage(
        raw="|switch|p2a: Charizard|Charizard, L50, M|100/100",
        msg_type="switch",
        args=("p2a: Charizard", "Charizard, L50, M", "100/100"),
        kwargs={},
    )
    agent.observe_message(msg_switch)
    assert agent._slot_species.get("p2a") == "Charizard"

    # Observe Trick Room fieldstart
    msg_tr = ParsedMessage(
        raw="|-fieldstart|move: Trick Room",
        msg_type="-fieldstart",
        args=("move: Trick Room",),
        kwargs={},
    )
    agent.observe_message(msg_tr)
    assert agent._trick_room_turns_left == 5
