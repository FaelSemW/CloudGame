"""Verify Qt's exact source archive and collect its original license notices."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tarfile
from source_bundle import legal

VERSION = '6.12.0'
SHA256 = '98ff4f44bac6ec3e1e62ee2a4316ae0e3d15badb015d753cc0268a20db52f165'
URL = 'https://download.qt.io/official_releases/qt/6.12/6.12.0/single/qt-everywhere-src-6.12.0.tar.xz'


def collect(source, destination):
    with source.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != SHA256:
        raise RuntimeError('Qt source archive does not match the reviewed official SHA-256')
    count = 0
    with tarfile.open(source, 'r|xz') as archive:
        for entry in archive:
            name = PurePosixPath(entry.name)
            if name.is_absolute() or '..' in name.parts:
                raise RuntimeError('Unsafe Qt source path')
            if not entry.isfile() or not legal(entry.name):
                continue
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.extractfile(entry).read())
            count += 1
    if count < 1:
        raise RuntimeError('No Qt notices found')
    (destination / 'qt-source.json').write_text(json.dumps({
        'version': VERSION, 'source': URL, 'sha256': SHA256,
        'noticeFiles': count,
        'note': 'Original notices from all source modules; shipped DLL inventory must be reviewed separately.'
    }, indent=2))
    print(f'Qt {VERSION}: {count} original notice files preserved; source SHA-256 verified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    collect(args.source, args.destination)
