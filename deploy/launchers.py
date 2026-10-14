"""Desktop entries are written as their owner, never through root into a user home."""
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys


def entry(kind, dns=''):
    if kind == 'setup':
        name = 'Cloud Game — continuar instalação'
        command = '/usr/bin/pkexec /usr/bin/python3 /var/lib/cloud-game-native-installer/source/deploy/setup_host.py --window'
        terminal = 'true'
    elif kind == 'host' and re.fullmatch(r'[a-z0-9.-]+\.ts\.net', dns):
        name = 'Cloud Game HOST'
        command = '/usr/bin/xdg-open https://' + dns
        terminal = 'false'
    else:
        raise ValueError('Atalho inválido')
    return ('[Desktop Entry]\nType=Application\nVersion=1.0\nName=' + name +
            '\nComment=Cloud Game: painel do computador de jogos\nExec=' + command +
            '\nTerminal=' + terminal + '\nIcon=applications-games\nCategories=Game;Network;\n'
            'Keywords=cloudgame;cloud;game;host;jogos;streaming;\nStartupNotify=true\n')


def install_for_user(uid, kind, dns=''):
    if uid is None: return
    account = pwd.getpwuid(int(uid))
    if account.pw_uid < 1000 or account.pw_uid == 65534:
        raise RuntimeError('Atalho requer usuário desktop comum.')
    subprocess.run(['runuser', '-u', account.pw_name, '--', '/usr/bin/python3', '-', kind, dns],
                   input=Path(__file__).read_text(), text=True, check=True,
                   env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'HOME': account.pw_dir, 'LANG': 'C.UTF-8'})


def user_install(kind, dns):
    if os.geteuid() == 0: raise RuntimeError('Não gravar na home como root.')
    home = Path(pwd.getpwuid(os.geteuid()).pw_dir)
    content = entry(kind, dns)
    filename = 'cloud-game-host.desktop' if kind == 'host' else 'cloud-game-native-setup.desktop'
    menu = home / '.local/share/applications'
    menu.mkdir(parents=True, exist_ok=True)
    destinations = [menu]
    if shutil.which('xdg-user-dir'):
        result = subprocess.run(['xdg-user-dir', 'DESKTOP'], text=True, capture_output=True, check=True)
        desktop = Path(result.stdout.strip())
        if desktop.is_absolute() and desktop != home and desktop.is_dir(): destinations.append(desktop)
    for directory in destinations:
        target = directory / filename
        if target.exists() or target.is_symlink():
            if target.is_symlink() or target.read_text() != content:
                print('Atalho existente preservado: ' + str(target)); continue
        else:
            with target.open('x') as stream: stream.write(content)
        target.chmod(0o755)
    if shutil.which('update-desktop-database'):
        subprocess.run(['update-desktop-database', str(menu)], check=False)


if __name__ == '__main__':
    user_install(sys.argv[1], sys.argv[2])
