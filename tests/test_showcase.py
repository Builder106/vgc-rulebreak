"""Tests for exporting evaluated games as showcase data."""

import gzip
import json
from pathlib import Path
from typing import Any

from vgc_rulebreak.showcase import (
    FrameBuilder,
    build_battle,
    export_showcase,
    public_lines,
    slot_choices,
)

NAMES = {
    "moves": {"protect": "Protect", "closecombat": "Close Combat", "fakeout": "Fake Out"},
    "items": {"leftovers": "Leftovers"},
    "abilities": {"defiant": "Defiant"},
}

LOG = [
    "|player|p1|native-s11-g10||",
    "|player|p2|HeuristicBaseline||",
    "|start",
    "|split|p1",
    "|switch|p1a: Urshifu|Urshifu-Rapid-Strike, F|179/179",
    "|switch|p1a: Urshifu|Urshifu-Rapid-Strike, F|100/100",
    "|switch|p2a: Maushold|Maushold|401/401",
    "|turn|1",
    "|move|p2a: Maushold|Protect|p2a: Maushold",
    "|-singleturn|p2a: Maushold|Protect",
    "|move|p1a: Urshifu|Close Combat|p2a: Maushold",
    "|-activate|p2a: Maushold|move: Protect",
    "|turn|2",
    "|move|p1a: Urshifu|Close Combat|p2a: Maushold",
    "|-supereffective|p2a: Maushold",
    "|split|p2",
    "|-damage|p2a: Maushold|0 fnt",
    "|-damage|p2a: Maushold|0/100",
    "|faint|p2a: Maushold",
    "|win|native-s11-g10",
]


def mon(ident: str, details: str, condition: str, moves: list[str]) -> dict[str, Any]:
    return {
        "ident": ident,
        "details": details,
        "condition": condition,
        "moves": moves,
        "item": "leftovers",
        "ability": "defiant",
        "stats": {"atk": 100, "def": 100, "spa": 100, "spd": 100, "spe": 100},
    }


def move_request(pp: int) -> dict[str, Any]:
    return {
        "active": [
            {
                "moves": [
                    {"move": "Protect", "id": "protect", "pp": pp, "maxpp": 8},
                    {"move": "Close Combat", "id": "closecombat", "pp": 8, "maxpp": 8},
                ]
            }
        ],
        "side": {
            "pokemon": [
                mon("p1: Urshifu", "Urshifu-Rapid-Strike, F", "179/179", ["protect", "closecombat"])
            ]
        },
    }


DECISIONS = [
    {
        "turn": 0,
        "side": "p1",
        "choice": "team 1",
        "request": {
            "teamPreview": True,
            "side": {
                "pokemon": [
                    mon(
                        "p1: Urshifu",
                        "Urshifu-Rapid-Strike, F",
                        "179/179",
                        ["protect", "closecombat"],
                    )
                ]
            },
        },
    },
    {"turn": 1, "side": "p1", "choice": "move 2 1", "request": move_request(8)},
    {"turn": 2, "side": "p1", "choice": "move 1", "request": move_request(7)},
]

GAME = {
    "game_id": "g00001",
    "variant": "protect-8",
    "format_id": "gen9championsdoublescustomgame",
    "eval_seed": 101,
    "battle_seed": [1, 2, 3, 4],
    "candidate": "native-s11-g10",
    "opponent": "HeuristicBaseline",
    "candidate_team": "test-a",
    "opponent_team": "test-b",
    "candidate_role": "p1",
    "result": "win",
    "end_reason": "win",
    "turns": 2,
    "candidate_protect_uses": 1,
    "candidate_protect_opportunities": 2,
    "opponent_protect_uses": 1,
    "protect_depleted": False,
    "replay": "replays/g00001.json.gz",
}

RUN = {
    "name": "native-s11-g10",
    "agent": "native",
    "seed": 11,
    "generation": 10,
    "checkpoint": "native-s11-g10.json",
    "simulator_revision": "9fb3a5b",
}


def test_public_lines_keeps_the_secret_copy_only() -> None:
    lines = list(public_lines(LOG))
    assert "|switch|p1a: Urshifu|Urshifu-Rapid-Strike, F|179/179" in lines
    assert "|switch|p1a: Urshifu|Urshifu-Rapid-Strike, F|100/100" not in lines
    assert not any(line.startswith("|split|") for line in lines)


