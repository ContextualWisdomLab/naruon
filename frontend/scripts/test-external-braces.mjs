import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
const frontend = path.resolve(import.meta.dirname, '..');
const lock = fs.readFileSync(path.join(frontend, 'pnpm-lock.yaml'), 'utf8');
const unwanted = ['braces', 'micromatch', 'fast-glob', 'fill-range', 'to-regex-range'];
for (const name of unwanted) {
  assert.equal(new RegExp('^\\s+' + name + (name === 'fast-glob' ? '@' : '(?:@|:)'), 'm').test(lock), false, `external ${name} remains in lock`);
  const installed = fs.readdirSync(path.join(frontend, 'node_modules/.pnpm')).filter(entry => entry.startsWith(name + '@'));
  assert.deepEqual(installed, [], `external ${name} remains installed`);
}
console.log('PASS: all external chain lock records and installed package slots absent');
