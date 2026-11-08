// Compose the independently fixture-checked Study P and Study R interventions.
require('./protect_formats.cjs');
require('./rage_fist_formats.cjs');
const path = require('node:path');
const formats = require(path.join(process.cwd(), 'dist/config/formats.js')).Formats;
for (const pp of [16, 8]) {
  const protect = formats.find(format => format.name === `[Gen 9] Rulebreak Protect ${pp}`);
  for (const persistence of ['Persist', 'Reset']) {
    const rage = formats.find(format => format.name === `[Gen 9] Rulebreak Rage Fist ${persistence}`);
    formats.push({
      ...protect,
      name: `[Gen 9] Rulebreak Protect ${pp} Rage Fist ${persistence}`,
      ...(rage.onSwitchOut ? {onSwitchOut: rage.onSwitchOut} : {}),
    });
  }
}
