const $ = id => document.getElementById(id);
let setup = false, current = null, polling = false;
const states = {
  available: ['Disponível', 'O PC está livre. Inicie sua sessão para preparar um ambiente exclusivo.'],
  preparing: ['Preparando', 'O HOST está criando seu ambiente temporário e verificando o Sunshine.'],
  ready: ['Pronto para conectar', 'Sunshine confirmou disponibilidade. Conecte pelo Moonlight para começar.'],
  streaming: ['Transmitindo', 'O HOST confirmou uma conexão no Sunshine. Aproveite sua sessão.'],
  reconnecting: ['Aguardando reconexão', 'A transmissão foi desconectada. Retorne pelo Moonlight em até 2 minutos.'],
  cleaning: ['Limpando ambiente', 'O HOST está encerrando a VM e verificando o descarte dos dados locais.'],
  blocked: ['Bloqueado', 'O administrador precisa verificar a configuração ou recuperar o ambiente.'],
  offline: ['Sem comunicação', 'Não foi possível consultar o HOST. O estado atual da sessão é desconhecido.']
};
function notify(message) { $('message').textContent = message; $('message').hidden = false; }
async function api(path, body) {
  const response = await fetch(`/api/${path}`, { method: body === undefined ? 'GET' : 'POST', headers: body === undefined ? {} : { 'Content-Type': 'application/json' }, body: body === undefined ? undefined : JSON.stringify(body), signal: AbortSignal.timeout(body === undefined ? 6000 : 190000) });
  const value = await response.json();
  if (!response.ok) { const error = new Error(value.error); error.status = response.status; throw error; }
  return value;
}
function render(state) {
  current = state;
  $('auth').hidden = true; $('dashboard').hidden = false; $('logout').hidden = false;
  $('welcome').textContent = `Olá, ${state.user.name}.`;
  const label = states[state.state] ?? states.offline;
  $('state').textContent = !state.own && ['preparing','ready','streaming','reconnecting'].includes(state.state) ? 'Ocupado' : label[0];
  $('stateDescription').textContent = state.error || (!state.own && ['preparing','ready','streaming','reconnecting'].includes(state.state) ? 'Outro jogador está usando o PC. Aguarde a liberação do HOST.' : label[1]);
  $('start').hidden = state.own; $('start').disabled = state.state !== 'available';
  $('stop').hidden = !state.own; $('stop').disabled = ['preparing','cleaning','offline'].includes(state.state);
  $('connection').hidden = !state.own || !['ready','streaming','reconnecting'].includes(state.state);
  $('streamAddress').textContent = state.streamHost || 'Endereço não configurado pelo administrador';
  $('pairForm').hidden = state.paired; $('paired').hidden = !state.paired;
  $('admin').hidden = state.user.role !== 'admin';
  $('recover').disabled = state.state !== 'blocked';
  $('checked').textContent = state.state === 'offline' ? 'Sem confirmação recente do HOST.' : `Confirmado pelo HOST às ${new Date().toLocaleTimeString('pt-BR')}`;
}
async function poll() {
  if (polling) return;
  polling = true;
  try { render(await api('status')); }
  catch (e) {
    if (e.status === 401) { current = null; $('auth').hidden = false; $('dashboard').hidden = true; $('logout').hidden = true; }
    else if (current) render({ ...current, state: 'offline' });
  } finally { polling = false; }
}
async function act(button, action) {
  button.disabled = true; $('message').hidden = true;
  try { await action(); } catch (e) { notify(e.message); } finally { button.disabled = false; await poll(); }
}
$('loginForm').addEventListener('submit', event => {
  event.preventDefault(); const fields = Object.fromEntries(new FormData(event.target));
  act($('loginButton'), async () => {
    if (setup) { await api('setup', fields); setup = false; $('setupLabel').hidden = true; $('formTitle').textContent = 'Entre para jogar'; $('loginButton').textContent = 'Entrar'; }
    await api('login', fields); event.target.reset(); await poll(); if (current?.user.role === 'admin') await admin();
  });
});
$('start').onclick = () => act($('start'), () => api('session/start', {}));
$('stop').onclick = () => { if (confirm('Encerrar a sessão e descartar os dados locais? Confirme antes se seus saves foram sincronizados.')) act($('stop'), () => api('session/stop', {})); };
$('logout').onclick = () => act($('logout'), async () => { await api('logout', {}); notify('Você saiu da conta. Uma sessão em andamento continua até o encerramento ou expiração.'); });
$('copyAddress').onclick = () => act($('copyAddress'), async () => { if (!current?.streamHost) throw new Error('Endereço não configurado.'); await navigator.clipboard.writeText(current.streamHost); notify('Endereço copiado.'); });
$('pairForm').addEventListener('submit', event => { event.preventDefault(); const form = event.target; act(form.querySelector('button'), async () => { await api('session/pair', Object.fromEntries(new FormData(form))); form.reset(); }); });
$('recover').onclick = () => act($('recover'), async () => { await api('admin/recover', {}); await admin(); });
$('refreshAdmin').onclick = () => act($('refreshAdmin'), admin);
$('userForm').addEventListener('submit', event => { event.preventDefault(); const form = event.target; act(form.querySelector('button'), async () => { await api('admin/users', { ...Object.fromEntries(new FormData(form)), role: 'player' }); form.reset(); await admin(); }); });
async function admin() {
  const [diagnostics, users, logs] = await Promise.all([api('admin/diagnostics'), api('admin/users'), api('admin/logs')]);
  $('diagnostics').textContent = JSON.stringify(diagnostics, null, 2);
  $('logs').textContent = logs.map(x => `${new Date(x.time).toLocaleString('pt-BR')} · ${x.event}\n${x.detail}`).join('\n\n') || 'Nenhum registro.';
  $('users').replaceChildren();
  for (const user of users) {
    const row = document.createElement('div'); row.className = 'user-row';
    const label = document.createElement('span'); label.textContent = `${user.name} · ${user.role === 'admin' ? 'Administrador' : user.enabled ? 'Autorizado' : 'Desativado'} · ${user.peer ?? 'local'}`; row.append(label);
    if (user.role === 'player') {
      const toggle = document.createElement('button'); toggle.className = 'quiet'; toggle.textContent = user.enabled ? 'Desativar e revogar' : 'Ativar';
      toggle.onclick = () => act(toggle, async () => { await api('admin/user/update', { id: user.id, enabled: !user.enabled }); await admin(); });
      const input = document.createElement('input'); input.type = 'password'; input.placeholder = 'Nova senha (12+ caracteres)'; input.setAttribute('aria-label', `Nova senha para ${user.name}`); input.autocomplete = 'new-password';
      const reset = document.createElement('button'); reset.className = 'quiet'; reset.textContent = 'Trocar senha';
      reset.onclick = () => act(reset, async () => { if (input.value.length < 12) throw new Error('Use ao menos 12 caracteres.'); await api('admin/user/update', { id: user.id, enabled: !!user.enabled, password: input.value }); await admin(); });
      row.append(toggle, input, reset);
    }
    $('users').append(row);
  }
}
async function init() {
  try {
    setup = (await api('setup')).required;
    if (setup) { $('setupLabel').hidden = false; $('formLabel').textContent = 'PRIMEIRA CONFIGURAÇÃO'; $('formTitle').textContent = 'Configure seu HOST'; $('loginButton').textContent = 'Criar administrador'; }
    await poll(); if (current?.user.role === 'admin') await admin();
  } catch (e) { notify(e.message); }
  setInterval(poll, 2000);
}
init();
