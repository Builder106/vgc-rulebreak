"""Deterministic mechanics verification fixtures for Showdown Gen 9 and Champions rules."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vgc_rulebreak.simulator.process import ShowdownProcess


@dataclass(frozen=True)
class ProtectPPVerification:
    gen9_max_pp: int
    champions_max_pp: int
    passed: bool


@dataclass(frozen=True)
class RageFistVerification:
    gen9_hits_after_switch: int
    champions_hits_after_switch: int
    passed: bool


@dataclass(frozen=True)
class SpeedStatsVerification:
    gen9_spe: dict[str, int]
    champions_spe: dict[str, int]
    passed: bool


@dataclass(frozen=True)
class MechanicsReport:
    simulator_revision: str
    protect_pp: ProtectPPVerification
    rage_fist: RageFistVerification
    speed_stats: SpeedStatsVerification
    all_passed: bool


def _run_node_script(showdown_dir: Path, script: str) -> dict[str, Any]:
    cmd = ["node", "-e", script]
    result = subprocess.run(
        cmd,
        cwd=str(showdown_dir),
        capture_output=True,
        text=True,
        check=True,
    )
    raw = result.stdout.strip()
    return json.loads(raw)  # type: ignore[no-any-return]


def verify_protect_pp(showdown_dir: Path | str | None = None) -> ProtectPPVerification:
    resolved_dir = ShowdownProcess._resolve_showdown_dir(showdown_dir)
    script = """
    const {Battle} = require("./dist/sim/battle.js");
    const b1 = new Battle({formatid: "gen9customgame"});
    const m1 = b1.dex.moves.get("protect");
    const p1 = b1.calculatePP(m1, 3);

    const b2 = new Battle({formatid: "gen9championscustomgame"});
    const m2 = b2.dex.moves.get("protect");
    const p2 = b2.calculatePP(m2, 3);

    console.log(JSON.stringify({gen9_max_pp: p1, champions_max_pp: p2}));
    """
    data = _run_node_script(resolved_dir, script)
    gen9_pp = int(data["gen9_max_pp"])
    champions_pp = int(data["champions_max_pp"])
    passed = (gen9_pp == 16) and (champions_pp == 8)
    return ProtectPPVerification(
        gen9_max_pp=gen9_pp,
        champions_max_pp=champions_pp,
        passed=passed,
    )


def verify_rage_fist(showdown_dir: Path | str | None = None) -> RageFistVerification:
    resolved_dir = ShowdownProcess._resolve_showdown_dir(showdown_dir)
    script = """
    const {Battle} = require("./dist/sim/battle.js");

    function testRageFistSwitch(format) {
      const b = new Battle({formatid: format});
      b.setPlayer("p1", {name: "Alice", team: [
        {species: "Annihilape", ability: "vitalspirit", moves: ["ragefist", "protect"]},
        {species: "Pikachu", ability: "static", moves: ["protect"]}
      ]});
      b.setPlayer("p2", {name: "Bob", team: [
        {species: "Eevee", ability: "runaway", moves: ["bite", "protect"]}
      ]});

      b.makeChoices("default", "default");
      // Turn 1: Annihilape uses ragefist, Eevee bites Annihilape
      b.makeChoices("move 1", "move 1");

      // Turn 2: Switch Annihilape out for Pikachu
      b.makeChoices("switch 2", "move 1");

      // Turn 3: Switch Pikachu back to Annihilape, Eevee protects (no hit on Annihilape)
      b.makeChoices("switch 2", "move 2");

      return b.p1.active[0].timesAttacked;
    }

    const g9 = testRageFistSwitch("gen9customgame");
    const champ = testRageFistSwitch("gen9championscustomgame");
    console.log(JSON.stringify({gen9_hits: g9, champions_hits: champ}));
    """
    data = _run_node_script(resolved_dir, script)
    g9_hits = int(data["gen9_hits"])
    champ_hits = int(data["champions_hits"])
    passed = (g9_hits == 1) and (champ_hits == 0)
    return RageFistVerification(
        gen9_hits_after_switch=g9_hits,
        champions_hits_after_switch=champ_hits,
        passed=passed,
    )


def verify_speed_stats(showdown_dir: Path | str | None = None) -> SpeedStatsVerification:
    resolved_dir = ShowdownProcess._resolve_showdown_dir(showdown_dir)
    script = """
    const {Battle} = require("./dist/sim/battle.js");

    function getSpeStats(format) {
      const b = new Battle({formatid: format});
      const flutter = {
        species: "Flutter Mane",
        ability: "protosynthesis",
        nature: "Timid",
        evs: {hp: 0, atk: 0, def: 0, spa: 252, spd: 4, spe: 252},
        moves: ["moonblast"]
      };
      const ogerpon = {
        species: "Ogerpon-Wellspring",
        ability: "waterabsorb",
        nature: "Jolly",
        evs: {hp: 252, atk: 4, def: 0, spa: 0, spd: 0, spe: 252},
        moves: ["ivycudgel"]
      };
      b.setPlayer("p1", {name: "Alice", team: [flutter]});
      b.setPlayer("p2", {name: "Bob", team: [ogerpon]});
      b.makeChoices("default", "default");
      return {
        flutter_spe: b.p1.active[0].getStat("spe"),
        ogerpon_spe: b.p2.active[0].getStat("spe")
      };
    }

    const g9 = getSpeStats("gen9customgame");
    const champ = getSpeStats("gen9championscustomgame");
    console.log(JSON.stringify({gen9: g9, champions: champ}));
    """
    data = _run_node_script(resolved_dir, script)
    g9_spe = {str(k): int(v) for k, v in data["gen9"].items()}
    champ_spe = {str(k): int(v) for k, v in data["champions"].items()}
    # Flutter Mane Spe 405 vs 447, Ogerpon Spe 350 vs 420
    passed = (
        g9_spe["flutter_spe"] == 405
        and g9_spe["ogerpon_spe"] == 350
        and champ_spe["flutter_spe"] == 447
        and champ_spe["ogerpon_spe"] == 420
    )
    return SpeedStatsVerification(
        gen9_spe=g9_spe,
        champions_spe=champ_spe,
        passed=passed,
    )


def verify_all_mechanics(
    showdown_dir: Path | str | None = None,
    expected_revision: str = "9fb3a5b99f1a0bea17f495c5cc1bfe04fdd19c3e",
) -> MechanicsReport:
    protect_res = verify_protect_pp(showdown_dir)
    rage_res = verify_rage_fist(showdown_dir)
    speed_res = verify_speed_stats(showdown_dir)
    all_passed = protect_res.passed and rage_res.passed and speed_res.passed
    return MechanicsReport(
        simulator_revision=expected_revision,
        protect_pp=protect_res,
        rage_fist=rage_res,
        speed_stats=speed_res,
        all_passed=all_passed,
    )
