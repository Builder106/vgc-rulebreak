// Certify source teams against a regulated format, then verify actual public OTS.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {Battle, Dex, Teams, TeamValidator, toID} = require(path.join(process.cwd(), 'dist/sim'));
const config = JSON.parse(fs.readFileSync(0, 'utf8'));
const validator = new TeamValidator(Dex.formats.get(config.legality_format, true));
assert.equal(validator.format.mod, 'championsregmb');
assert.equal(validator.ruleTable.evLimit, 66);
assert.equal(validator.ruleTable.minTeamSize, 6);
assert.equal(validator.ruleTable.pickedTeamSize, 4);
assert(validator.ruleTable.has('speciesclause'));
assert(validator.ruleTable.has('itemclause'));
assert(validator.ruleTable.isBanned('nonexistent'));

const teams = {};
for (const [id, paste] of Object.entries(config.pastes)) {
  const team = Teams.import(paste);
  assert(team && team.length === 6, `${id}: expected six source members`);
  assert(team.every(p => p.moves.length === 4 && p.level === 50), `${id}: incomplete sets`);
  const original = structuredClone(team);
  const errors = validator.validateTeam(team);
  if (errors) throw new Error(`${id}: ${errors.join('; ')}`);
  teams[id] = {
    packed: Teams.pack(team),
    private_team: team,
    normalization: original.map((p, i) => ({
      member: i + 1, source_species: p.species, battle_species: team[i].species,
    })).filter(p => p.source_species !== p.battle_species),
  };
}
assert.equal(new Set(Object.values(teams).map(t => t.packed)).size, Object.keys(teams).length);

const setups = [];
for (const matchup of config.matchups) {
  const battle = new Battle({formatid: config.ots_format, seed: matchup.seed});
  try {
    battle.setPlayer('p1', {name: matchup.p1, team: structuredClone(teams[matchup.p1].private_team)});
    battle.setPlayer('p2', {name: matchup.p2, team: structuredClone(teams[matchup.p2].private_team)});
    assert.equal(battle.p1.requestState, 'teampreview');
    assert.equal(battle.p2.requestState, 'teampreview');
    const sheets = battle.log.filter(line => line.startsWith('|showteam|'));
    assert.equal(sheets.length, 2, 'both OTS must be public before selection');
    for (const line of sheets) {
      const side = line.split('|')[2];
      const packed = line.split('|').slice(3).join('|');
      const members = packed.split(']');
      assert.equal(members.length, 6);
      for (const member of members) {
        const fields = member.split('|');
        assert.equal(fields[6], '', 'OTS must not reveal stat points');
        assert.equal(fields[8], '', 'OTS must not reveal IVs');
        assert(fields[5], 'Champions nature must be public');
      }
      const publicTeam = Teams.unpack(packed);
      const privateTeam = teams[matchup[side]].private_team;
      for (let i = 0; i < 6; i++) {
        for (const field of ['species', 'item', 'ability', 'nature', 'moves']) {
          const normalize = value => Array.isArray(value) ? value.map(toID) : toID(value);
          assert.deepEqual(normalize(publicTeam[i][field]), normalize(privateTeam[i][field]),
            `OTS ${field} mismatch`);
        }
      }
    }
    battle.makeChoices('default', 'default');
    assert.equal(battle.turn, 1);
    for (const side of battle.sides) {
      assert.equal(side.pokemon.length, 4, 'bring six, pick four');
      assert.equal(side.active.length, 2, 'doubles leads');
    }
    setups.push({...matchup, public_sheets: sheets, selected_members: 4, active_members: 2});
  } finally {
    battle.destroy();
  }
}
console.log(JSON.stringify({teams, setups}));
