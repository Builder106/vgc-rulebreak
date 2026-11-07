// Study R changes only hit-counter persistence; all other mechanics stay Gen 9.
const path = require('node:path');

const formats = require(path.join(process.cwd(), 'dist/config/formats.js')).Formats;
const base = formats.find((format) => format.name === '[Gen 9] Doubles Custom Game');
if (!base) throw new Error('Pinned Showdown lacks the Gen 9 Doubles Custom Game format');

formats.push({ ...base, name: '[Gen 9] Rulebreak Rage Fist Persist' });
formats.push({
  ...base,
  name: '[Gen 9] Rulebreak Rage Fist Reset',
  onSwitchOut(pokemon) {
    pokemon.timesAttacked = 0;
  },
});
