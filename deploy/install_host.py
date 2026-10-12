#!/usr/bin/python3
"""Run from this checkout with pkexec; never changes the immutable /usr tree."""
import hashlib
import io
import json
import os
import pathlib
import pwd
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.request

SOURCE = pathlib.Path(__file__).resolve().parent.parent
DEST = pathlib.Path('/opt/cloud-game')


def run(*args):
    return subprocess.run(args, text=True, capture_output=True, check=True).stdout.strip()


def write(path, text, mode=0o644):
    if path.exists() or path.is_symlink():
        raise RuntimeError(f'Arquivo existente preservado: {path}. Atualize manualmente após revisar o diff.')
    path.write_text(text)
    path.chmod(mode)


def install():
    if os.geteuid() != 0 or 'bazzite' not in pathlib.Path('/etc/os-release').read_text().lower():
        raise RuntimeError('Execute no Bazzite com pkexec, após preparar virtualização pelo Bazzite Portal.')
    if DEST.exists():
        raise RuntimeError('/opt/cloud-game já existe; atualização automática não substituirá sua instalação.')
    required = ['virsh', 'qemu-img', 'nft', 'tailscale', 'ip', 'sudo', 'restorecon', 'semanage']
    missing = [x for x in required if not shutil.which(x)]
    if missing:
        raise RuntimeError('Pré-requisitos ausentes: ' + ', '.join(missing) + '. Consulte docs/BAZZITE.md; não instale pacotes com apt/dnf no HOST.')
    run('virsh', '-c', 'qemu:///system', 'list', '--all')
    info = json.loads(run('tailscale', 'status', '--json'))
    dns = info.get('Self', {}).get('DNSName', '').rstrip('.')
    addresses = info.get('Self', {}).get('TailscaleIPs', [])
    address = next((a for a in addresses if re.fullmatch(r'100\.\d+\.\d+\.\d+', a)), None)
    if not address or not re.fullmatch(r'[a-z0-9.-]+\.ts\.net', dns):
        raise RuntimeError('Conecte o HOST ao Tailscale e habilite MagicDNS/HTTPS antes de instalar.')
    try:
        pwd.getpwnam('cloud-game')
    except KeyError:
        run('useradd', '--system', '--home-dir', '/var/lib/cloudgame/control', '--shell', '/usr/sbin/nologin', 'cloud-game')
    account = pwd.getpwnam('cloud-game')
    qemu = pwd.getpwnam('qemu')
    DEST.mkdir(mode=0o755)
    for folder in ('host', 'client', 'deploy', 'docs', 'licenses'):
        for file in (SOURCE / folder).rglob('*'):
            if file.is_symlink():
                raise RuntimeError('Symlink recusado no pacote de instalação.')
            if file.is_file() and '__pycache__' not in file.parts:
                target = DEST / file.relative_to(SOURCE)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, target)
                target.chmod(0o644)
    shutil.copyfile(SOURCE / 'package.json', DEST / 'package.json')
    from runtime import install_runtime
    install_runtime(DEST / 'runtime')
    root = pathlib.Path('/var/lib/cloudgame')
    root.mkdir(mode=0o751, exist_ok=True)
    control = root / 'control'
    control.mkdir(mode=0o700, exist_ok=True)
    os.chown(control, account.pw_uid, account.pw_gid)
    (root / 'volatile').mkdir(mode=0o750, exist_ok=True)
    config = pathlib.Path('/etc/cloud-game')
    config.mkdir(mode=0o755, exist_ok=True)
    write(config / 'vm.json', (SOURCE / 'deploy/vm.example.json').read_text(), 0o600)
    write(config / 'host.env', f'CG_ORIGIN=https://{dns}\nCG_STREAM_HOST={address}\n', 0o600)
    units = ['cloud-game.service', 'cloud-game-network.service', 'cloud-game-watchdog.service', 'cloud-game-watchdog.timer', 'var-lib-cloudgame-volatile.mount']
    for name in units:
        content = (SOURCE / 'deploy' / name).read_text().replace('ExecStart=/usr/bin/node ', 'ExecStart=/opt/cloud-game/runtime/node ')
        if name.endswith('.mount'):
            content = content.replace('mode=0750,', f'mode=0750,gid={qemu.pw_gid},')
        write(pathlib.Path('/etc/systemd/system') / name, content)
    sudo = pathlib.Path('/etc/sudoers.d/cloud-game')
    write(sudo, 'cloud-game ALL=(root) NOPASSWD: /usr/bin/python3 /opt/cloud-game/deploy/vm_helper.py\n', 0o440)
    run('visudo', '-cf', str(sudo))
    run('semanage', 'fcontext', '-a', '-t', 'virt_image_t', '/var/lib/cloudgame/volatile(/.*)?')
    run('semanage', 'fcontext', '-a', '-t', 'virt_image_t', '/var/lib/cloudgame/base.qcow2')
    run('restorecon', '-R', str(root))
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', '--now', 'cloud-game.service', 'cloud-game-watchdog.timer')
    print(json.dumps({'url': 'https://' + dns, 'state': 'blocked until template prepared', 'next': 'tailscale serve --bg http://127.0.0.1:8787'}))


if __name__ == '__main__':
    try:
        install()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
