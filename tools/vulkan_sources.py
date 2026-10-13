"""Preserve the pinned shaderc SDK source set next to Windows downloads."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def download(item):
    repo, commit = item['subrepo'], item['commit']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo) or not re.fullmatch(r'[a-f0-9]{40}', commit):
        raise ValueError('Invalid pinned source')
    url = f'https://codeload.github.com/{repo}/tar.gz/{commit}'
    with urllib.request.urlopen(url, timeout=90) as response:
        data = response.read()
    # Preserve the complete upstream archive without extracting remote paths.
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        if not archive.getmembers():
            raise RuntimeError('Empty source archive')
    return item, data, url


def main():
    pin = ROOT / 'licenses/vulkan-sdk-1.4.363.0/shaderc-known-good.json'
    items = json.loads(pin.read_text())['commits']
    output = ROOT / 'dist/CloudGame-Vulkan-SDK-sources.tar'
    output.parent.mkdir(exist_ok=True)
    manifest = []
    with tarfile.open(output, 'w') as bundle, ThreadPoolExecutor(max_workers=4) as pool:
        for item, data, url in pool.map(download, items):
            name = item['name'] + '-' + item['commit'] + '.tar.gz'
            entry = tarfile.TarInfo(name); entry.size = len(data)
            bundle.addfile(entry, io.BytesIO(data))
            manifest.append(dict(item, archive=name, url=url, sha256=hashlib.sha256(data).hexdigest()))
        data = json.dumps(manifest, indent=2).encode()
        entry = tarfile.TarInfo('SOURCE-MANIFEST.json'); entry.size = len(data)
        bundle.addfile(entry, io.BytesIO(data))
        bundle.add(pin, arcname='shaderc-known-good.json')
    print(output)


if __name__ == '__main__':
    main()
