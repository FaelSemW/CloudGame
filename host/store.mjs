import { DatabaseSync } from 'node:sqlite';
import { randomBytes, scryptSync, timingSafeEqual, createHash } from 'node:crypto';
export const digest = value => createHash('sha256').update(value).digest('hex');
export function hashPassword(password) {
  if (typeof password !== 'string' || password.length < 12 || password.length > 256) throw new Error('Use uma senha entre 12 e 256 caracteres.');
  const salt = randomBytes(16).toString('hex');
  return `${salt}:${scryptSync(password, salt, 64).toString('hex')}`;
}
const dummy = hashPassword('invalid-password-placeholder');
export function verifyPassword(password, stored = dummy) {
  if (typeof password !== 'string' || password.length > 256) return false;
  const [salt, expected] = stored.split(':');
  return timingSafeEqual(scryptSync(password, salt, 64), Buffer.from(expected, 'hex'));
}
export class Store {
  constructor(path) {
    this.db = new DatabaseSync(path);
    this.db.exec(`PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; PRAGMA foreign_keys=ON;
      CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, password TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('admin','player')), enabled INTEGER NOT NULL DEFAULT 1, peer TEXT);
      CREATE TABLE IF NOT EXISTS tokens(hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id), expires INTEGER NOT NULL);
      CREATE TABLE IF NOT EXISTS machine(id INTEGER PRIMARY KEY CHECK(id=1), state TEXT NOT NULL, session TEXT, user_id INTEGER, started INTEGER, last_connected INTEGER, paired INTEGER DEFAULT 0, error TEXT);
      INSERT OR IGNORE INTO machine(id,state) VALUES(1,'blocked');
      CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, time INTEGER NOT NULL, actor INTEGER, event TEXT NOT NULL, detail TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS attempts(key TEXT PRIMARY KEY, count INTEGER NOT NULL, until INTEGER NOT NULL);`);
  }
  get machine() { return this.db.prepare('SELECT * FROM machine WHERE id=1').get(); }
  audit(actor, event, detail = '') { this.db.prepare('INSERT INTO audit(time,actor,event,detail) VALUES(?,?,?,?)').run(Date.now(), actor ?? null, event, detail); }
  user(name) { return this.db.prepare('SELECT * FROM users WHERE name=?').get(name); }
  addUser(name, password, role, peer = null) {
    if (!/^[a-zA-Z0-9_.-]{3,40}$/.test(name) || !['admin','player'].includes(role)) throw new Error('Nome ou permissão inválida.');
    return this.db.prepare('INSERT INTO users(name,password,role,peer) VALUES(?,?,?,?)').run(name, hashPassword(password), role, peer).lastInsertRowid;
  }
  login(name, password, address) {
    const now = Date.now();
    this.db.prepare('DELETE FROM attempts WHERE until<?').run(now);
    const keys = [`ip:${address}`, `user:${name}`];
    for (const key of keys) {
      const a = this.db.prepare('SELECT * FROM attempts WHERE key=?').get(key);
      if (a?.count >= 8 && a.until > now) throw Object.assign(new Error('Muitas tentativas. Aguarde 15 minutos.'), { status: 429 });
    }
    const u = this.user(name);
    const valid = verifyPassword(password, u?.password);
    if (!valid || !u?.enabled) {
      for (const key of keys) this.db.prepare('INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE SET count=count+1').run(key, now + 900000);
      throw Object.assign(new Error('Usuário ou senha inválidos.'), { status: 401 });
    }
    for (const key of keys) this.db.prepare('DELETE FROM attempts WHERE key=?').run(key);
    const token = randomBytes(32).toString('base64url');
    this.db.prepare('DELETE FROM tokens WHERE expires<?').run(now);
    this.db.prepare('INSERT INTO tokens VALUES(?,?,?)').run(digest(token), u.id, now + 12 * 3600000);
    this.audit(u.id, 'login');
    return token;
  }
  authenticate(token) { return this.db.prepare('SELECT users.* FROM tokens JOIN users ON users.id=tokens.user_id WHERE hash=? AND expires>? AND enabled=1').get(digest(token), Date.now()); }
  revoke(id) { this.db.prepare('DELETE FROM tokens WHERE user_id=?').run(id); }
  reserve(user, id) {
    const r = this.db.prepare("UPDATE machine SET state='preparing',session=?,user_id=?,started=?,last_connected=NULL,paired=0,error=NULL WHERE id=1 AND state='available'").run(id, user.id, Date.now());
    return r.changes === 1;
  }
  state(state, error = null) { this.db.prepare('UPDATE machine SET state=?,error=? WHERE id=1').run(state, error); }
  clear() { this.db.exec("UPDATE machine SET state='available',session=NULL,user_id=NULL,started=NULL,last_connected=NULL,paired=0,error=NULL WHERE id=1"); }
  close() { this.db.close(); }
}
