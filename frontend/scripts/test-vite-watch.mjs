import assert from 'node:assert/strict';
import fsp from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { once } from 'node:events';
import { tmpdir } from 'node:os';
const require = createRequire(import.meta.url);
const vr = createRequire(require.resolve('vitest/package.json'));
const { createServer } = await import(pathToFileURL(vr.resolve('vite')).href);
const fixture = await fsp.mkdtemp(path.join(tmpdir(), 'watch-'));
const servers = [];
async function server(root, watch, initialFile) {
  const s = await createServer({ root, configFile:false, publicDir:false, appType:'custom', optimizeDeps:{noDiscovery:true}, server:{middlewareMode:true,hmr:false,ws:false,watch} });
  servers.push(s);
  if (watch !== null && !s.watcher._readyEmitted) await once(s.watcher,'ready',{signal:AbortSignal.timeout(5000)});
  // Vite also watches missing env files; their ready calls can precede root registration.
  // An initial add is emitted only after the actual file subscription is installed.
  if (initialFile && !s.watcher._closers.has(initialFile))
    await event(s.watcher, 'add', initialFile, async () => {});
  if (initialFile) assert.ok(s.watcher._closers.has(initialFile), 'initial file subscription');
  return s;
}
async function event(w, name, target, operation) {
  console.log('watch-operation',name,target);
  const promise = new Promise((resolve,reject) => {
    const timer = setTimeout(() => { w.off(name,listener); reject(new Error('watch control deadline')); },5000);
    function listener(p) { if(path.resolve(p) !== target) return; clearTimeout(timer); w.off(name,listener); resolve(); }
    w.on(name,listener);
  });
  await operation(); await promise;
}
try {
  const literal = path.join(fixture,'literal-{a,b}');
  await fsp.mkdir(literal);
  const f = path.join(literal,'entry.txt'); await fsp.writeFile(f,'before');
  const disabled=await server(literal,null); assert.deepEqual(disabled.watcher.getWatched(),{});
  const lit=await server(literal,{disableGlobbing:true,ignoreInitial:false,usePolling:false,useFsEvents:false,atomic:false},f);
  assert.equal(lit.watcher.options.disableGlobbing,true);
  await event(lit.watcher,'change',f,()=>fsp.writeFile(f,'after'));
  await event(lit.watcher,'unlink',f,()=>fsp.unlink(f));
  await event(lit.watcher,'add',f,()=>fsp.writeFile(f,'again'));
  const globroot=path.join(fixture,'glob'); await fsp.mkdir(globroot);
  for(const d of ['a','b','c']) { await fsp.mkdir(path.join(globroot,d)); await fsp.writeFile(path.join(globroot,d,'file.txt'),'initial'); }
  const gl=await server(globroot,{disableGlobbing:false,ignoreInitial:true,usePolling:false,useFsEvents:false,atomic:false});
  const glob=path.join(globroot,'{a,b}','*.txt');
  const helper=gl.watcher._getWatchHelpers(glob,0);
  assert.equal(helper.hasGlob,true);
  assert.deepEqual(helper.dirParts,[['a'],['b']]);
  assert.equal(helper.globFilter(path.join(globroot,'a/file.txt')),true);
  assert.equal(helper.globFilter(path.join(globroot,'c/file.txt')),false);
  const globWatcher = new gl.watcher.constructor(gl.watcher.options);
  servers.push({close: () => globWatcher.close()});
  const globReady = once(globWatcher,'ready',{signal:AbortSignal.timeout(5000)});
  globWatcher.add(glob);
  await globReady;
  await event(globWatcher,'change',path.join(globroot,'a/file.txt'),()=>fsp.writeFile(path.join(globroot,'a/file.txt'),'changed'));
  const actual=path.join(fixture,'actual'); await fsp.mkdir(actual);
  const sf=path.join(actual,'symlink.txt'); await fsp.writeFile(sf,'first');
  const link=path.join(fixture,'link'); await fsp.symlink(actual,link);
  const sy=await server(link,{disableGlobbing:true,ignoreInitial:false,followSymlinks:true,usePolling:false,useFsEvents:false},path.join(link,'symlink.txt'));
  await event(sy.watcher,'change',path.join(link,'symlink.txt'),()=>fsp.writeFile(sf,'second'));
  const err=new Error('fixture non-ENOENT'); err.code='EIO';
  const observed=[]; lit.watcher.on('error',e=>observed.push(e));
  assert.equal(lit.watcher._handleError(err),err);
  assert.equal(observed.length,1); assert.equal(observed[0],err);
  const absent=new Error('fixture missing'); absent.code='ENOENT';
  lit.watcher._handleError(absent); assert.equal(observed.length,1);
  assert.throws(()=>gl.watcher._getWatchHelpers(path.join(globroot,'{'.repeat(4000)+'a'+'}'.repeat(4000),'*.txt'),0),/ERR_VITE_BRACES_DEPTH/);
  console.log(JSON.stringify({watchNull:true,literalBrace:true,change:true,unlink:true,add:true,braceGlob:true,symlink:true,nonENOENT:true,ENOENT:true,realConsumerDepthRejection:true}));
} finally {
  for(const s of servers.reverse()) await s.close();
  await fsp.rm(fixture,{recursive:true,force:true});
}
