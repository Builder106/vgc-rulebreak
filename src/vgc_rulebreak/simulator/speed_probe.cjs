// One-turn, complete-information fixtures; private state is never sent to an agent.
require('./speed_formats.cjs');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {Battle} = require(path.join(process.cwd(), 'dist/sim/battle.js'));
const {Dex} = require(path.join(process.cwd(), 'dist/sim/dex.js'));
const {TeamValidator} = require(path.join(process.cwd(), 'dist/sim/team-validator.js'));
const config = JSON.parse(fs.readFileSync(0, 'utf8'));

// Custom Game alone skips legality. Validate a separate copy with Obtainable,
// including each system's actual IV, per-stat and total investment restrictions.
for (const scenario of config.scenarios) {
  for (const system of ['ev', 'sp']) {
    const base = system === 'ev' ? 'gen9doublescustomgame' : 'gen9championsdoublescustomgame';
    // Trusted parsing fails loudly for invalid custom rules instead of silently
    // falling back to unrestricted Custom Game. Obtainable supplies EV Limit=Auto.
    const validator = new TeamValidator(Dex.formats.get(`${base}@@@Obtainable,Species Clause`, true));
    assert.equal(validator.ruleTable.evLimit, system === 'ev' ? 510 : 66);
    assert.equal(validator.ruleTable.isBanned('nonexistent'), true);
    for (const team of Object.values(scenario.teams[system])) {
      const errors = validator.validateTeam(structuredClone(team));
      if (errors) throw new Error(`${scenario.name}/${system}: ${errors.join('; ')}`);
    }
  }
}

function settings(id) {
  const {id: _, name, fullname, section, column, battle, ...rest} = Dex.formats.get(id);
  return rest;
}
assert.deepEqual(settings('gen9rulebreakspeedev'), settings('gen9rulebreakspeedsp'));
assert.equal(Dex.formats.get('gen9rulebreakspeedsp').battle.statModify,
  Dex.mod('champions').data.Scripts.statModify);

function run(scenario, context, seed, seat, system, action) {
  const b = new Battle({formatid: `gen9rulebreakspeed${system}`, seed});
  const opponent = seat === 'p1' ? 'p2' : 'p1';
  const teams = scenario.teams[system];
  b.setPlayer(seat, {name: 'Candidate', team: structuredClone(teams.candidate)});
  b.setPlayer(opponent, {name: 'Opponent', team: structuredClone(teams.opponent)});
  b.makeChoices('default', 'default');
  const side = b[seat];
  const foe = b[opponent];
  const outgoing = side.active[0];
  const incoming = side.pokemon[2];
  const attacker = foe.active[0];
  if (context === 'trick_room') b.field.addPseudoWeather('trickroom', outgoing);
  if (context === 'tailwind') side.addSideCondition('tailwind', outgoing);
  const initial = b.getAllPokemon().map(p => ({
    ident: p.fullname, species: p.species.id, stats: {...p.storedStats},
    maxhp: p.maxhp, speed: p.getStat('spe'), moves: structuredClone(p.moveSlots),
  }));
  const requests = {candidate: structuredClone(side.activeRequest),
    opponent: structuredClone(foe.activeRequest)};
  const candidateChoice = action === 'pivot' ? 'move 1 1, move 1' : 'switch 3, move 1';
  const opponentChoice = context === 'opponent_protect' ? 'move 2, move 1' : 'move 1 1, move 1';
  const start = b.log.length;
  assert.equal(b.choose(seat, candidateChoice), true);
  assert.equal(b.choose(opponent, opponentChoice), true);
  if (side.requestState === 'switch') {
    assert.equal(action, 'pivot');
    assert.equal(b.choose(seat, 'switch 3'), true);
  }
  assert.equal(b.turn, 2, 'fixture did not finish exactly one turn');
  const events = b.log.slice(start);
  const pivotIndex = events.findIndex(line => line.startsWith(`|move|${seat}a:`));
  const foeIndex = events.findIndex(line => line.startsWith(`|move|${opponent}a:`));
  const incomingDamage = incoming.maxhp - incoming.hp;
  const outgoingDamage = outgoing.maxhp - outgoing.hp;
  const result = {
    scenario: scenario.name, equivalence: scenario.equivalence,
    context, seed, seat, system, action,
    candidate_choice: candidateChoice, opponent_choice: opponentChoice,
    candidate_speed: initial.find(p => p.ident === outgoing.fullname).speed,
    opponent_speed: initial.find(p => p.ident === attacker.fullname).speed,
    pivot_before_opponent: action === 'pivot' ? pivotIndex < foeIndex : null,
    pivot_completed: action === 'pivot' ? side.active[0] === incoming : null,
    incoming_damage: incomingDamage, outgoing_damage: outgoingDamage,
    incoming_damage_fraction: incomingDamage / incoming.maxhp,
    team_damage_fraction: incomingDamage / incoming.maxhp + outgoingDamage / outgoing.maxhp,
    initial, requests, log: b.log,
  };
  b.destroy();
  return result;
}

const rows = [];
for (const scenario of config.scenarios) {
  for (const context of config.contexts) {
    for (const seed of config.seeds) {
      for (const seat of ['p1', 'p2']) {
        for (const system of ['ev', 'sp']) {
          for (const action of ['pivot', 'switch']) {
            rows.push(run(scenario, context, seed, seat, system, action));
          }
        }
      }
    }
  }
}
console.log(JSON.stringify(rows));
