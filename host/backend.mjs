import { spawn } from 'node:child_process';
export class Backend {
  async call(op, args = {}) {
    if (process.env.CG_LAB === '1') throw new Error('Laboratório: apenas o controle local está instalado. Streaming requer HOST Bazzite com KVM, GPU dedicada e imagem preparada.');
    if (process.platform !== 'linux') throw new Error('O HOST requer Linux/Bazzite, KVM e uma VM de jogos provisionada.');
    return new Promise((resolve, reject) => {
      const child = spawn('/usr/bin/sudo', ['-n', '/usr/bin/python3', '/opt/cloud-game/deploy/vm_helper.py'], { stdio: ['pipe', 'pipe', 'pipe'], env: { PATH: '/usr/sbin:/usr/bin:/sbin:/bin', LANG: 'C.UTF-8' } });
      let out = '', err = '';
      const timer = setTimeout(() => child.kill('SIGKILL'), 180000);
      child.stdout.on('data', b => { out += b; if (out.length > 1024 * 1024) child.kill(); });
      child.stderr.on('data', b => { err = (err + b).slice(-4000); });
      child.on('error', e => { clearTimeout(timer); reject(e); });
      child.on('close', code => {
        clearTimeout(timer);
        if (code !== 0) return reject(new Error(err.trim() || 'Falha no controlador da VM.'));
        try { resolve(JSON.parse(out)); } catch { reject(new Error('Resposta inválida do controlador da VM.')); }
      });
      child.stdin.on('error', () => {});
      child.stdin.end(JSON.stringify({ op, ...args }));
    });
  }
}
