#!/usr/bin/python3
"""Targeted repair for preview HOST entrypoint on Bazzite's symlinked /opt."""
from contextlib import ExitStack
import fcntl
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request

OLD = {'05c6038c5a398ce5a39d454605464063526f5844e8575ee585e4ab58b263d8c4',
       '0df29499c6a466644d2b28c27bbba9ef0bbd3ef029b1ef5846138cc1b6ef03de'}
NEW = '10f456e15db93e2e5c4972d58a72ce4b18d01ae01fd714eae7b193c58c87e345'
URL = 'https://raw.githubusercontent.com/FaelSemW/CloudGame/ea185a1/host/server.mjs'


def digest(data): return hashlib.sha256(data).hexdigest()


def trusted(path, directory=False):
    info = path.lstat()
    if info.st_uid != 0 or info.st_mode & 0o022 or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise RuntimeError('Arquivo/permissões inesperados; preservado: ' + str(path))


def replace(target, data):
    original = target.read_bytes()
    if digest(original) == NEW: return
    backup = target.with_name('server.mjs.before-start-fix')
    if backup.exists() or backup.is_symlink():
        trusted(backup)
        if backup.read_bytes() != original: raise RuntimeError('Backup diferente; preservado.')
    else:
        with open(backup, 'xb', opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW, 0o600)) as stream:
            stream.write(original); stream.flush(); os.fsync(stream.fileno())
    fd, temporary = tempfile.mkstemp(prefix='.host-start-fix-', dir=target.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, target)
        fd = os.open(target.parent, os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def main():
    if os.geteuid() != 0: raise RuntimeError('Execute com sudo python3.')
    files = [Path('/opt/cloud-game/host/server.mjs'),
             Path('/var/lib/cloud-game-native-installer/source/host/server.mjs')]
    for target in files:
        trusted(target)
        for parent in target.resolve().parents: trusted(parent, True)
        if digest(target.read_bytes()) not in OLD | {NEW}:
            raise RuntimeError('Versão diferente; arquivo preservado: ' + str(target))
    with urllib.request.urlopen(URL, timeout=45) as response:
        if not response.url.startswith('https://'): raise RuntimeError('Download recusado.')
        data = response.read(1024 * 1024)
    if digest(data) != NEW: raise RuntimeError('Integridade da correção inválida.')
    with ExitStack() as stack:
        for path in (Path('/var/lib/cloud-game-native-installer/setup.lock'), Path('/var/lib/cloudgame/native.lock')):
            trusted(path.parent, True)
            if path.exists() or path.is_symlink(): trusted(path)
            lock = stack.enter_context(open(path, 'a', opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW, 0o600)))
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if Path('/var/lib/cloudgame/native-session.json').exists():
            raise RuntimeError('Sessão registrada: encerre pelo painel antes do reparo.')
        for target in files: replace(target, data)
    print('Inicialização corrigida; backup salvo. Reiniciando o painel...', flush=True)
    subprocess.run(['systemctl', 'restart', 'cloud-game.service'], check=True, timeout=60)
    for _ in range(45):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8787/api/setup', timeout=2) as response:
                if response.status == 200:
                    print('Painel respondeu HTTP 200. Abra Cloud Game HOST ou atualize a página.', flush=True)
                    return
        except OSError: pass
        time.sleep(1)
    raise RuntimeError('Correção aplicada, mas o painel ainda não respondeu. Consulte journalctl -b -u cloud-game.service -n 30 --no-pager.')


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print('Reparo: ' + str(error), file=sys.stderr)
        sys.exit(1)
