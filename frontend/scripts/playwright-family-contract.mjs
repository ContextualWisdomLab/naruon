// Run from frontend: node --test scripts/playwright-family-contract.mjs
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { createHash } from 'node:crypto';
import vm from 'node:vm';
import os from 'node:os';
import { setTimeout as delay } from 'node:timers/promises';
const require = createRequire(import.meta.url);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const testPackage = require.resolve('@playwright/test/package.json');
const testRequire = createRequire(testPackage);
const playwrightPackage = testRequire.resolve('playwright/package.json');
const playwrightRequire = createRequire(playwrightPackage);
const corePackage = playwrightRequire.resolve('playwright-core/package.json');
const family = [testPackage, playwrightPackage, corePackage];
test('top-level exact pin and installed test/runner/core versions align at 1.63.0', () => {
  const manifest = JSON.parse(fs.readFileSync(path.join(__dirname, '../package.json'), 'utf8'));
  const versions = family.map(filename => JSON.parse(fs.readFileSync(filename, 'utf8')).version);
  console.log(JSON.stringify({ versions, family }));
  assert.equal(manifest.devDependencies['@playwright/test'], '1.63.0');
  assert.deepEqual(versions, ['1.63.0', '1.63.0', '1.63.0']);
});

// Internal installed runner seam: FSWatcher is not a public Playwright API.
// Evaluate its complete unmodified installed class, with the real exported
// bundled chokidar interface. This is not CLI UI-mode/watch-mode acceptance.
test('installed runner watcher emits add/change/unlink for literal braces and honors ignore/close', { timeout: 15000 }, async () => {
  const runnerPath = path.join(path.dirname(playwrightPackage), 'lib/runner/index.js');
  const source = fs.readFileSync(runnerPath, 'utf8');
  const begin = source.indexOf('var FSWatcher = class {');
  const end = source.indexOf('\n};', begin) + 3;
  assert.ok(begin >= 0 && end > begin, 'locate the actual installed watcher class');
  const classSource = source.slice(begin, end);
  console.log(JSON.stringify({ seam: 'internal installed FSWatcher', runnerPath,
    classSha256: createHash('sha256').update(classSource).digest('hex') }));
  const { chokidar } = playwrightRequire('playwright-core/lib/utilsBundle');
  const FSWatcher = vm.runInNewContext(`${classSource}\nFSWatcher`, { chokidar, clearTimeout, setTimeout });
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'playwright-watcher-'));
  const watched = path.join(temporary, 'literal{a,b}');
  const ignored = path.join(watched, 'ignored{c,d}');
  fs.mkdirSync(ignored, { recursive: true });
  fs.mkdirSync(path.join(watched, 'node_modules'));
  fs.mkdirSync(path.join(temporary, 'literala'));
  const initial = path.join(watched, 'initial.txt');
  fs.writeFileSync(initial, 'initial');
  // macOS FSEvents may deliver a queued pre-watch write as change, not add.
  // Let fixture setup settle before opening the watcher; keep ignoreInitial strict.
  await delay(1000);
  const events = [];
  const watcher = new FSWatcher(batch => events.push(...batch));
  async function waitFor(event, file) {
    const deadline = Date.now() + 5000;
    while (!events.some(item => item.event === event && item.file === file) && Date.now() < deadline) await delay(25);
    assert.ok(events.some(item => item.event === event && item.file === file), `missing ${event}: ${file}; events=${JSON.stringify(events)}`);
  }
  try {
    await watcher.update([watched], [ignored], false);
    await delay(350);
    assert.equal(events.length, 0, `ignoreInitial: ${JSON.stringify(events)}`);
    const literal = path.join(watched, 'file{x,y}.txt');
    fs.writeFileSync(literal, 'added');
    await waitFor('add', literal);
    fs.appendFileSync(literal, ' changed');
    await waitFor('change', literal);
    fs.unlinkSync(literal);
    await waitFor('unlink', literal);
    const ignoredFile = path.join(ignored, 'hidden.txt');
    const moduleFile = path.join(watched, 'node_modules', 'hidden.txt');
    const expandedFile = path.join(temporary, 'literala', 'not-watched.txt');
    for (const file of [ignoredFile, moduleFile, expandedFile]) fs.writeFileSync(file, 'negative control');
    const adjacent = path.join(watched, 'ignored{c,d}-adjacent');
    fs.mkdirSync(adjacent);
    const allowed = path.join(adjacent, 'allowed.txt');
    fs.writeFileSync(allowed, 'prefix sibling must not be ignored');
    await waitFor('add', allowed);
    await delay(500);
    for (const file of [initial, ignoredFile, moduleFile, expandedFile]) assert.ok(!events.some(item => item.file === file), `unexpected event: ${file}`);
    await watcher.close();
    await delay(350);
    const count = events.length;
    fs.writeFileSync(path.join(watched, 'after-close.txt'), 'closed');
    await delay(500);
    assert.equal(events.length, count, 'no events after close');
    console.log(JSON.stringify({ events, controls: ['ignoreInitial', 'literal braces', 'add', 'change', 'unlink', 'ignored subtree', 'node_modules', 'no glob expansion', 'prefix sibling', 'close'] }));
  } finally {
    await watcher.close();
    fs.rmSync(temporary, { recursive: true, force: true });
  }
});
function scripts(directory) {
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const filename = path.join(directory, entry.name);
    return entry.isDirectory() ? scripts(filename) : /\.(?:js|cjs|mjs)$/.test(filename) ? [filename] : [];
  });
}
test('installed Playwright family has no bundled braces implementation or old glob watcher consumer', () => {
  const findings = [];
  let inspected = 0;
  for (const packageFile of family) {
    for (const filename of scripts(path.dirname(packageFile))) {
      inspected++;
      const source = fs.readFileSync(filename, 'utf8');
      for (const marker of ['require_braces', 'node_modules/braces/', 'getDirParts']) {
        if (source.includes(marker)) findings.push({ filename, marker });
      }
    }
  }
  console.log(JSON.stringify({ inspected, findings }));
  assert.ok(inspected > 0, 'must inspect installed artifacts, not just the lockfile');
  assert.deepEqual(findings, [], 'remove both the embedded implementation and consuming glob watcher');
});
