#!/usr/bin/python3
"""Provision a clean Linux X11 guest. Does not install third-party software."""
import getpass
import grp
import json
import os
import pathlib
import pwd
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
    for command in ('sunshine','qemu-ga','journalctl','systemctl'):
        if not shutil.which(command):
            sys.exit('Componente ausente na VM: ' + command)
    if shutil.which('sunshine') != '/usr/bin/sunshine':
        sys.exit('Esta unidade requer Sunshine nativo em /usr/bin/sunshine, não Flatpak.')
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
    print('Defina a credencial administrativa do Sunshine no primeiro acesso local a https://localhost:47990.\nEsta credencial é interna à VM e NÃO é uma senha Steam.')
    username = input('Usuário administrativo do Sunshine: ').strip()
    password = getpass.getpass('Senha administrativa do Sunshine (12+ caracteres): ')
    if not username or len(password) < 12:
        sys.exit('Credencial inválida.')
    target.write_text(json.dumps({'username':username,'password':password}))
    target.chmod(0o600)
    libexec = pathlib.Path('/usr/local/libexec')
    libexec.mkdir(exist_ok=True)
    shutil.copyfile(HERE / 'cloud-game-guest', libexec / 'cloud-game-guest')
    (libexec / 'cloud-game-guest').chmod(0o755)
    service = pathlib.Path('/etc/systemd/system/cloud-game-sunshine.service')
    if service.exists():
        sys.exit('Unidade de serviço existente preservada.')
    shutil.copyfile(HERE / service.name, service)
    run('systemctl','daemon-reload')
    run('systemctl','enable','qemu-guest-agent.service','cloud-game-sunshine.service')
    print('Arquivos preparados. Configure rede estática, autologin X11, Sunshine local e teste captura/GPU antes de selar a imagem. Consulte docs/BAZZITE.md.')


if __name__ == '__main__':
    main()
