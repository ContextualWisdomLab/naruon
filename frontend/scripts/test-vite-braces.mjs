import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import path from 'node:path';
import vm from 'node:vm';
import { spawnSync } from 'node:child_process';
const require = createRequire(import.meta.url);
const viteRequire = createRequire(require.resolve('vitest/package.json'));
const bundle = path.join(path.dirname(viteRequire.resolve('vite')), 'chunks/node.js');
function supplier() {
  const source = readFileSync(bundle, 'utf8');
  const start = source.indexOf('//#region ../../node_modules/.pnpm/braces@3.0.3/node_modules/braces/lib/utils.js');
  const finish = source.indexOf('//#endregion', source.indexOf('var require_braces =', start)) + '//#endregion'.length;
  assert.ok(start > 0 && finish > start);
  const context = vm.createContext({ console, __require: require, __commonJSMin: (fn) => { let mod; return () => { if (!mod) { mod = { exports: {} }; fn(mod.exports, mod); } return mod.exports; }; } });
  vm.runInContext(source.slice(start, finish) + '\nthis.braces = require_braces();', context, { timeout: 1000 });
  return context.braces;
}
if (process.argv[2] === '--child') {
  const b = supplier();
  const mode = process.argv[3];
  const input = '{'.repeat(4000) + 'a' + '}'.repeat(4000);
  if (mode === 'parse-internal') b.parse('{' + input + '..z,q}');
  else if (mode === 'compile') b.compile(input);
  else if (mode === 'expand') b.expand(input);
  else if (mode === 'stringify') b.stringify(input);
  else if (mode === 'paren') b.compile('('.repeat(4000) + 'a' + ')'.repeat(4000));
  console.log('UNBOUNDED_ACCEPTANCE');
} else {
  assert.equal(viteRequire('vite/package.json').version, '8.1.4');
  let failures = 0;
  for (const mode of ['compile','expand','stringify','parse-internal','paren']) {
    const child = spawnSync(process.execPath, ['--stack-size=512','--max-old-space-size=128',import.meta.filename,'--child',mode], { timeout: 4000, maxBuffer: 32768, encoding:'utf8' });
    const guarded = child.status === 1 && /ERR_VITE_BRACES_DEPTH/.test(child.stderr) && !/Maximum call stack size exceeded/.test(child.stderr);
    console.log(JSON.stringify({ mode, status:child.status, signal:child.signal, guarded, stderr:child.stderr, stdout:child.stdout, spawnError:child.error?.message }));
    if (!guarded) failures++;
  }
  assert.equal(failures, 0, 'supplier must reject every excessive nesting input with explicit depth error');
  const b = supplier();
  assert.deepEqual(Array.from(b.expand('x/{a,b}/y')), ['x/a/y','x/b/y']);
  assert.equal(b.compile('x/{a,b}/y'),'x/(a|b)/y');
  assert.deepEqual(Array.from(b.expand('x/{01..03}/y')), ['x/01/y','x/02/y','x/03/y']);
  assert.deepEqual(Array.from(b.expand('x/{a,{b,c}}/y')), ['x/a/y','x/b/y','x/c/y']);
  assert.equal(b.stringify('x/{a,b}/y'),'x/{a,b}/y');
  const at = '{'.repeat(64)+'x'+'}'.repeat(64);
  assert.equal(b.stringify(at),at);
  assert.equal(typeof b.compile(at), 'string');
  assert.deepEqual(Array.from(b.expand(at)),[at]);
  for (const mode of ['compile','expand','stringify']) {
    let ast = { type:'root', nodes:[] };
    let cursor = ast;
    for (let i=0;i<67;i++) {
      const child = { type:'brace', open:true, close:true, commas:1, ranges:0, nodes:[], parent:cursor };
      cursor.nodes.push(child); cursor=child;
    }
    cursor.nodes.push({type:'text',value:'x'});
    assert.throws(() => b[mode](ast), /ERR_VITE_BRACES_DEPTH/);
  }
  for (const mode of ['parse','compile','expand','stringify']) {
    assert.throws(() => b[mode]('{'.repeat(65)+'x'+'}'.repeat(65), {maxDepth:Infinity, depth:Infinity, maxLength:10000, rangeLimit:false}), /ERR_VITE_BRACES_DEPTH/);
    assert.throws(() => b[mode]('('.repeat(65)+'x'+')'.repeat(65)), /ERR_VITE_BRACES_DEPTH/);
    assert.equal(typeof b[mode]('\\\\{literal\\\\}'),mode==='parse'?'object':mode==='expand'?'object':'string');
  }
  console.log('Vite mandatory depth and positive braces controls passed');
}
