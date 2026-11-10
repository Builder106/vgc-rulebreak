"""Live invariants for Study T's fixed-background mechanic intervention."""

import json
import subprocess
from pathlib import Path

import pytest

from vgc_rulebreak import tera_mega as tm
from vgc_rulebreak.manifest import load_manifest
from vgc_rulebreak.simulator.process import ShowdownProcess


def test_controlled_formats_preserve_unrelated_rules_and_no_activation_traces() -> None:
    try:
        sd = ShowdownProcess._resolve_showdown_dir(None)
    except FileNotFoundError:
        pytest.skip("Showdown not available")
    manifest = load_manifest(tm.MANIFEST_PATH)
    inputs = {domain: tm.domain_teams(manifest, domain) for domain in tm.CONTROLLED_FORMATS}
    script = """
    const assert = require('node:assert/strict');
    const fs = require('node:fs');
    const {Battle} = require('./dist/sim/battle.js');
    const {Dex} = require('./dist/sim/dex.js');
    const inputs = JSON.parse(fs.readFileSync(0, 'utf8'));
    const ids = ['gen9rulebreakchampionstera', 'gen9rulebreakchampionsmega'];
    const formats = ids.map(id => Dex.formats.get(id));
    // Every format setting other than identity and the two eligibility functions matches.
    const settings = format => Object.fromEntries(Object.entries(format).filter(
      ([key]) => !['name', 'id', 'fullname', 'actions'].includes(key)));
    assert.deepEqual(settings(formats[0]), settings(formats[1]));
    const rows = Object.keys(inputs.tera).map(team => {
      const battles = ids.map((formatid, i) => {
        const battle = new Battle({formatid, seed: [101, 202, 303, 404]});
        const packed = inputs[i ? 'mega' : 'tera'][team];
        battle.setPlayer('p1', {name: 'Candidate', team: packed});
        battle.setPlayer('p2', {name: 'Opponent', team: packed});
        battle.makeChoices('default', 'default'); // team preview
        return battle;
      });
      const [tera, mega] = battles;
      assert.equal(tera.dex, mega.dex);
      assert.equal(tera.dex.currentMod, 'champions');
      assert.deepEqual([...tera.ruleTable], [...mega.ruleTable]);
      assert.equal(tera.statModify, mega.statModify);
      assert.equal(tera.calculatePP, mega.calculatePP);
      const actionKeys = new Set([
        ...Object.getOwnPropertyNames(Object.getPrototypeOf(tera.actions)),
        ...Object.keys(tera.actions), ...Object.keys(mega.actions),
      ]);
      for (const key of actionKeys) {
        if (['canMegaEvo', 'canTerastallize'].includes(key)) continue;
        if (typeof tera.actions[key] === 'function') {
          assert.equal(tera.actions[key], mega.actions[key], key);
        }
      }
      const snapshot = battle => battle.getAllPokemon().map(p => ({
        species: p.species.name, types: p.getTypes(), ability: p.ability,
        hp: p.hp, maxhp: p.maxhp, stats: p.storedStats,
        moves: p.moveSlots, baseMoves: p.baseMoveSlots,
      }));
      assert.deepEqual(snapshot(tera), snapshot(mega));
      for (const battle of battles) {
        for (const p of battle.getAllPokemon()) {
          assert.equal(p.moveSlots.find(m => m.id === 'protect').maxpp, 8);
          p.timesAttacked = 3;
          p.clearVolatile();
          assert.equal(p.timesAttacked, 0); // retain Champions Rage Fist reset
        }
        battle.makeChoices('default', 'default');
        battle.makeChoices('default', 'default');
        assert(!battle.log.some(l => /\\|-(mega|terastallize)\\|/.test(l)));
        assert(!battle.log.some(l => l.includes('|error|')));
      }
      assert.deepEqual(snapshot(tera), snapshot(mega));
      const trace = battle => battle.log.filter(l => !l.startsWith('|tier|'));
      assert.deepEqual(trace(tera), trace(mega));
      // Native Mega data/execution stays identical to the full Champions reference.
      const native = new Battle({formatid: 'gen9championsdoublescustomgame'});
      assert.equal(mega.dex, native.dex);
      assert.equal(mega.actions.canMegaEvo, native.actions.canMegaEvo);
      assert.equal(mega.actions.runMegaEvo, native.actions.runMegaEvo);
      return team;
    });
    console.log(JSON.stringify(rows));
    """
    result = subprocess.run(
        [
            "node",
            "--require",
            str(Path(tm.__file__).with_name("simulator") / "tera_mega_formats.cjs"),
            "-e",
            script,
        ],
        cwd=sd,
        input=json.dumps(inputs),
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert set(json.loads(result.stdout)) == set(manifest.teams)


def test_unknown_rules_mode_fails_before_outputs(tmp_path: Path) -> None:
    output = tmp_path / "run"
    with pytest.raises(ValueError, match="rules mode"):
        tm.run_tera_mega(output, rules_mode="unknown")
    assert not output.exists()
