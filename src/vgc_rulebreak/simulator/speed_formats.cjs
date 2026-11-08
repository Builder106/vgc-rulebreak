// Study S changes only stat calculation. All battle mechanics remain Gen 9.
const path = require('node:path');
const formats = require(path.join(process.cwd(), 'dist/config/formats.js')).Formats;
const {Scripts} = require(path.join(process.cwd(), 'dist/data/mods/champions/scripts.js'));
const base = formats.find(format => format.name === '[Gen 9] Doubles Custom Game');
if (!base) throw new Error('Pinned Showdown lacks Gen 9 Doubles Custom Game');
formats.push({...base, name: '[Gen 9] Rulebreak Speed EV'});
formats.push({
  ...base,
  name: '[Gen 9] Rulebreak Speed SP',
  battle: {...base.battle, statModify: Scripts.statModify},
});
