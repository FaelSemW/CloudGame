#!/usr/bin/python3
"""Resumable Bazzite setup. Fixed package/service names, no remote shell scripts."""
import json
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

ROOT = Path('/var/lib/cloud-game-installer')
STATE = ROOT / 'state.json'
PACKAGES = {
    'virsh': 'libvirt-client', 'qemu-img': 'qemu-img',
    'qemu-system-x86_64': 'qemu-system-x86', 'nft': 'nftables',
    'tailscale': 'tailscale', 'ip': 'iproute', 'sudo': 'sudo',
    'restorecon': 'policycoreutils', 'semanage': 'policycoreutils-python-utils',
    'visudo': 'sudo',
    'pkexec': 'polkit',
}
REPO = """[tailscale-stable]
name=Tailscale stable
baseurl=https://pkgs.tailscale.com/stable/fedora/$basearch
enabled=1
type=rpm
repo_gpgcheck=1
gpgcheck=1
gpgkey=https://pkgs.tailscale.com/stable/fedora/repo.gpg
"""


def run(*args, capture=True, timeout=120, check=True, **kwargs):
    result = subprocess.run(args, text=True, capture_output=capture, timeout=timeout,
                            env=dict(os.environ, PATH='/usr/sbin:/usr/bin:/sbin:/bin', LANG='C.UTF-8'), **kwargs)
    if check and result.returncode:
        raise RuntimeError(f'{args[0]} falhou (código {result.returncode}). ' +
                           ((result.stderr or '')[-1500:] if capture else 'Veja a mensagem acima.'))
    return result.stdout.strip() if capture and check else result


def save(state):
    target = ROOT / 'state.new'
    with open(target, 'w', opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW, 0o600)) as stream:
        json.dump(state, stream); stream.flush(); os.fsync(stream.fileno())
    os.replace(target, STATE)
    descriptor = os.open(ROOT, os.O_DIRECTORY)
    try: os.fsync(descriptor)
    finally: os.close(descriptor)


def owned_write(path, content, mode=0o644):
    from install_host import trusted_directory
    trusted_directory(path.parent)
    if path.exists() or path.is_symlink():
        if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o022 or path.read_text() != content:
            raise RuntimeError('Configuração existente preservada: ' + str(path))
        return
    with open(path, 'x', opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW, mode)) as stream:
        stream.write(content)
    path.chmod(mode)


def ask(message):
    # curl | sh consumes stdin; prompts must use the controlling terminal.
    try:
        with open('/dev/tty', 'w') as terminal:
            terminal.write(message + '\n'); terminal.flush()
        with open('/dev/tty', 'r') as terminal:
            return terminal.readline().strip().lower()
    except OSError:
        raise RuntimeError('Abra “Cloud Game — continuar instalação” no menu para continuar interativamente.')


def missing_packages():
    missing = {package for tool, package in PACKAGES.items() if not shutil.which(tool)}
    for package in ('libvirt-daemon-kvm', 'libvirt-daemon-config-network'):
        if run('rpm', '-q', package, check=False).returncode:
            missing.add(package)
    return sorted(missing)


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


def offer_reboot():
    print('Progresso salvo. Após reiniciar, abra “Cloud Game — continuar instalação” no menu.', flush=True)
    if ask('Reiniciar agora? Digite sim; Enter deixa para depois.') in ('sim', 's'):
        run('systemctl', 'reboot', capture=False)


def dependencies(state):
    if state.get('rebootBoot') == boot_id():
        offer_reboot(); return False
    missing = missing_packages()
    if not missing:
        return True
    if not shutil.which('rpm-ostree'):
        raise RuntimeError('Esta imagem Bazzite não oferece rpm-ostree. Nenhum comando dnf/apt será aplicado ao HOST.')
    status = json.loads(run('rpm-ostree', 'status', '--json'))
    if status.get('transaction'):
        raise RuntimeError('O sistema está atualizando. Aguarde a transação e reabra o assistente.')
    deployments = status.get('deployments', [])
    if deployments and not deployments[0].get('booted'):
        print('Há uma atualização do sistema aguardando reinício. Ela será preservada.')
        state['rebootBoot'] = boot_id(); save(state); offer_reboot(); return False
    if 'tailscale' in missing:
        repos = list(Path('/etc/yum.repos.d').glob('*.repo'))
        if not any('[tailscale-stable]' in path.read_text() for path in repos):
            owned_write(Path('/etc/yum.repos.d/cloud-game-tailscale.repo'), REPO)
    state['phase'] = 'dependencies'; state['packages'] = missing; save(state)
    print('Instalando dependências nativas: ' + ', '.join(missing), flush=True)
    run('rpm-ostree', 'install', '--idempotent', '--allow-inactive', *missing, capture=False, timeout=3600)
    state['rebootBoot'] = boot_id(); state['phase'] = 'reboot'; save(state)
    offer_reboot(); return False


