import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, mkdirSync, writeFileSync, symlinkSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { Store, hashPassword, verifyPassword } from '../host/store.mjs';
import { Sessions } from '../host/sessions.mjs';
import { createApp, isEntrypoint } from '../host/server.mjs';

test('HOST starts through a directory symlink like Bazzite /opt', t => {
  const root = mkdtempSync(join(tmpdir(), 'cg-entry-'));
  t.after(() => rmSync(root, { recursive: true }));
  const physical = join(root, 'physical'); mkdirSync(physical);
  const script = join(physical, 'server.mjs'); writeFileSync(script, '');
  const alias = join(root, 'opt'); symlinkSync(physical, alias, process.platform === 'win32' ? 'junction' : 'dir');
  assert.equal(isEntrypoint(pathToFileURL(script), join(alias, 'server.mjs')), true);
  const other = join(physical, 'other.mjs'); writeFileSync(other, '');
  assert.equal(isEntrypoint(pathToFileURL(script), other), false);
  assert.equal(isEntrypoint(pathToFileURL(script), undefined), false);
});

// Test-only fault injection. Production has no simulated backend or available fallback.
class FaultBackend {
  constructor() { this.operations = []; this.fail = null; this.connected = false; this.gate = null; }
  async call(op, args) {
    this.operations.push([op, args]);
    if (this.fail === op) throw new Error('Injected ' + op + ' failure');
    if (op === 'start' && this.gate) await this.gate;
    return { ok: true, clean: true, ready: true, paired: true, connected: this.connected };
  }
}
function fixture(t) {
  const store = new Store(':memory:'); t.after(() => store.close());
  const id = store.addUser('player', 'long-secret-password', 'player', '100.100.10.20');
  const user = store.user('player');
  const backend = new FaultBackend(); const sessions = new Sessions(store, backend);
  return { store, user, id, backend, sessions };
}
test('passwords are salted and checked without plaintext storage', () => {
  const a = hashPassword('long-secret-password'), b = hashPassword('long-secret-password');
  assert.notEqual(a,b); assert.ok(verifyPassword('long-secret-password',a)); assert.ok(!verifyPassword('wrong',a));
  assert.throws(() => hashPassword('short'));
});
test('new database starts blocked and recovery is required', async t => {
  const f = fixture(t); assert.equal(f.store.machine.state, 'blocked');
  await f.sessions.recover(); assert.equal(f.store.machine.state,'available');
  assert.deepEqual(f.backend.operations.map(x => x[0]), ['recover','doctor']);
});
test('failed recovery never exposes available', async t => {
  const f = fixture(t); f.backend.fail = 'recover'; await f.sessions.recover();
  assert.equal(f.store.machine.state,'blocked');
});
test('reservation is atomic across independent SQLite connections', t => {
  const dir = mkdtempSync(join(tmpdir(),'cg-test-'));
  const a = new Store(join(dir,'state.sqlite')), b = new Store(join(dir,'state.sqlite'));
  t.after(() => { a.close(); b.close(); rmSync(dir, {recursive:true}); });
  a.clear(); assert.equal(a.reserve({id:1},'one'),true); assert.equal(b.reserve({id:2},'two'),false);
  assert.equal(b.machine.session,'one');
});
test('simultaneous starts create exactly one backend session', async t => {
  const f = fixture(t); f.store.clear();
  let release; f.backend.gate = new Promise(r => { release=r; });
  const first = f.sessions.start(f.user);
  await assert.rejects(f.sessions.start({...f.user,id:2}), /operação/);
  release(); await first;
  assert.equal(f.backend.operations.filter(x => x[0] === 'start').length,1);
});
test('same user retries return same session without spawning again', async t => {
  const f = fixture(t); f.store.clear(); const a = await f.sessions.start(f.user), b = await f.sessions.start(f.user);
  assert.equal(a.session,b.session); assert.equal(f.backend.operations.filter(x => x[0] === 'start').length,1);
});
test('another user cannot end or pair the reserved session', async t => {
  const f = fixture(t); f.store.clear(); await f.sessions.start(f.user);
  await assert.rejects(f.sessions.stop({...f.user,id:999}), /outro usuário/);
  await assert.rejects(f.sessions.pair({...f.user,id:999},'1234'), /Pareamento/);
});
test('only one pairing is accepted and PIN is validated', async t => {
  const f = fixture(t); f.store.clear(); await f.sessions.start(f.user);
  await assert.rejects(f.sessions.pair(f.user,'1234; command'), /quatro/);
  await f.sessions.pair(f.user,'1234'); await assert.rejects(f.sessions.pair(f.user,'5678'),/Pareamento/);
});
test('pairing requires positive Sunshine confirmation', async t => {
  const f = fixture(t); f.store.clear(); await f.sessions.start(f.user);
  f.backend.call = async () => ({ paired: false });
  await assert.rejects(f.sessions.pair(f.user, '1234'), /não confirmou/);
  assert.equal(f.store.machine.paired, 0);
});
test('failed preparation attempts verified cleanup', async t => {
  const f = fixture(t); f.store.clear(); f.backend.fail='start';
  await assert.rejects(f.sessions.start(f.user), /preparar/);
  assert.equal(f.store.machine.state,'available'); assert.equal(f.backend.operations.at(-1)[0], 'stop');
});
test('failed cleanup retains reservation and blocks next player', async t => {
  const f = fixture(t); f.store.clear(); await f.sessions.start(f.user); const id=f.store.machine.session;
  f.backend.fail='stop'; await assert.rejects(f.sessions.stop(f.user), /limpeza/);
  assert.equal(f.store.machine.state,'blocked'); assert.equal(f.store.machine.session,id);
  await assert.rejects(f.sessions.start({...f.user,id:99}), /bloqueado/);
});
test('missing explicit cleanup confirmation keeps host blocked', async t => {
  const f = fixture(t); f.store.clear(); await f.sessions.start(f.user);
  f.backend.call = async () => ({});
  await assert.rejects(f.sessions.stop(f.user), /limpeza/);
  assert.equal(f.store.machine.state, 'blocked'); assert.ok(f.store.machine.session);
});
test('idle host becomes blocked when compatibility check fails', async t => {
  const f = fixture(t); f.store.clear(); f.backend.fail = 'doctor';
  await f.sessions.tick(); assert.equal(f.store.machine.state, 'blocked');
});
test('restart recovery discards previous reservation before release', async t => {
  const f = fixture(t); f.store.clear(); await f.sessions.start(f.user);
  const restarted = new Sessions(f.store,f.backend); await restarted.recover();
  assert.equal(f.store.machine.session,null); assert.equal(f.store.machine.state,'available');
});
test('streaming is never inferred from successful preparation', async t => {
  const f = fixture(t); f.store.clear(); await f.sessions.start(f.user);
  assert.equal(f.store.machine.state,'ready'); await f.sessions.tick(); assert.equal(f.store.machine.state,'ready');
  f.backend.connected=true; await f.sessions.tick(); assert.equal(f.store.machine.state,'streaming');
  f.backend.connected=false; await f.sessions.tick(); assert.equal(f.store.machine.state,'reconnecting');
});
test('disconnect grace expiration cleans session', async t => {
  const f=fixture(t); f.store.clear(); await f.sessions.start(f.user);
  f.store.db.prepare('UPDATE machine SET last_connected=?').run(Date.now()-121000);
  await f.sessions.tick(); assert.equal(f.store.machine.state,'available');
});
test('reservation without stream expires independently of browser heartbeat', async t => {
  const f=fixture(t); f.store.clear(); await f.sessions.start(f.user);
  f.store.db.prepare('UPDATE machine SET started=?').run(Date.now()-601000);
  await f.sessions.tick(); assert.equal(f.store.machine.state,'available');
});
test('hard duration limit applies even with active stream', async t => {
  const f=fixture(t); f.store.clear(); await f.sessions.start(f.user); f.backend.connected=true;
  f.store.db.prepare('UPDATE machine SET started=?').run(Date.now()-4*3600000-1);
  await f.sessions.tick(); assert.equal(f.store.machine.state,'available');
});
test('lost backend health triggers cleanup, not an invented state', async t => {
  const f=fixture(t); f.store.clear(); await f.sessions.start(f.user); f.backend.fail='status';
  await f.sessions.tick(); assert.equal(f.backend.operations.at(-1)[0],'stop'); assert.equal(f.store.machine.state,'available');
});
test('tokens can be revoked and disabled users cannot authenticate', t => {
  const f=fixture(t); const token=f.store.login('player','long-secret-password','test');
  assert.equal(f.store.authenticate(token).id,f.id); f.store.revoke(f.id); assert.equal(f.store.authenticate(token),undefined);
  f.store.db.prepare('UPDATE users SET enabled=0 WHERE id=?').run(f.id);
  assert.throws(()=>f.store.login('player','long-secret-password','test'), /inválidos/);
});
test('brute-force throttling persists in database', t => {
  const f=fixture(t);
  for(let i=0;i<8;i++) assert.throws(()=>f.store.login('player','wrong','test'),/inválidos/);
  assert.throws(()=>f.store.login('player','long-secret-password','test'),/tentativas/);
});
test('HTTP requires same-origin mutations, denies admin access, protects cookies', async t => {
  const f=fixture(t); const origin='https://test.example';
  const {server}=await createApp({store:f.store,backend:f.backend,origin});
  await new Promise(r=>server.listen(0,'127.0.0.1',r)); t.after(()=>{server.closeAllConnections();server.close();});
  const url=`http://127.0.0.1:${server.address().port}`;
  const call=(path,body,headers={})=>fetch(url+path,{method:body?'POST':'GET',headers:{...(body?{'Content-Type':'application/json','Origin':origin}:{}),...headers},body:body?JSON.stringify(body):undefined});
  assert.equal((await call('/api/status')).status,401);
  assert.equal((await call('/api/login',{name:'player',password:'long-secret-password'},{Origin:'https://evil.example'})).status,403);
  const response=await call('/api/login',{name:'player',password:'long-secret-password'});
  const cookie=response.headers.get('set-cookie'); assert.match(cookie,/HttpOnly/); assert.match(cookie,/Secure/); assert.match(cookie,/SameSite=Strict/);
  const headers={Cookie:cookie.split(';')[0]};
  assert.equal((await call('/api/status',undefined,headers)).status,200);
  assert.equal((await call('/api/admin/users',undefined,headers)).status,403);
  assert.equal((await call('/api/session/pair',{pin:'0000'},headers)).status,409);
  await call('/api/logout',{},headers); assert.equal((await call('/api/status',undefined,headers)).status,401);
});
test('bootstrap is one-time and requires installation secret', async t => {
  const store = new Store(':memory:'); t.after(()=>store.close());
  const origin='http://127.0.0.1:8787'; const {server}=await createApp({store,backend:new FaultBackend(),origin,setupToken:'installation-secret'});
  await new Promise(r=>server.listen(0,'127.0.0.1',r)); t.after(()=>{server.closeAllConnections();server.close();});
  const url=`http://127.0.0.1:${server.address().port}/api/setup`;
  const post=token=>fetch(url,{method:'POST',headers:{Origin:origin,'Content-Type':'application/json'},body:JSON.stringify({token,name:'admin',password:'long-admin-password'})});
  assert.equal((await post('wrong')).status,403); assert.equal((await post('installation-secret')).status,201); assert.equal((await post('installation-secret')).status,403);
});
