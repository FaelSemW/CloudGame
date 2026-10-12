"""Download official Node 22 runtime with checksum and license preservation."""
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import urllib.request


def install_runtime(destination):
    destination = Path(destination)
    base = 'https://nodejs.org/dist/latest-v22.x/'
    checks = urllib.request.urlopen(base + 'SHASUMS256.txt', timeout=30).read().decode()
    match = re.search(r'^([a-f0-9]{64})\s+(node-v22\.[0-9.]+-linux-x64\.tar\.xz)$', checks, re.M)
    if not match:
        raise RuntimeError('Runtime oficial não encontrado.')
    digest, name = match.groups()
    archive = urllib.request.urlopen(base + name, timeout=120).read()
    if hashlib.sha256(archive).hexdigest() != digest:
        raise RuntimeError('Checksum do runtime inválido.')
    destination.mkdir()
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:xz') as tar:
        for inside, filename in [('bin/node', 'node'), ('LICENSE', 'LICENSE')]:
            member = tar.getmember(name.removesuffix('.tar.xz') + '/' + inside)
            if not member.isfile():
                raise RuntimeError('Arquivo de runtime inválido.')
            (destination / filename).write_bytes(tar.extractfile(member).read())
    (destination / 'node').chmod(0o755)
    (destination / 'provenance.json').write_text(json.dumps({'url': base + name, 'sha256': digest}))
