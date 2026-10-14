#!/usr/bin/python3
"""Ubuntu 24.04 desktop + private network installer; no enrollment secrets."""
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tempfile
import urllib.request

RELEASE = 'v0.1.0-desktop-preview.2'
BASE = 'https://github.com/FaelSemW/CloudGame/releases/download/' + RELEASE + '/'
KEY_URL = 'https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg'
KEY_HASH = '3e03dacf222698c60b8e2f990b809ca1b3e104de127767864284e6c228f1fb39'


def download(url, limit):
    with urllib.request.urlopen(url, timeout=120) as response:
        if not response.url.startswith('https://'): raise RuntimeError('Download HTTPS obrigatório.')
        data = response.read(limit + 1)
        if len(data) > limit: raise RuntimeError('Download maior que o permitido.')
        return data


def provision(client):
    if not shutil.which('tailscale'):
        key = download(KEY_URL, 1024 * 1024)
        if hashlib.sha256(key).hexdigest() != KEY_HASH: raise RuntimeError('Chave do repositório Tailscale não confere.')
        outputs = {
            Path('/usr/share/keyrings/cloud-game-tailscale.gpg'): key,
            Path('/etc/apt/sources.list.d/cloud-game-tailscale.list'):
                b'deb [signed-by=/usr/share/keyrings/cloud-game-tailscale.gpg] https://pkgs.tailscale.com/stable/ubuntu noble main\n',
        }
        for target, data in outputs.items():
            if target.exists() or target.is_symlink():
                if target.is_symlink() or target.stat().st_uid != 0 or target.stat().st_mode & 0o022 or target.read_bytes() != data:
                    raise RuntimeError('Configuração existente preservada: ' + str(target))
        for target, data in outputs.items():
            if not target.exists():
                with target.open('xb') as stream: stream.write(data)
                target.chmod(0o644)
    subprocess.run(['apt-get', 'update'], check=True)
    subprocess.run(['apt-get', 'install', '-y', 'tailscale', 'policykit-1', str(client)], check=True)
    subprocess.run(['systemctl', 'enable', '--now', 'tailscaled'], check=True)


def main():
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if os.geteuid() != 0: raise RuntimeError('Execute este instalador com sudo python3.')
    if release.get('ID', '').strip('"') != 'ubuntu' or release.get('VERSION_ID', '').strip('"') != '24.04' or platform.machine() != 'x86_64':
        raise RuntimeError('Este pacote CLIENT requer Ubuntu 24.04 x86_64. Não execute no HOST Bazzite.')
    checks = download(BASE + 'SHA256SUMS', 1024 * 1024).decode()
    match = re.search(r'^([a-f0-9]{64})  CloudGame-Ubuntu24-amd64\.deb$', checks, re.M)
    if not match: raise RuntimeError('Pacote de cliente não publicado nesta versão.')
    data = download(BASE + 'CloudGame-Ubuntu24-amd64.deb', 256 * 1024 * 1024)
    if hashlib.sha256(data).hexdigest() != match[1]: raise RuntimeError('Integridade do cliente inválida.')
    with tempfile.TemporaryDirectory(prefix='cloud-game-client-') as stage:
        client = Path(stage) / 'cloud-game-client.deb'
        client.write_bytes(data)
        provision(client)
    print('Cloud Game e Tailscale instalados. Abra Cloud Game no menu e clique em Conectar rede privada para autorizar sua conta.')


if __name__ == '__main__':
    try: main()
    except Exception as error:
        raise SystemExit('Cloud Game: ' + str(error))
