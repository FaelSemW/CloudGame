#!/usr/bin/python3
"""Provision a clean Linux X11 guest. Does not install third-party software."""
import grp
import json
import os
import pathlib
import pwd
import secrets
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent


def run(*args):
    subprocess.run(args, check=True)


def main():
    if os.geteuid() != 0:
        sys.exit('Execute como root DENTRO da VM limpa, nunca no HOST.')
    product = pathlib.Path('/sys/class/dmi/id/product_name').read_text().lower()
    if not any(x in product for x in ('qemu','kvm','standard pc')):
        sys.exit('Este provisionador exige uma VM QEMU/KVM.')
    player = pwd.getpwnam('player')
    if player.pw_uid != 1000 or player.pw_dir != '/home/player':
        sys.exit('Crie o usuário player com UID 1000 e home /home/player.')
    denied = {'sudo','wheel','docker','libvirt','disk','lxd'}
    groups = {g.gr_name for g in grp.getgrall() if 'player' in g.gr_mem or g.gr_gid == player.pw_gid}
    if groups & denied:
        sys.exit('Remova os grupos administrativos do player: ' + ', '.join(groups & denied))
    for command in ('sunshine','qemu-ga','journalctl','systemctl','runuser','usermod','groupadd','udevadm','modprobe'):
        if not shutil.which(command):
            sys.exit('Componente ausente na VM: ' + command)
    if shutil.which('sunshine') != '/usr/bin/sunshine':
        sys.exit('Esta unidade requer Sunshine nativo em /usr/bin/sunshine, não Flatpak.')
    for output in ('/etc/cloud-game/sunshine-api.json', '/etc/systemd/system/cloud-game-sunshine.service',
                   '/usr/local/libexec/cloud-game-guest', '/etc/udev/rules.d/85-cloud-game-input.rules'):
        if pathlib.Path(output).exists() or pathlib.Path(output).is_symlink():
            sys.exit('Arquivo existente preservado: ' + output)
    home = pathlib.Path('/home/player')
    config = home / '.config/sunshine'
    if config.exists():
        sys.exit('Configuração Sunshine existente preservada. Use uma imagem limpa.')
    if any((home / p).exists() for p in ('.steam', '.local/share/Steam/config/loginusers.vdf')):
        sys.exit('Possíveis dados Steam encontrados. Este script não sanitiza uma imagem usada.')
    config.mkdir(parents=True, mode=0o700)
    for directory in (home / '.config', config):
        os.chown(directory, player.pw_uid, player.pw_gid)
    for filename in ('sunshine.conf','apps.json'):
        target = config / filename
        shutil.copyfile(HERE / filename, target)
        os.chown(target, player.pw_uid, player.pw_gid)
        target.chmod(0o600)
    credentials = pathlib.Path('/etc/cloud-game')
    credentials.mkdir(mode=0o700, exist_ok=True)
    target = credentials / 'sunshine-api.json'
    if target.exists():
        sys.exit('Credencial existente preservada.')
    # Provision the official CLI while this is an empty maintenance image.
    # Never print command arguments or exception repr: they contain this internal
    # administrative password (never a Steam credential).
    username = 'cloud-game-internal'
    password = secrets.token_urlsafe(32)
    result = subprocess.run(['runuser', '-u', 'player', '--', '/usr/bin/env',
        'HOME=/home/player', '/usr/bin/sunshine', str(config / 'sunshine.conf'),
        '--creds', username, password], capture_output=True)
    if result.returncode != 0:
        sys.exit('Falha ao configurar a credencial interna do Sunshine. A imagem ainda não pode ser selada.')
    target.write_text(json.dumps({'username':username,'password':password}))
    target.chmod(0o600)
    # These groups and devices are inside the disposable guest, never the HOST.
    available = {g.gr_name for g in grp.getgrall()}
    if 'input' not in available:
        run('groupadd', '--system', 'input')
        available.add('input')
    run('usermod', '-aG', ','.join(sorted(available & {'input', 'video', 'render'})), 'player')
    pathlib.Path('/etc/udev/rules.d/85-cloud-game-input.rules').write_text(
        'KERNEL=="uinput", SUBSYSTEM=="misc", GROUP="input", MODE="0660", OPTIONS+="static_node=uinput"\n')
    run('udevadm', 'control', '--reload-rules')
    run('modprobe', 'uinput')
    run('udevadm', 'trigger', '--subsystem-match=misc', '--sysname-match=uinput')
    libexec = pathlib.Path('/usr/local/libexec')
    libexec.mkdir(exist_ok=True)
    shutil.copyfile(HERE / 'cloud-game-guest', libexec / 'cloud-game-guest')
    (libexec / 'cloud-game-guest').chmod(0o755)
    shutil.copyfile(HERE / 'wait_desktop.py', libexec / 'cloud-game-wait-desktop.py')
    (libexec / 'cloud-game-wait-desktop.py').chmod(0o644)
    service = pathlib.Path('/etc/systemd/system/cloud-game-sunshine.service')
    if service.exists():
        sys.exit('Unidade de serviço existente preservada.')
    shutil.copyfile(HERE / service.name, service)
    run('systemctl','daemon-reload')
    run('systemctl','enable','qemu-guest-agent.service','cloud-game-sunshine.service')
    print('Serviço e credencial interna do Sunshine preparados. Configure rede estática e autologin X11, e teste captura/GPU antes de selar a imagem. Consulte docs/BAZZITE.md.')


if __name__ == '__main__':
    main()
