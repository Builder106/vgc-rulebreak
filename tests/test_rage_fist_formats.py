"""Live single-factor controls for Study R's experimental doubles formats."""

import json
import subprocess
from pathlib import Path

import pytest

from vgc_rulebreak.simulator import process
from vgc_rulebreak.simulator.battle import BattleSession
from vgc_rulebreak.simulator.process import ShowdownProcess

FORMATS = ("gen9rulebreakragefistpersist", "gen9rulebreakragefistreset")


def _showdown_dir() -> Path | None:
    try:
        return ShowdownProcess._resolve_showdown_dir(None)
    except FileNotFoundError:
        return None


@pytest.mark.skipif(_showdown_dir() is None, reason="Showdown not found in default paths")
@pytest.mark.parametrize("switch_kind", ["manual", "pivot", "forced"])
def test_rage_fist_formats_change_only_switch_reset(switch_kind: str) -> None:
    showdown_dir = _showdown_dir()
    assert showdown_dir is not None
    overlay = Path(process.__file__).with_name("rage_fist_formats.cjs")
    script = """
    const assert = require('node:assert/strict');
    const {Battle} = require('./dist/sim/battle.js');
    const {Dex} = require('./dist/sim/dex.js');
    const ids = ['gen9rulebreakragefistpersist', 'gen9rulebreakragefistreset'];
    const base = Dex.formats.get('gen9doublescustomgame');
    // Compare all mechanics, excluding identity, menu placement, and the reset hook.
    function settings(format) {
      const {id, name, fullname, section, column, onSwitchOut, ...rest} = format;
      return rest;
    }
    for (const id of ids) assert.deepEqual(settings(Dex.formats.get(id)), settings(base));
    assert.equal(Dex.formats.get(ids[0]).onSwitchOut, undefined);
    assert.equal(typeof Dex.formats.get(ids[1]).onSwitchOut, 'function');

    const observations = ids.map(id => {
      const b = new Battle({formatid: id, seed: [101, 102, 103, 104]});
      b.setPlayer('p1', {name: 'Alice', team: [
        {species: 'Annihilape', ability: 'vitalspirit', nature: 'Jolly',
         evs: {spe: 252}, moves: ['ragefist', 'uturn', 'splash', 'protect']},
        {species: 'Magikarp', ability: 'swiftswim', moves: ['splash', 'protect']},
        {species: 'Pikachu', ability: 'static', moves: ['splash', 'protect']},
      ]});
      b.setPlayer('p2', {name: 'Bob', team: [
        {species: 'Umbreon', ability: 'synchronize', moves: ['bite', 'splash', 'roar']},
        {species: 'Magikarp', ability: 'swiftswim', moves: ['splash', 'protect']},
      ]});
      b.makeChoices('default', 'default');
      const ape = b.p1.active[0];
      const target = b.p2.active[0];
      const rageFist = b.dex.moves.get('ragefist');
      function snapshot() {
        return structuredClone({
          hits: ape.timesAttacked,
          power: rageFist.basePowerCallback.call(b, ape),
          mod: b.format.mod,
          pokemon: b.getAllPokemon().map(p => ({
            species: p.species.id, stats: p.storedStats, hp: p.hp,
            teraType: p.teraType, canTerastallize: p.canTerastallize,
            moves: p.moveSlots, baseMoves: p.baseMoveSlots,
          })),
        });
      }
      const initial = snapshot();
      b.makeChoices('move 1 1, move 1', 'move 1 1, move 1');
      const oneHit = snapshot();
      b.makeChoices('move 1 1, move 1', 'move 1 1, move 1');
      const beforeSwitch = snapshot();
      const preSwitchLog = b.log.filter(line =>
        !line.startsWith('|tier|') && !line.startsWith('|t:|'));
      const kind = process.argv[1];
      if (kind === 'manual') {
        b.makeChoices('switch 3, move 1', 'move 2, move 1');
      } else if (kind === 'pivot') {
        b.makeChoices('move 2 1, move 1', 'move 2, move 1');
        b.makeChoices('switch 3');
      } else {
        b.makeChoices('move 3, move 1', 'move 3 1, move 1');
      }
      assert.equal(b.p1.active[0].species.id, 'pikachu');
      const benchedHits = ape.timesAttacked;
      b.makeChoices('switch 3, move 1', 'move 2, move 1');
      assert.equal(b.p1.active[0], ape);
      const afterSwitch = snapshot();
      // Reuse the exact Gen 9 damage path with fixed rolls for comparable damage.
      b.randomizer = damage => damage;
      const damageAfterSwitch = b.actions.getDamage(ape, target, 'ragefist', true);
      b.makeChoices('move 3, move 1', 'move 1 1, move 1');
      const afterNewHit = snapshot();
      return {initial, oneHit, beforeSwitch, preSwitchLog, benchedHits,
        afterSwitch, damageAfterSwitch, afterNewHit};
    });
    console.log(JSON.stringify(observations));
    """
    result = subprocess.run(
        ["node", "--require", str(overlay), "-e", script, switch_kind],
        cwd=showdown_dir,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    persist, reset = json.loads(result.stdout)
    for phase, hits, power in (("initial", 0, 50), ("oneHit", 1, 100), ("beforeSwitch", 2, 150)):
        assert persist[phase] == reset[phase]
        assert persist[phase]["hits"] == hits
        assert persist[phase]["power"] == power
        assert persist[phase]["mod"] == "gen9"
    assert persist["preSwitchLog"] == reset["preSwitchLog"]
    assert persist["benchedHits"] == 2
    assert reset["benchedHits"] == 0
    assert persist["afterSwitch"]["hits"] == 2
    assert reset["afterSwitch"]["hits"] == 0
    assert persist["afterSwitch"]["power"] == 150
    assert reset["afterSwitch"]["power"] == 50
    assert persist["afterSwitch"]["pokemon"] == reset["afterSwitch"]["pokemon"]
    assert persist["damageAfterSwitch"] > reset["damageAfterSwitch"] > 0
    assert persist["afterNewHit"]["hits"] == 3
    assert reset["afterNewHit"]["hits"] == 1
    assert persist["afterNewHit"]["power"] == 200
    assert reset["afterNewHit"]["power"] == 100
    for pokemon in persist["initial"]["pokemon"]:
        for move in pokemon["moves"]:
            if move["id"] == "protect":
                assert move["pp"] == move["maxpp"] == 16


@pytest.mark.skipif(_showdown_dir() is None, reason="Showdown not found in default paths")
@pytest.mark.parametrize("format_id", FORMATS)
def test_rage_fist_formats_work_through_battle_stream(format_id: str) -> None:
    team = (
        "Annihilape|||VitalSpirit|RageFist,Protect|Serious||||||"
        "]Magikarp|||SwiftSwim|Splash,Protect|Serious||||||"
        "]Pikachu|||Static|Splash,Protect|Serious||||||"
    )
    with ShowdownProcess() as showdown:
        session = BattleSession(showdown)
        session.start(format_id, "Alice", team, "Bob", team, seed=(101, 102, 103, 104))
        session.step("default", "default")
        session.step("switch 3, move 1", "move 2, move 1")
        session.step("switch 3, move 1", "move 2, move 1")
        assert session.turn == 3
        assert session.p1_request is not None
        moves = session.p1_request["active"][0]["moves"]
        protect = next(move for move in moves if move["id"] == "protect")
        assert protect["pp"] == protect["maxpp"] == 16