def services():
    def exists(unit):
        return run('systemctl', 'show', '--property=LoadState', '--value', unit) == 'loaded'
    if run('systemctl', 'is-active', '--quiet', 'libvirtd.service', check=False).returncode == 0:
        run('systemctl', 'enable', 'libvirtd.service')
    elif exists('virtqemud.socket'):
        for daemon in ('virtqemud', 'virtproxyd', 'virtnetworkd', 'virtstoraged', 'virtnodedevd', 'virtsecretd', 'virtnwfilterd'):
            if exists(daemon + '.socket'):
                run('systemctl', 'enable', '--now', daemon + '.socket')
    elif exists('libvirtd.service'):
        run('systemctl', 'enable', '--now', 'libvirtd.service')
    else:
        raise RuntimeError('Nenhum serviço libvirt nativo encontrado após instalar dependências.')
    run('virsh', '-c', 'qemu:///system', 'list', '--all')
    run('systemctl', 'enable', '--now', 'tailscaled.service')


def tailnet():
    status = json.loads(run('tailscale', 'status', '--json'))
    if status.get('BackendState') != 'Running':
        print('Autorize o HOST pelo link Tailscale mostrado abaixo. Não digite sua senha aqui.', flush=True)
        run('tailscale', 'up', '--timeout=10m', capture=False, timeout=620)
    while True:
        status = json.loads(run('tailscale', 'status', '--json'))
        dns = status.get('Self', {}).get('DNSName', '').rstrip('.')
        valid = status.get('BackendState') == 'Running' and re.fullmatch(r'[a-z0-9.-]+\.ts\.net', dns)
        if valid:
            # Probe authorization without changing Serve or exposing a listener.
            with tempfile.TemporaryDirectory(prefix='https-', dir=ROOT) as directory:
                result = run('tailscale', 'cert', '--cert-file=' + directory + '/cert.pem',
                             '--key-file=' + directory + '/key.pem', dns, check=False, timeout=90)
                if result.returncode == 0:
                    return dns
        print('Habilite MagicDNS e certificados HTTPS em https://login.tailscale.com/admin/dns', flush=True)
        print('Se houver aprovação de dispositivos, autorize este HOST no painel Tailscale.', flush=True)
        if ask('Depois de autorizar, pressione Enter para verificar novamente; q para continuar depois.') == 'q':
            raise RuntimeError('Progresso salvo. Reabra o assistente depois de autorizar a rede.')


def verify_host(dns):
    for unit in ('cloud-game.service', 'cloud-game-network.service', 'cloud-game-watchdog.timer', 'var-lib-cloudgame-volatile.mount'):
        run('systemctl', 'is-active', '--quiet', unit)
    health = json.loads(run('/usr/bin/python3', '/opt/cloud-game/deploy/vm_helper.py', input='{"op":"doctor"}'))
    if health.get('ok') is not True:
        raise RuntimeError('Diagnóstico do HOST não confirmou os recursos necessários.')
    with urllib.request.urlopen('https://' + dns + '/api/setup', timeout=30) as response:
        return json.load(response)


