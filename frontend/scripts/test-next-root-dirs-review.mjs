import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { createRequire } from 'node:module';
const frontend = path.resolve(import.meta.dirname, '..');
const baseline = process.argv[2] && path.resolve(process.argv[2]);
// An optional installed original supplier enables differential diagnostics.
// CI always exercises candidate assertions without requiring the removed package.
const mode = process.argv[3] || 'all';
function supplier(dir) {
  const configRequire = createRequire(fs.realpathSync(path.join(dir, 'node_modules/eslint-config-next/package.json')));
  const pluginRequire = createRequire(configRequire.resolve('@next/eslint-plugin-next/package.json'));
  return { roots: pluginRequire('./dist/utils/get-root-dirs.js').getRootDirs, pluginRequire };
}
const candidate = supplier(frontend);
const original = baseline ? supplier(baseline) : null;
const supplierAdapters = [];
if (original) {
  const originalGlobRequire = createRequire(original.pluginRequire.resolve('fast-glob'));
  const scandirRequire = createRequire(originalGlobRequire.resolve('@nodelib/fs.walk'));
  supplierAdapters.push(
    createRequire(scandirRequire.resolve('@nodelib/fs.scandir'))('./adapters/fs.js').FILE_SYSTEM_ADAPTER,
    createRequire(originalGlobRequire.resolve('@nodelib/fs.stat'))('./adapters/fs.js').FILE_SYSTEM_ADAPTER,
    originalGlobRequire('./settings.js').DEFAULT_FILE_SYSTEM_ADAPTER,
  );
}
const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'naruon-root-review-'));
const cwd = process.cwd();
const context = rootDir => ({ cwd, settings: { next: { rootDir } } });
const roots = (s, p) => s.roots(context(p)).sort();
function parity(pattern, expected) {
  if (original) assert.deepEqual(roots(original, pattern), [...expected].sort(), `original: ${pattern}`);
  assert.deepEqual(roots(candidate, pattern), [...expected].sort(), `candidate: ${pattern}`);
}
function outcome(s, pattern) {
  try { return { matches: roots(s, pattern) }; }
  catch (error) { return { error: error.code || error.message }; }
}
function inject(method, target, code, callback) {
  const owners = [fs, ...supplierAdapters].filter(o => typeof o[method] === 'function');
  const saved = owners.map(o => o[method]);
  let hits = 0;
  try {
    owners.forEach((owner, i) => { owner[method] = function(file, ...args) {
      if (path.resolve(String(file)) === path.resolve(target)) {
        hits++;
        throw Object.assign(new Error(`fixture ${method} ${code}`), { code });
      }
      return saved[i].call(this, file, ...args);
    }; });
    callback(() => hits);
  } finally {
    owners.forEach((owner, i) => { owner[method] = saved[i]; });
    owners.forEach((owner, i) => assert.equal(owner[method], saved[i], 'filesystem seam restored'));
  }
}
try {
  for (const name of ['web', 'admin', 'web+', 'admin+', 'webweb', 'adminadmin']) fs.mkdirSync(path.join(fixture, 'apps', name), { recursive: true });
  fs.symlinkSync('web', path.join(fixture, 'apps', 'linked'), 'dir');
  fs.symlinkSync('missing', path.join(fixture, 'apps', 'dangling'), 'dir');
  fs.symlinkSync('loop', path.join(fixture, 'apps', 'loop'), 'dir');
  process.chdir(fixture);
  if (mode === 'all' || mode === 'brace') {
    parity('apps/web+', ['apps/web+']);
    parity('apps/we?+', ['apps/web+']);
    parity('apps/{web,admin}', ['apps/web', 'apps/admin']);
    const pattern = 'apps/{web,admin}+';
    if (original) assert.deepEqual(roots(original, pattern), ['apps/admin+', 'apps/web+']);
    console.log('OBSERVED bounded brace-plus', JSON.stringify({ original: original ? outcome(original, pattern) : null, candidate: outcome(candidate, pattern) }));
    assert.throws(() => roots(candidate, pattern), /Unsupported Next\.js rootDir glob/, 'brace-plus must be explicitly rejected, not interpreted as repetition');
    assert.throws(() => roots(candidate, 'apps/{web+,admin}'), /Unsupported Next\.js rootDir glob/, 'plus inside a brace list must be rejected');
    console.log('PASS brace-plus rejection and ordinary literal-plus supplier parity');
  }
  if (mode === 'all' || mode === 'fs') {
    parity('apps/link*', ['apps/linked']);
    parity('apps/dang*', []);
    assert.deepEqual(roots(candidate, 'apps/loop*'), [], 'existing ELOOP symlink no-match retained');
    const failures = [];
    for (const method of ['readdirSync', 'statSync']) {
      for (const code of ['EACCES', 'EIO', 'ENOENT']) {
        const target = method === 'readdirSync' ? 'apps' : 'apps/linked';
        const pattern = method === 'readdirSync' ? 'apps/w*' : 'apps/link*';
        inject(method, target, code, hits => {
          const before = hits();
          const old = original ? outcome(original, pattern) : null;
          if (original) assert.ok(hits() > before, 'original supplier reached injected seam');
          const middle = hits();
          const actual = outcome(candidate, pattern);
          assert.ok(hits() > middle, 'candidate supplier reached injected seam');
          console.log('OBSERVED injected filesystem', JSON.stringify({ method, code, original: old, candidate: actual }));
          const expected = code === 'ENOENT' ? { matches: [] } : { error: code };
          const oldExpected = method === 'statSync' ? { matches: [] } : expected;
          if (original) assert.deepEqual(old, oldExpected, 'original supplier contract (broken-link stat errors are swallowed upstream)');
          try { assert.deepEqual(actual, expected, 'candidate must propagate nonENOENT outside fdir catch'); }
          catch (error) { failures.push(`${method} ${code}: ${error.message}`); }
        });
        parity('apps/link*', ['apps/linked']);
        parity('apps/w*', ['apps/web', 'apps/web+', 'apps/webweb']);
      }
    }
    assert.deepEqual(failures, [], 'all injected filesystem failures propagate');
    console.log('PASS read/stat EACCES/EIO propagation, ENOENT no-match, finally restoration and symlink controls');
  }
  if (mode === 'all' || mode === 'bounds') {
    const dir32 = 'a'.repeat(32);
    fs.mkdirSync(dir32);
    const wild32 = '?'.repeat(32);
    assert.equal(wild32.length, 32);
    parity(wild32, [dir32]);
    const wild33 = '?'.repeat(33);
    fs.mkdirSync('a'.repeat(33));
    assert.equal(wild33.length, 33);
    assert.throws(() => roots(candidate, wild33), /Unsupported Next\.js rootDir glob/);
    // Dot prefixes keep actual traversal shallow; Darwin cannot create a
    // physical 1024-character path under this scratch directory.
    const p1024 = './'.repeat(508) + 'apps/web';
    const p1025 = './'.repeat(508) + 'apps/web/';
    assert.equal(p1024.length, 1024);
    assert.equal(p1025.length, 1025);
    assert.deepEqual(roots(candidate, p1024), [p1024], 'exact 1024-character static spelling accepted');
    assert.throws(() => roots(candidate, p1025), /Unsupported Next\.js rootDir glob/);
    const alternatives = Array.from({ length: 17 }, (_, i) => `root${i}`);
    for (const name of alternatives) fs.mkdirSync(name);
    parity(`{${alternatives.slice(0,16).join(',')}}`, alternatives.slice(0,16));
    const rejects = ['apps/[wa]*', 'apps/{web,admin}/{x,y}', 'apps/{web,admin', 'apps/web}', 'apps/{web,}', 'apps/{,admin}', 'apps/{web}', `{${alternatives.join(',')}}`];
    for (const pattern of rejects) {
      parity('apps/{web,admin}', ['apps/web', 'apps/admin']);
      assert.throws(() => roots(candidate, pattern), /Unsupported Next\.js rootDir glob/, pattern);
    }
    console.log('PASS independent 32/33 wildcard, exact 1024/1025 length, 16/17 brace alternatives, classes/multiple/malformed/empty negatives and valid positives');
  }
} finally {
  process.chdir(cwd);
  fs.rmSync(fixture, { recursive: true, force: true });
}
