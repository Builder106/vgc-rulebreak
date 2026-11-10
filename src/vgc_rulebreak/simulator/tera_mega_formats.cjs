// Study T: keep every Champions rule fixed and vary only mechanic availability.
const path = require('node:path');
const formats = require(path.join(process.cwd(), 'dist/config/formats.js')).Formats;
const {BattleActions} = require(path.join(process.cwd(), 'dist/sim/battle-actions.js'));
const base = formats.find(format => format.name === '[Gen 9 Champions] Doubles Custom Game');
if (!base) throw new Error('Pinned Showdown lacks Champions Doubles Custom Game');

formats.push({
  ...base,
  name: '[Gen 9] Rulebreak Champions Tera',
  actions: {
    ...base.actions,
    canMegaEvo() { return null; },
    canTerastallize: BattleActions.prototype.canTerastallize,
  },
});
formats.push({...base, name: '[Gen 9] Rulebreak Champions Mega'});
