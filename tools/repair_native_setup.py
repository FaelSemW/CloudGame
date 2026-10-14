#!/usr/bin/python3
"""Repair only the known preview-1 saved wizard, preserving state and firewall."""
import fcntl
import hashlib
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
import urllib.request
import zipfile

ROOT = Path('/var/lib/cloud-game-native-installer')
OLD = 'd26bcb4206dd7f9aa14dabe8b8e255c9eacc216ea093eddbfe9814808ebc6d36'
NEW = '954e007ce74b2ecac080340ab31e96efa64ebebd932aa26bda90e2ef2e5f4c0a'
PACKAGE = 'bb880fc697678c1c9bf916116b6c1ce594468e5f17ac62ebcb21ac5f13ae98a8'
URL = 'https://raw.githubusercontent.com/FaelSemW/CloudGame/main/downloads/host-native-preview-2/cloud-game.pyz'


def digest(data): return hashlib.sha256(data).hexdigest()


def trusted(path, directory=False):
    info = path.lstat()
    if info.st_uid != 0 or info.st_mode & 0o022 or not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise RuntimeError('Caminho inesperado; nada alterado: ' + str(path))


def main():
    if os.geteuid() != 0: raise RuntimeError('Execute com sudo python3.')
    for directory in (Path('/var'), Path('/var/lib'), ROOT, ROOT / 'source', ROOT / 'source/deploy'):
        trusted(directory, True)
    target = ROOT / 'source/deploy/setup_host.py'
    trusted(target)
    lock_path = ROOT / 'setup.lock'
    trusted(lock_path)
    with open(lock_path, 'a', opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW, 0o600)) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        original = target.read_bytes()
        if digest(original) == NEW:
            print('Correção já aplicada.', flush=True)
        else:
            if digest(original) != OLD:
                raise RuntimeError('Versão salva diferente da preview-1; arquivo preservado para revisão.')
            with urllib.request.urlopen(URL, timeout=60) as response:
                if not response.url.startswith('https://'): raise RuntimeError('Download recusado.')
                archive = response.read(8 * 1024 * 1024)
            if digest(archive) != PACKAGE: raise RuntimeError('Integridade do pacote inválida.')
            with zipfile.ZipFile(io.BytesIO(archive)) as package:
                updated = package.read('payload/deploy/setup_host.py')
            if digest(updated) != NEW: raise RuntimeError('Integridade da correção inválida.')
            compile(updated, str(target), 'exec')
            backup = target.with_name('setup_host.py.before-firewall-fix')
            if backup.exists() or backup.is_symlink():
                trusted(backup)
                if backup.read_bytes() != original: raise RuntimeError('Backup diferente; preservado.')
            else:
                with open(backup, 'xb', opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW, 0o600)) as stream:
                    stream.write(original); stream.flush(); os.fsync(stream.fileno())
            descriptor, temporary = tempfile.mkstemp(prefix='.setup-repair-', dir=target.parent)
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(updated); stream.flush(); os.fsync(stream.fileno())
                os.chmod(temporary, 0o644)
                os.replace(temporary, target)
                directory_fd = os.open(target.parent, os.O_DIRECTORY)
                try: os.fsync(directory_fd)
                finally: os.close(directory_fd)
            finally:
                if os.path.exists(temporary): os.unlink(temporary)
            print('Retomada corrigida. Progresso e regras do firewall preservados.', flush=True)
    os.execv('/usr/bin/python3', ['/usr/bin/python3', str(target)])


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print('Reparo interrompido: ' + str(error), file=sys.stderr)
        sys.exit(1)