def test_frames_track_the_field_and_describe_events() -> None:
    builder = FrameBuilder({"p1": "Native", "p2": "Baseline"})
    for line in public_lines(LOG):
        builder.feed(line)
    builder.finish()

    assert builder.prelude == [
        "Native sent out Urshifu-Rapid-Strike.",
        "Baseline sent out Maushold.",
    ]
    first, second = builder.frames
    assert first["turn"] == 1
    assert first["field"]["p1"][0] == {
        "species": "Urshifu-Rapid-Strike",
        "hp": 179,
        "maxhp": 179,
        "fainted": False,
        "status": None,
    }
    assert first["events"] == [
        "Baseline's Maushold used Protect.",
        "Baseline's Maushold protected itself.",
        "Native's Urshifu-Rapid-Strike used Close Combat on Baseline's Maushold.",
        "Baseline's Maushold was protected by Protect.",
    ]
    assert second["events"][-2:] == ["Baseline's Maushold fainted.", "Native won."]
    assert first["after"] == second["field"]
    assert second["after"]["p2"][0]["fainted"] is True
    assert builder.field["p2"]["a"] == {
        "species": "Maushold",
        "hp": 0,
        "maxhp": 401,
        "fainted": True,
        "status": None,
    }


def test_slot_choices_show_pp_and_the_pick() -> None:
    slots = slot_choices(DECISIONS[2], NAMES)
    assert slots is not None
    (slot,) = slots
    assert slot["species"] == "Urshifu-Rapid-Strike"
    assert slot["moves"][0] == {
        "name": "Protect",
        "pp": 7,
        "maxpp": 8,
        "disabled": False,
        "protect": True,
    }
    assert slot["chosen"] == {"kind": "move", "index": 0, "name": "Protect"}
    assert slot_choices(DECISIONS[0], NAMES) is None


def test_build_battle_attaches_choices_and_rosters() -> None:
    battle = build_battle(7, RUN, GAME, {"log": LOG, "decisions": DECISIONS}, NAMES)
    assert battle["id"] == "0007"
    assert battle["labels"] == {"p1": "Native", "p2": "Baseline"}
    assert battle["teams"] == {"p1": "test-a", "p2": "test-b"}
    assert battle["frames"][0]["choices"]["p1"][0]["chosen"]["name"] == "Close Combat"
    assert battle["frames"][1]["choices"]["p1"][0]["moves"][0]["pp"] == 7
    (member,) = battle["rosters"]["p1"]
    assert member["item"] == "Leftovers"
    assert member["ability"] == "Defiant"
    assert member["moves"] == ["Protect", "Close Combat"]
    assert member["stats"]["hp"] == 179


def test_build_battle_handles_a_game_with_no_log() -> None:
    stalled = {**GAME, "result": "unfinished", "end_reason": "stalled", "turns": 0}
    battle = build_battle(1, RUN, stalled, {"log": [], "decisions": []}, NAMES)
    assert battle["frames"] == []
    assert battle["end_reason"] == "stalled"


def write_run(root: Path, name: str) -> None:
    run_dir = root / f"{name}-protect-8"
    (run_dir / "replays").mkdir(parents=True)
    replay = {"log": LOG, "decisions": DECISIONS}
    (run_dir / "replays" / "g00001.json.gz").write_bytes(gzip.compress(json.dumps(replay).encode()))
    document = {
        "spec": "protect-pp",
        "simulator_revision": "9fb3a5b",
        "options": {"checkpoint": f"/somewhere/checkpoints/{name}.json"},
        "summary": {"candidate_name": name},
        "games": [{**GAME, "candidate": name}],
    }
    (run_dir / "results.json").write_text(json.dumps(document), encoding="utf-8")


def test_export_showcase_writes_the_site_data(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    write_run(runs, "adapted-s11-g00")
    write_run(runs, "source-s11-g00")
    asked: list[dict[str, set[str]]] = []

    def names_for(ids: dict[str, set[str]]) -> dict[str, dict[str, str]]:
        asked.append(ids)
        return NAMES

    out = tmp_path / "data"
    meta = export_showcase(runs, out, names_for)

    assert meta["games"] == 2
    assert asked[0]["moves"] == {"protect", "closecombat"}
    index = json.loads((out / "battles.json").read_text())
    assert [row["run"] for row in index["battles"]] == ["source-s11-g00", "adapted-s11-g00"]
    assert index["battles"][0]["id"] == "0001"
    battle = json.loads(gzip.decompress((out / "battles" / "0002.json.gz").read_bytes()))
    assert battle["checkpoint"] == "adapted-s11-g00.json"
    assert "test-a" in json.loads((out / "teams.json").read_text())["teams"]
    assert json.loads((out / "recovery.json").read_text())["series"]
