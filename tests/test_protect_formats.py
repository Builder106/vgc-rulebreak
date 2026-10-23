"""Live fixtures for the repository-owned Protect-only format pair."""

import json
import subprocess
from pathlib import Path

import pytest

from vgc_rulebreak.agents.heuristic import HeuristicAgent
from vgc_rulebreak.evaluation import FORMAT_BY_PP
from vgc_rulebreak.manifest import load_manifest
from vgc_rulebreak.simulator import process
from vgc_rulebreak.simulator.battle import BattleSession
from vgc_rulebreak.simulator.process import ShowdownProcess


def _showdown_dir() -> Path | None:
    try:
        return ShowdownProcess._resolve_showdown_dir(None)
    except FileNotFoundError:
        return None


@pytest.mark.skipif(_showdown_dir() is None, reason="Showdown not found in default paths")
def test_protect_formats_change_only_protect_pp() -> None:
    showdown_dir = _showdown_dir()
    assert showdown_dir is not None
    overlay_path = Path(process.__file__).with_name("protect_formats.cjs")
    script = """
    const {Battle} = require('./dist/sim/battle.js');
    const {Dex} = require('./dist/sim/dex.js');
    const ids = ['gen9rulebreakprotect16', 'gen9rulebreakprotect8'];
    const formats = ids.map(id => Dex.formats.get(id));
    const observations = ids.map(id => {
      const battle = new Battle({formatid: id, seed: [101, 102, 103, 104]});
      battle.setPlayer('p1', {name: 'Alice', team: [
        {species: 'Flutter Mane', ability: 'protosynthesis', nature: 'Timid',
         evs: {spe: 252, spa: 252}, moves: ['protect', 'moonblast']},
        {species: 'Pikachu', ability: 'static', moves: ['protect', 'thunderbolt']},
      ]});
      battle.setPlayer('p2', {name: 'Bob', team: [
        {species: 'Ogerpon-Wellspring', ability: 'waterabsorb', nature: 'Jolly',
         evs: {spe: 252, atk: 252}, moves: ['protect', 'ivycudgel']},
        {species: 'Eevee', ability: 'runaway', moves: ['protect', 'bite']},
      ]});
      battle.makeChoices('default', 'default');
      return {
        mod: battle.dex.currentMod,
        speed: [battle.p1.active[0].getStat('spe'), battle.p2.active[0].getStat('spe')],
        moves: battle.getAllPokemon().map(pokemon =>
          pokemon.moveSlots.map(slot => ({id: slot.id, pp: slot.pp, maxpp: slot.maxpp}))),
        baseMoves: battle.getAllPokemon().map(pokemon =>
          pokemon.baseMoveSlots.map(slot => ({id: slot.id, pp: slot.pp, maxpp: slot.maxpp}))),
      };
    });
    console.log(JSON.stringify({
      formats: formats.map(format => ({mod: format.mod, gameType: format.gameType,
        ruleset: format.ruleset, battle: Object.keys(format.battle || {})})),
      observations,
    }));
    """
    result = subprocess.run(
        ["node", "--require", str(overlay_path), "-e", script],
        cwd=showdown_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert FORMAT_BY_PP == {16: "gen9rulebreakprotect16", 8: "gen9rulebreakprotect8"}
    assert data["formats"][0] == data["formats"][1]
    assert data["formats"][0]["mod"] == "gen9"
    high, low = data["observations"]
    assert high["mod"] == low["mod"]
    assert high["speed"] == low["speed"]
    for slot_set in ("moves", "baseMoves"):
        for high_pokemon, low_pokemon in zip(high[slot_set], low[slot_set], strict=True):
            for high_move, low_move in zip(high_pokemon, low_pokemon, strict=True):
                if high_move["id"] == "protect":
                    assert high_move["pp"] == high_move["maxpp"] == 16
                    assert low_move["pp"] == low_move["maxpp"] == 8
                else:
                    assert high_move == low_move


@pytest.mark.skipif(_showdown_dir() is None, reason="Showdown not found in default paths")
def test_protect_formats_work_through_battle_stream() -> None:
    manifest = load_manifest(Path("experiments/teams/protect-pp.json"))
    teams = list(manifest.teams.values())[:2]
    for pp, format_id in FORMAT_BY_PP.items():
        with ShowdownProcess() as showdown:
            session = BattleSession(showdown)
            session.start(format_id, "Alice", teams[0].packed, "Bob", teams[1].packed)
            assert session.p1_request is not None
            assert session.p2_request is not None
            session.step(
                HeuristicAgent("Alice").choose_action(session.p1_request),
                HeuristicAgent("Bob").choose_action(session.p2_request),
            )
            assert session.p1_request is not None
            slots = session.p1_request["active"]
            protect_moves = [
                move
                for active in slots
                if active
                for move in active["moves"]
                if move["id"] == "protect"
            ]
            assert protect_moves
            assert all(move["pp"] == move["maxpp"] == pp for move in protect_moves)
