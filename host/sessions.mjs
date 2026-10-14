import { randomUUID } from 'node:crypto';
export class Sessions {
  constructor(store, backend) { this.store = store; this.backend = backend; this.busy = false; this.health = { ok: false, error: 'Verificação inicial pendente.' }; }
  async exclusive(fn) {
    if (this.busy) throw Object.assign(new Error('Uma operação já está em andamento.'), { status: 409 });
    this.busy = true;
    try { return await fn(); } finally { this.busy = false; }
  }
  async recover(actor) {
    return this.exclusive(async () => {
      this.store.state('cleaning');
      try {
        const recovery = await this.backend.call('recover');
        if (recovery.clean !== true) throw new Error('O controlador não confirmou a limpeza.');
        this.health = await this.backend.call('doctor');
        if (!this.health.ok) throw new Error('Pré-requisitos incompletos. Consulte o diagnóstico.');
        this.store.clear(); this.store.audit(actor, 'recovered');
      } catch (e) { this.store.state('blocked', e.message); this.health = { ok: false, error: e.message }; this.store.audit(actor, 'recovery_failed', e.message); }
    });
  }
  async start(user) {
    return this.exclusive(async () => {
      const existing = this.store.machine;
      if (existing.user_id === user.id && ['preparing','ready','streaming','reconnecting'].includes(existing.state)) return existing;
      if (!user.peer) throw Object.assign(new Error('O administrador precisa autorizar o IP Tailscale deste dispositivo.'), { status: 403 });
      const id = randomUUID();
      if (!this.store.reserve(user, id)) throw Object.assign(new Error('O PC está ocupado ou bloqueado.'), { status: 409 });
      this.store.audit(user.id, 'reserved', id);
      try {
        await this.backend.call('start', { id, peer: user.peer });
        const result = await this.backend.call('status', { id });
        if (!result.ready) throw new Error('O Sunshine ainda não confirmou disponibilidade da sessão.');
        this.store.state('ready'); this.store.audit(user.id, 'ready', id);
      } catch (e) {
        this.store.audit(user.id, 'prepare_failed', e.message);
        await this.cleanup(user.id);
        this.store.state('available', e.message);
        throw Object.assign(new Error(`Não foi possível preparar a sessão: ${e.message}`), { status: 503 });
      }
      return this.store.machine;
    });
  }
  async cleanup(actor) {
    const m = this.store.machine;
    this.store.state('cleaning');
    try {
      const result = await this.backend.call('stop', { id: m.session });
      if (result.clean !== true) throw new Error('O controlador não confirmou o descarte.');
      this.store.clear(); this.store.audit(actor, 'cleaned', m.session ?? '');
    } catch (e) { this.store.state('blocked', e.message); this.store.audit(actor, 'cleanup_failed', e.message); throw Object.assign(new Error('A limpeza falhou. O PC continuará bloqueado.'), { status: 503 }); }
  }
  async stop(user) {
    return this.exclusive(async () => {
      const m = this.store.machine;
      if (!m.session && m.state === 'available') return;
      if (user.role !== 'admin' && m.user_id !== user.id) throw Object.assign(new Error('Esta sessão pertence a outro usuário.'), { status: 403 });
      await this.cleanup(user.id);
    });
  }
  async pair(user, pin) {
    return this.exclusive(async () => {
      const m = this.store.machine;
      if (m.user_id !== user.id || m.state !== 'ready' || m.paired) throw Object.assign(new Error('Pareamento indisponível. Apenas um dispositivo pode ser pareado por sessão.'), { status: 409 });
      if (!/^\d{4}$/.test(pin)) throw Object.assign(new Error('Informe os quatro números exibidos pelo Moonlight.'), { status: 400 });
      await this.backend.call('pair', { id: m.session, pin });
      this.store.db.exec('UPDATE machine SET paired=1 WHERE id=1');
      this.store.audit(user.id, 'paired');
    });
  }
  async tick() {
    if (this.busy) return;
    const m = this.store.machine;
    if (m.state === 'available' && Date.now() - (this.checked ?? 0) > 30000) {
      return this.exclusive(async () => {
        this.checked = Date.now();
        try { this.health = await this.backend.call('doctor'); if (!this.health.ok) throw new Error('HOST incompatível.'); }
        catch (e) { this.store.state('blocked', e.message); this.health = { ok: false, error: e.message }; }
      });
    }
    if (!['ready','streaming','reconnecting'].includes(m.state)) return;
    await this.exclusive(async () => {
      try {
        const s = await this.backend.call('status', { id: m.session });
        if (!s.ready) throw new Error('A VM ou o Sunshine parou de responder.');
        const now = Date.now();
        if (s.connected) {
          this.store.db.prepare('UPDATE machine SET last_connected=? WHERE id=1').run(now);
          this.store.state('streaming');
        } else if (m.last_connected) this.store.state('reconnecting');
        if (now - m.started > 4 * 3600000 || (!s.connected && now - (m.last_connected ?? m.started) > (m.last_connected ? 120000 : 600000))) await this.cleanup(m.user_id);
      } catch (e) {
        this.store.audit(m.user_id, 'monitor_failed', e.message);
        if (this.store.machine.state !== 'blocked') await this.cleanup(m.user_id);
      }
    });
  }
}
