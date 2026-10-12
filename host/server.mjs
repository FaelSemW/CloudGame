import http from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { randomBytes } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { Store, digest, hashPassword } from './store.mjs';
import { Backend } from './backend.mjs';
import { Sessions } from './sessions.mjs';

export async function createApp({ store, backend, origin = 'http://127.0.0.1:8787', streamHost = '', setupToken = randomBytes(24).toString('base64url') }) {
  const sessions = new Sessions(store, backend);
  const secure = new URL(origin).protocol === 'https:';
  const fail = (status, message) => { throw Object.assign(new Error(message), { status }); };
  const assets = new Map([['/', ['index.html','text/html']], ['/app.js',['app.js','text/javascript']], ['/style.css',['style.css','text/css']], ['/manifest.webmanifest',['manifest.webmanifest','application/manifest+json']], ['/icon.svg',['icon.svg','image/svg+xml']]]);
  const cookie = (token, age = 43200) => `cg=${token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=${age}${secure ? '; Secure' : ''}`;
  const server = http.createServer(async (req, res) => {
    res.setHeader('Cache-Control', 'no-store');
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'no-referrer');
    res.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'");
    if (secure) res.setHeader('Strict-Transport-Security', 'max-age=31536000');
    const send = (status, value) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(value)); };
    try {
      if (!['GET','POST'].includes(req.method)) fail(405, 'Método não permitido.');
      const url = new URL(req.url, origin);
      if (req.method === 'GET' && assets.has(url.pathname)) {
        const [file, type] = assets.get(url.pathname);
        res.writeHead(200, { 'Content-Type': `${type}; charset=utf-8` });
        return res.end(await readFile(new URL(`../client/${file}`, import.meta.url)));
      }
      let body = {};
      if (req.method === 'POST') {
        if (req.headers.origin !== origin || req.headers['content-type'] !== 'application/json') fail(403, 'Origem ou formato de solicitação inválido.');
        let data = '';
        for await (const chunk of req) { data += chunk; if (data.length > 8192) fail(413, 'Solicitação muito grande.'); }
        try { body = JSON.parse(data); } catch { fail(400, 'JSON inválido.'); }
        if (!body || typeof body !== 'object' || Array.isArray(body)) fail(400, 'Solicitação inválida.');
      }
      const hasAdmin = !!store.db.prepare("SELECT id FROM users WHERE role='admin'").get();
      if (url.pathname === '/api/setup' && req.method === 'GET') return send(200, { required: !hasAdmin });
      if (url.pathname === '/api/setup' && req.method === 'POST') {
        if (hasAdmin || typeof body.token !== 'string' || digest(body.token) !== digest(setupToken)) fail(403, 'Código de instalação inválido ou já utilizado.');
        store.addUser(body.name, body.password, 'admin'); store.audit(null, 'setup'); return send(201, { ok: true });
      }
      if (url.pathname === '/api/login' && req.method === 'POST') {
        if (typeof body.name !== 'string' || !/^[a-zA-Z0-9_.-]{3,40}$/.test(body.name) || typeof body.password !== 'string') fail(400, 'Informe usuário e senha válidos.');
        const token = store.login(body.name, body.password, req.socket.remoteAddress);
        res.setHeader('Set-Cookie', cookie(token)); return send(200, { ok: true });
      }
      const token = /(?:^|;\s*)cg=([A-Za-z0-9_-]{43})(?:;|$)/.exec(req.headers.cookie ?? '')?.[1];
      const user = token && store.authenticate(token);
      if (!user) fail(401, 'Entre para continuar.');
      if (req.method === 'GET' && url.pathname === '/api/status') {
        const m = store.machine;
        return send(200, { notice: sessions.health.profile === 'software' ? 'Modo de teste por CPU: desempenho limitado, sem GPU dedicada.' : null, user: { name: user.name, role: user.role }, state: m.state, own: m.user_id === user.id, session: m.user_id === user.id ? m.session : null, paired: m.user_id === user.id ? !!m.paired : false, started: m.user_id === user.id ? m.started : null, streamHost: m.user_id === user.id ? streamHost : null, error: m.state === 'blocked' ? 'PC bloqueado. O administrador precisa verificar a preparação ou a limpeza.' : m.error ? 'A preparação anterior falhou. O ambiente foi descartado. Consulte o administrador antes de tentar novamente.' : null });
      }
      if (req.method === 'POST' && url.pathname === '/api/logout') { store.db.prepare('DELETE FROM tokens WHERE hash=?').run(digest(token)); res.setHeader('Set-Cookie', cookie('', 0)); return send(200, { ok: true }); }
      if (req.method === 'POST' && url.pathname === '/api/session/start') {
        if (sessions.busy) fail(409, 'Uma operação já está em andamento.');
        const m = store.machine;
        if (m.state !== 'available' && !(m.user_id === user.id && ['ready','streaming','reconnecting'].includes(m.state))) fail(409, 'PC indisponível.');
        if (!user.peer) fail(403, 'Peça ao administrador para autorizar o IP Tailscale do dispositivo.');
        sessions.start(user).catch(() => {}); return send(202, { accepted: true });
      }
      if (req.method === 'POST' && url.pathname === '/api/session/stop') { await sessions.stop(user); return send(200, { ok: true }); }
      if (req.method === 'POST' && url.pathname === '/api/session/pair') { await sessions.pair(user, body.pin); return send(200, { ok: true }); }
      if (!url.pathname.startsWith('/api/admin/')) fail(404, 'Recurso não encontrado.');
      if (user.role !== 'admin') fail(403, 'Acesso administrativo necessário.');
      if (req.method === 'GET' && url.pathname === '/api/admin/diagnostics') return send(200, { health: sessions.health, machine: store.machine });
      if (req.method === 'GET' && url.pathname === '/api/admin/users') return send(200, store.db.prepare('SELECT id,name,role,enabled,peer FROM users ORDER BY name').all());
      if (req.method === 'GET' && url.pathname === '/api/admin/logs') return send(200, store.db.prepare('SELECT time,actor,event,detail FROM audit ORDER BY id DESC LIMIT 100').all());
      if (req.method === 'POST' && url.pathname === '/api/admin/recover') { if (store.machine.state !== 'blocked') fail(409, 'Recuperação permitida somente com PC bloqueado.'); await sessions.recover(user.id); return send(200, { state: store.machine.state }); }
      if (req.method === 'POST' && url.pathname === '/api/admin/users') {
        if (typeof body.peer !== 'string' || !/^100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.(?:\d{1,3})\.(?:\d{1,3})$/.test(body.peer) || body.peer.split('.').some(x => +x > 255)) fail(400, 'Informe um IPv4 válido da rede Tailscale 100.64.0.0/10.');
        if (body.role !== 'player') fail(400, 'Novas contas são de jogador.');
        const id = store.addUser(body.name, body.password, 'player', body.peer); store.audit(user.id, 'user_created', String(id)); return send(201, { id });
      }
      if (req.method === 'POST' && url.pathname === '/api/admin/user/update') {
        if (!Number.isSafeInteger(body.id) || body.id === user.id) fail(400, 'Selecione outra conta.');
        const target = store.db.prepare("SELECT * FROM users WHERE id=? AND role='player'").get(body.id);
        if (!target || typeof body.enabled !== 'boolean') fail(400, 'Conta inválida.');
        const password = body.password ? hashPassword(body.password) : null;
        if (store.machine.user_id === target.id) await sessions.stop(user);
        store.db.prepare('UPDATE users SET enabled=?,password=COALESCE(?,password) WHERE id=?').run(+body.enabled, password, target.id);
        store.revoke(target.id); store.audit(user.id, 'user_updated', String(target.id)); return send(200, { ok: true });
      }
      fail(404, 'Recurso não encontrado.');
    } catch (e) { if (!res.headersSent) send(e.status ?? 400, { error: e.status ? e.message : 'Operação recusada. Verifique os campos e se o usuário já existe.' }); else res.end(); }
  });
  server.requestTimeout = 200000; server.headersTimeout = 10000;
  return { server, sessions, setupToken };
}
if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  process.umask(0o077);
  const data = process.env.CG_DATA ?? './data'; await mkdir(data, { recursive: true, mode: 0o700 });
  const store = new Store(`${data}/host.sqlite`);
  const app = await createApp({ store, backend: new Backend(), origin: process.env.CG_ORIGIN ?? 'http://127.0.0.1:8787', streamHost: process.env.CG_STREAM_HOST ?? '' });
  if (!store.db.prepare("SELECT id FROM users WHERE role='admin'").get()) console.log(`Código de instalação (uso único): ${app.setupToken}`);
  await app.sessions.recover(null);
  app.server.listen(8787, '127.0.0.1', () => console.log('HOST: http://127.0.0.1:8787'));
  const timer = setInterval(() => app.sessions.tick().catch(() => {}), 5000);
  for (const signal of ['SIGTERM','SIGINT']) process.once(signal, async () => { clearInterval(timer); app.server.close(); /* Restart recovery and the root watchdog also enforce cleanup. */ process.exit(0); });
}
