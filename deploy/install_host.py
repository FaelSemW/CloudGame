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
import stat
import uuid
import argparse

SOURCE = pathlib.Path(__file__).resolve().parent.parent
DEST = pathlib.Path('/opt/cloud-game')
UNITS = ['cloud-game.service', 'cloud-game-network.service', 'cloud-game-watchdog.service', 'cloud-game-watchdog.timer', 'var-lib-cloudgame-volatile.mount']


def trusted_directory(path):
    path.mkdir(mode=0o751, parents=True, exist_ok=True)
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise RuntimeError('Diretório de instalação inseguro; preservado: ' + str(path))


def serve_available(configuration):
    # Never reset an existing reverse proxy or public Funnel configuration.
    if configuration not in ({}, None):
        raise RuntimeError('Tailscale Serve já possui configuração. Ela foi preservada; reserve um HOST sem outro Serve/Funnel antes de instalar.')


def run(*args):
    return subprocess.run(args, text=True, capture_output=True, check=True).stdout.strip()


def write(path, text, mode=0o644):
    if path.exists() or path.is_symlink():
        raise RuntimeError(f'Arquivo existente preservado: {path}. Atualize manualmente após revisar o diff.')
    path.write_text(text)
    path.chmod(mode)


def install(software=False):
    if os.geteuid() != 0 or 'bazzite' not in pathlib.Path('/etc/os-release').read_text().lower():
        raise RuntimeError('Execute no Bazzite com pkexec, após preparar virtualização pelo Bazzite Portal.')
    if DEST.exists() or DEST.is_symlink():
        raise RuntimeError('/opt/cloud-game já existe; atualização automática não substituirá sua instalação.')
    required = ['virsh', 'qemu-img', 'qemu-system-x86_64', 'nft', 'tailscale', 'ip', 'sudo', 'restorecon', 'semanage', 'visudo']
    missing = [x for x in required if not shutil.which(x)]
    if missing:
        raise RuntimeError('Pré-requisitos ausentes: ' + ', '.join(missing) + '. Consulte docs/BAZZITE.md; não instale pacotes com apt/dnf no HOST.')
    from network_setup import validate_network, firewall_plan
    validate_network(json.loads(run('ip', '-details', '-json', 'link', 'show')),
                     json.loads(run('ip', '-json', '-4', 'route', 'show', 'table', 'all')))
    firewall_plan()  # Detect conflicts before building a guest or changing host accounts.
    run('virsh', '-c', 'qemu:///system', 'list', '--all')
    info = json.loads(run('tailscale', 'status', '--json'))
    dns = info.get('Self', {}).get('DNSName', '').rstrip('.')
    addresses = info.get('Self', {}).get('TailscaleIPs', [])
    address = next((a for a in addresses if re.fullmatch(r'100\.\d+\.\d+\.\d+', a)), None)
    if not address or not re.fullmatch(r'[a-z0-9.-]+\.ts\.net', dns):
        raise RuntimeError('Conecte o HOST ao Tailscale e habilite MagicDNS/HTTPS antes de instalar.')
    serve_available(json.loads(run('tailscale', 'serve', 'status', '--json')))
    # Refuse all known conflicts before starting a long image build or changing accounts.
    outputs = [pathlib.Path('/etc/systemd/system') / name for name in UNITS]
    outputs += [pathlib.Path('/etc/sudoers.d/cloud-game'), pathlib.Path('/etc/cloud-game/vm.json'), pathlib.Path('/etc/cloud-game/host.env')]
    for output in outputs:
        if output.exists() or output.is_symlink():
            raise RuntimeError('Configuração existente preservada: ' + str(output))
    from hardware import dedicated_gpus
    candidates = dedicated_gpus()
    if not software and len(candidates) != 1:
        raise RuntimeError('Não há uma única GPU já dedicada a VFIO. Configure GPU/IOMMU primeiro; para testar em VM sem GPU, use install --software (renderização/encoding por CPU, desempenho limitado). Nenhum driver do proprietário foi alterado.')
    if not software and candidates[0]['vendor'] == '0x10de':
        raise RuntimeError('A imagem automática ainda não inclui o driver proprietário NVIDIA. Prepare uma imagem com o driver ou teste primeiro o perfil --software. Não será anunciada compatibilidade de GPU sem driver.')
    root = pathlib.Path('/var/lib/cloudgame')
    trusted_directory(root)
    base = root / 'base.qcow2'
    if base.exists() or base.is_symlink():
        info = base.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o222:
            raise RuntimeError('Imagem existente precisa ser regular, root e somente leitura; preservada.')
    else:
        if shutil.disk_usage(root).free < 16 * 1024**3:
            raise RuntimeError('Reserve ao menos 16 GiB livres para preparar a imagem inicial.')
        from build_image import build
        image = build(root / ('image-build-' + uuid.uuid4().hex))
        # Link refuses an unexpected existing destination; both paths are on the same volume.
        os.link(image, base)
        image.unlink()
    from verify_image import verify
    verify(base, pathlib.Path('/tmp') / ('cg-check-' + uuid.uuid4().hex[:12]))
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
    control = root / 'control'
    control.mkdir(mode=0o700, exist_ok=True)
    os.chown(control, account.pw_uid, account.pw_gid)
    (root / 'volatile').mkdir(mode=0o750, exist_ok=True)
    config = pathlib.Path('/etc/cloud-game')
    trusted_directory(config)
    vm = {'templateReviewed': True, 'profile': 'software' if software else 'vfio',
          'memoryMiB': 2048 if software else 8192, 'cpus': 2 if software else 4,
          'gpuDevices': [] if software else candidates[0]['devices']}
    write(config / 'vm.json', json.dumps(vm, indent=2), 0o600)
    write(config / 'host.env', f'CG_ORIGIN=https://{dns}\nCG_STREAM_HOST={address}\n', 0o600)
    for name in UNITS:
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
    # Background HTTPS stays inside the tailnet; no Funnel or router port is enabled.
    run('tailscale', 'serve', '--bg', '--https=443', 'http://127.0.0.1:8787')
    write(config / 'installed.json', json.dumps({'installer': 'cloud-game-v1', 'profile': vm['profile']}), 0o600)
    print(json.dumps({'url': 'https://' + dns, 'image': str(base),
        'profile': vm['profile'], 'state': 'installed; HOST recovery determines availability',
        'next': 'Crie o administrador no endereço privado e consulte o diagnóstico. O perfil software tem desempenho limitado e não valida GPU física.'}))


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--software', action='store_true', help='VM isolada com vídeo/encoding por CPU para validação, sem passthrough.')
        args = parser.parse_args()
        install(args.software)
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
