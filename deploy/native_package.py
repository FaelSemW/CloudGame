"""Verified native Sunshine RPM for the Fedora base used by Bazzite."""
import hashlib
from pathlib import Path
import re
import urllib.request

VERSION = '2026.914.233613'
DIGESTS = {
    '43': 'e44612e6e85458a183dc47a535c93c367ecf7f260b05daeac54bf0f4f5637080',
    '44': '2abb16033ecde677f5c45322b39b6d6ae4cf297ac3e36707aa90bd3911d0e00f',
    '45': 'a46b83e8c8e6c8fc2e0601464b43e9c3fd2f67907a23b537ea64ff58ba4fadf3',
    '46': '451c6c1ccee6edaa8734f12cd3fb9b0ffe2ce3d21cfe2681c9e9fd8c17c859c1',
}


def package(directory):
    match = re.search(r'^VERSION_ID=["\']?(\d+)', Path('/etc/os-release').read_text(), re.M)
    version = match[1] if match else ''
    if version not in DIGESTS: raise RuntimeError('Versão Fedora sem RPM Sunshine verificado.')
    name = f'Sunshine-{VERSION}-1.fc{version}.x86_64.rpm'
    target = directory / name
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() == DIGESTS[version]: return str(target)
        raise RuntimeError('Download Sunshine anterior incompleto; arquivo preservado para diagnóstico.')
    temporary = directory / (name + '.download')
    # Only this fixed staging file; never follow a link or overwrite owner data.
    if temporary.exists() or temporary.is_symlink(): temporary.unlink()
    url = f'https://github.com/LizardByte/Sunshine/releases/download/v{VERSION}/{name}'
    with urllib.request.urlopen(url, timeout=120) as response, temporary.open('xb') as stream:
        if not response.url.startswith('https://'): raise RuntimeError('Download não HTTPS recusado.')
        while block := response.read(1024 * 1024): stream.write(block)
    if hashlib.sha256(temporary.read_bytes()).hexdigest() != DIGESTS[version]:
        raise RuntimeError('Checksum Sunshine inválido.')
    temporary.rename(target)
    return str(target)
