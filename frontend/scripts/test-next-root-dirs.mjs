import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { createRequire } from 'node:module';
import { performance } from 'node:perf_hooks';
const require = createRequire(import.meta.url);
const frontend = path.resolve(import.meta.dirname, '..');
const baseline = process.argv[2] && path.resolve(process.argv[2]);
function loadSupplier(dir) {
  const configRequire = createRequire(fs.realpathSync(path.join(dir, 'node_modules/eslint-config-next/package.json')));
  const plugin = path.dirname(configRequire.resolve('@next/eslint-plugin-next/package.json'));
  assert.equal(require(path.join(plugin, 'package.json')).version, '16.3.6');
  return {
    roots: require(path.join(plugin, 'dist/utils/get-root-dirs.js')).getRootDirs,
    rule: require(path.join(plugin, 'dist/rules/no-html-link-for-pages.js')).default,
  };
}
const candidate = loadSupplier(frontend);
const original = baseline ? loadSupplier(baseline) : null;
const fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'naruon-next-roots-'));
const cwd = process.cwd();
try {
  for (const name of ['web', 'admin', '.hidden', '01', '02', '1', '2', '3']) {
    fs.mkdirSync(path.join(fixture, 'apps', name, 'pages'), { recursive: true });
    fs.writeFileSync(path.join(fixture, 'apps', name, 'pages', 'about.js'), 'export default function Page() {}');
  }
  fs.symlinkSync('web', path.join(fixture, 'apps', 'linked'), 'dir');
  fs.writeFileSync(path.join(fixture, 'apps', 'file.txt'), 'not a directory');
  process.chdir(fixture);
  const context = rootDir => ({ cwd: '/deliberately/different/context', settings: { next: { rootDir } } });
  const cases = [
    ['relative literal', 'apps/web', ['apps/web']],
    ['relative question wildcard', 'apps/we?', ['apps/web']],
    ['relative dot prefix', './apps/web', ['./apps/web']],
    ['directory suffix', 'apps/web/', ['apps/web/']],
    ['symlink child wildcard', 'apps/link*/pag*', ['apps/linked/pages']],
    ['absolute wildcard array', [path.join(fixture, 'apps/w*')], [path.join(fixture, 'apps/web')]],
    ['absolute symlink', path.join(fixture, 'apps/linked'), [path.join(fixture, 'apps/linked')]],
    ['relative wildcard', 'apps/*', ['apps/01', 'apps/02', 'apps/1', 'apps/2', 'apps/3', 'apps/admin', 'apps/linked', 'apps/web']],
    ['absolute literal', path.join(fixture, 'apps/web'), [path.join(fixture, 'apps/web')]],
    ['absolute wildcard', path.join(fixture, 'apps/*'), ['01', '02', '1', '2', '3', 'admin', 'linked', 'web'].map(name => path.join(fixture, 'apps', name))],
    ['mixed array', ['apps/web', path.join(fixture, 'apps/admin'), 17], ['apps/web', path.join(fixture, 'apps/admin')]],
    ['dot literal', 'apps/.hidden', ['apps/.hidden']],
    ['dot wildcard', 'apps/.*', ['apps/.hidden']],
    ['symlink literal', 'apps/linked', ['apps/linked']],
    ['symlink wildcard', 'apps/link*', ['apps/linked']],
    ['no matches', 'absent/*', []],
    ['file root excluded', 'apps/file.txt', []],
    ['brace alternatives', 'apps/{web,admin}', ['apps/web', 'apps/admin']],
    ['array duplicates preserved', ['apps/web', 'apps/web'], ['apps/web', 'apps/web']],
  ];
  for (const [label, pattern, expected] of cases) {
    const actual = candidate.roots(context(pattern)).sort();
    if (expected) assert.deepEqual(actual, [...expected].sort(), label);
    if (original) assert.deepEqual(actual, original.roots(context(pattern)).sort(), `supplier differential: ${label}`);
    console.log(`PASS roots: ${label}`);
  }
  assert.deepEqual(candidate.roots({ cwd, settings: {} }), [cwd], 'no rootDir remains context.cwd, no glob');
  if (original) assert.deepEqual(candidate.roots({ cwd, settings: {} }), original.roots({ cwd, settings: {} }));
  console.log('PASS no-rootDir context.cwd');
  const { Linter } = require('eslint');
  function diagnostics(supplier, rootDir, href) {
    const linter = new Linter();
    return linter.verify(`const link = <a href="${href}">about</a>;`, [{
      languageOptions: { ecmaVersion: 2022, sourceType: 'module', parserOptions: { ecmaFeatures: { jsx: true } } },
      settings: { next: { rootDir } },
      plugins: { next: { rules: { 'no-html-link-for-pages': supplier.rule } } },
      rules: { 'next/no-html-link-for-pages': 'error' },
    }]).map(({ruleId, message, severity}) => ({ruleId, message, severity}));
  }
  for (const pattern of ['apps/web', 'apps/w*', path.join(fixture, 'apps/web'), path.join(fixture, 'apps/w*'), ['apps/web']]) {
    for (const href of ['/about', '/unmatched', 'https://example.invalid/about']) {
      const actual = diagnostics(candidate, pattern, href);
      assert.equal(actual.length, href === '/about' ? 1 : 0, 'real Next rule diagnostic count');
      if (actual.length) assert.match(actual[0].message, /Use `<Link \/>`/);
      if (original) assert.deepEqual(actual, diagnostics(original, pattern, href), 'real Next rule supplier differential');
    }
  }
  console.log('PASS actual no-html-link-for-pages positive and negative diagnostics');
  // Safe, bounded inputs only. Never pass huge expansion input to the old oracle.
  for (const pattern of ['apps/**', 'apps/{01..02}', 'apps/{1..3..2}', 'apps/{1..3}', 'apps/{web,{admin,linked}}', 'apps/' + '*'.repeat(33), 'a'.repeat(1025), 'apps/@(web|admin)']) {
    const start = performance.now();
    assert.throws(() => candidate.roots(context(pattern)), /Unsupported Next\.js rootDir glob/, `explicit bounded rejection: ${pattern.slice(0, 60)}`);
    assert.ok(performance.now() - start < 1000, 'rejection stays bounded');
  }
  console.log('PASS unsupported range / nested brace / extglob / length / wildcard budget rejection');
} finally {
  process.chdir(cwd);
  fs.rmSync(fixture, { recursive: true, force: true });
}
