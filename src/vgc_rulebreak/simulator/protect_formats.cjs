// Loaded before the pinned Showdown CLI. The upstream checkout stays untouched.
const path = require('node:path');

const formats = require(path.join(process.cwd(), 'dist/config/formats.js')).Formats;
const base = formats.find((format) => format.name === '[Gen 9] Doubles Custom Game');
if (!base) throw new Error('Pinned Showdown lacks the Gen 9 Doubles Custom Game format');

formats.push({ ...base, name: '[Gen 9] Rulebreak Protect 16' });
formats.push({
  ...base,
  name: '[Gen 9] Rulebreak Protect 8',
  onBegin() {
    for (const pokemon of this.getAllPokemon()) {
      for (const slots of [pokemon.moveSlots, pokemon.baseMoveSlots]) {
        for (const slot of slots) {
          if (slot.id !== 'protect') continue;
          slot.maxpp = 8;
          slot.pp = Math.min(slot.pp, 8);
        }
      }
    }
  },
});