def proceed(state):
    if not dependencies(state): return
    state['phase'] = 'network'; save(state)
    services()
    dns = tailnet()
    receipt = Path('/etc/cloud-game/installed.json')
    if state.get('installed') is not True and state.get('phaseBeforeResume') == 'image-and-host' and receipt.is_file():
        if receipt.is_symlink() or receipt.stat().st_uid != 0 or receipt.stat().st_mode & 0o022:
            raise RuntimeError('Comprovante de instalação inseguro.')
        if json.loads(receipt.read_text()).get('installer') == 'cloud-game-v1':
            state['installed'] = True; save(state)
    if state.get('installed') is not True:
        if Path('/opt/cloud-game').exists():
            raise RuntimeError('Instalação existente/parcial preservada em /opt/cloud-game. Não será sobrescrita automaticamente.')
        state['phase'] = 'image-and-host'; save(state)
        from install_host import install
        install(state['software'])
        state['installed'] = True; save(state)
    state['phase'] = 'verification'; save(state)
    setup = verify_host(dns)
    state['phase'] = 'complete'; save(state)
    print('\nServiços e HTTPS verificados. Painel: https://' + dns, flush=True)
    if setup.get('required'):
        logs = run('journalctl', '-u', 'cloud-game', '-b', '--no-pager', '-o', 'cat', '-n', '100')
        for line in reversed(logs.splitlines()):
            if line.startswith('Código de instalação (uso único):'):
                print(line); break
        print('Abra o painel e crie sua conta administrativa. A senha é da plataforma, não da Steam.')
    print('A disponibilidade é confirmada pelo HOST no painel. Teste uma sessão real para validar este equipamento.')


def start(source=None, software=False):
    import fcntl
    if os.geteuid() != 0:
        raise RuntimeError('O assistente precisa de autorização administrativa.')
    os.umask(0o077)
    from install_host import trusted_directory
    release = Path('/etc/os-release').read_text()
    if not re.search(r'^ID=["\']?bazzite["\']?$', release, re.M):
        raise RuntimeError('Este assistente suporta Bazzite; sistema não alterado.')
    print('Cloud Game — assistente Bazzite\n' + '\n'.join(line for line in release.splitlines() if line.startswith(('PRETTY_NAME=', 'VERSION_ID='))), flush=True)
    trusted_directory(ROOT)
    with open(ROOT / 'setup.lock', 'a', opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW, 0o600)) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if STATE.exists():
            if STATE.is_symlink() or STATE.stat().st_uid != 0 or STATE.stat().st_mode & 0o022:
                raise RuntimeError('Estado do instalador inseguro.')
            state = json.loads(STATE.read_text())
            if source and software and not state['software']:
                raise RuntimeError('Retome pelo menu: o perfil salvo é diferente do solicitado.')
        else:
            if source is None: raise RuntimeError('Nenhuma instalação salva para retomar.')
            if not software:
                from hardware import dedicated_gpus
                if len(dedicated_gpus()) != 1:
                    answer = ask('Não há uma GPU única já dedicada a VFIO. Digite teste para usar CPU (desempenho limitado), ou q para sair sem instalar.')
                    if answer != 'teste':
                        raise RuntimeError('Instalação interrompida. Nenhuma GPU do proprietário foi alterada.')
                    software = True
            shutil.copytree(source, ROOT / 'source')
            state = {'version': 1, 'software': software, 'phase': 'start'}; save(state)
        state['phaseBeforeResume'] = state['phase']
        save(state)
        launcher = '/usr/bin/pkexec /usr/bin/python3 /var/lib/cloud-game-installer/source/deploy/setup_host.py --window'
        owned_write(Path('/usr/local/share/applications/cloud-game-setup.desktop'),
                    '[Desktop Entry]\nType=Application\nName=Cloud Game — continuar instalação\nExec=' + launcher + '\nTerminal=true\nCategories=System;\n')
        # Resume always uses the persisted version, including after another download.
        if source:
            fcntl.flock(lock, fcntl.LOCK_UN)
            return subprocess.call(['/usr/bin/python3', str(ROOT / 'source/deploy/setup_host.py')])
        proceed(state)
    return 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--window', action='store_true')
    args = parser.parse_args()
    code = 0
    try:
        code = start()
    except Exception as error:
        print('Cloud Game: ' + str(error), file=sys.stderr)
        print('Progresso preservado. Abra “Cloud Game — continuar instalação” no menu para tentar novamente.', file=sys.stderr)
        code = 1
    if args.window:
        try: ask('Pressione Enter para fechar esta janela.')
        except RuntimeError: pass
    sys.exit(code)
