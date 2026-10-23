import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { once } from 'node:events';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { setTimeout as delay } from 'node:timers/promises';
import { after, before, test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const require = createRequire(import.meta.url);
const root = fileURLToPath(new URL('..', import.meta.url));
const base = process.env.SHOWCASE_URL ?? 'http://127.0.0.1:4472';
const axePath = require.resolve('axe-core/axe.min.js');
const rows = JSON.parse(readFileSync(new URL('../data/battles.json', import.meta.url), 'utf8')).battles;
let preview;
let browser;

async function open(route, viewport = { width: 1440, height: 900 }) {
  const page = await browser.newPage({ viewport, reducedMotion: 'reduce' });
  await page.goto(new URL(route, base).href, { waitUntil: 'networkidle' });
  return page;
}

before(async () => {
  if (!process.env.SHOWCASE_URL) {
    preview = spawn(
      process.execPath,
      [fileURLToPath(new URL('../node_modules/astro/bin/astro.mjs', import.meta.url)), 'preview', '--host', '127.0.0.1', '--port', '4472'],
      { cwd: root, stdio: 'ignore' },
    );
    let ready = false;
    for (let attempt = 0; attempt < 100; attempt++) {
      if (preview.exitCode !== null) break;
      try {
        ready = (await fetch(base)).ok;
        if (ready) break;
      } catch {
        await delay(100);
      }
    }
    assert.equal(ready, true, 'Astro preview did not start');
  }
  browser = await chromium.launch({ headless: true });
});

after(async () => {
  await browser?.close();
  if (preview && preview.exitCode === null) {
    preview.kill('SIGTERM');
    await once(preview, 'exit');
  }
});

test('the title menu opens a recorded game with the keyboard', async () => {
  const page = await open('/');
  try {
    await page.keyboard.press('ArrowDown');
    assert.match(await page.locator('[data-menu] a[data-selected]').innerText(), /Watch a game/);
    await page.keyboard.press('Enter');
    await page.waitForURL(/\/battle\/\d+\//);
    assert.match(await page.getByRole('heading', { level: 1 }).innerText(), /Battle \d+/);
  } finally {
    await page.close();
  }
});

test('battle controls keep the turn, field, and provenance in sync', async () => {
  const page = await open('/battle/0519/');
  try {
    assert.equal(await page.locator('[data-slot="p2b"] [data-name]').innerText(), 'Flutter Mane');
    assert.equal(await page.locator('.console__title > span').first().innerText(), "Native's choices");
    await page.keyboard.press('ArrowRight');
    assert.equal(new URL(page.url()).search, '?turn=2');
    assert.equal(await page.locator('[data-turn]').first().innerText(), '2');
    await page.keyboard.press('p');
    assert.equal(await page.locator('[data-perspective-label]').innerText(), 'Baseline');
    await page.keyboard.press('i');
    assert.equal(await page.getByRole('button', { name: /Provenance/ }).getAttribute('aria-expanded'), 'true');
  } finally {
    await page.close();
  }
});

test('the battle log filters records and preserves the filter in its URL', async () => {
  const page = await open('/log/');
  try {
    await page.locator('label:has(input[name="agent"][value="native"])').click();
    const count = rows.filter((row) => row.agent === 'native').length;
    assert.equal(await page.locator('[data-count]').innerText(), `${count} games`);
    assert.equal(new URL(page.url()).search, '?agent=native');
  } finally {
    await page.close();
  }
});

test('the study and team sheet fit phone widths and the chart remains readable', async () => {
  for (const width of [320, 390]) {
    for (const route of ['/studies/p/', '/teams/test-annihilape-bulky/']) {
      const page = await open(route, { width, height: 844 });
      try {
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, `${route} overflows at ${width}px`);
        if (route === '/studies/p/') {
          assert.equal(await page.locator('[data-tip]').isVisible(), false);
          assert.equal(await page.locator('[data-chart]').evaluate((element) => element.scrollWidth > element.clientWidth), true);
        }
      } finally {
        await page.close();
      }
    }
  }
});

test('the title and battle have no automated WCAG A or AA violations', async () => {
  for (const route of ['/', '/battle/0519/']) {
    const page = await open(route, { width: 390, height: 844 });
    try {
      await page.addScriptTag({ path: axePath });
      const violations = await page.evaluate(async () => {
        const result = await window.axe.run(document, {
          runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] },
        });
        return result.violations.map((violation) => violation.id);
      });
      assert.deepEqual(violations, [], `${route}: ${violations.join(', ')}`);
    } finally {
      await page.close();
    }
  }
});
