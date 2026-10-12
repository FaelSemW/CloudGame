"""Package tracked native sources, including pinned submodules and applied overlays.

Never walks build directories or archives Git credentials. Qt SDK sources are a
separate release input; this archive does not claim to contain that SDK.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    'moonlight-qt': 'a57e947d7185fd01384f6973df4df59ae2968d01',
    'moonlight-android': 'b48494cb96bff23d8886c4775cc4f39a1075495d',
    'moonlight-qt-deps': '79621271459ebb945343f58d7acd6ad24d402c38',
}


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args])


def tracked(repo):
    entries = git(repo, 'ls-files', '--stage', '--recurse-submodules', '-z').decode().split('\0')
    for entry in sorted(filter(None, entries)):
        metadata, name = entry.split('\t', 1)
        mode, _, stage = metadata.split()
        if stage != '0':
            raise RuntimeError('Unresolved merge: ' + name)
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '.git' in relative.parts:
            raise RuntimeError('Unsafe source path: ' + name)
        path = repo / name
        if path.is_dir():
            raise RuntimeError('Uninitialized submodule: ' + name)
        if not path.exists() and not path.is_symlink():
            raise RuntimeError('Missing tracked source: ' + name)
        yield name, (path, int(mode, 8) & 0o777)


def legal(name):
    parts = PurePosixPath(name).parts
    base = parts[-1].lower()
    return (any(p.lower() == 'licenses' for p in parts) or
            base.startswith(('license', 'licence', 'copying', 'copyright', 'notice')))


def bundle(names, output, notices):
    manifest = {'format': 1, 'repositories': {}, 'files': {}}
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents silently replacing previously published bytes.
    with output.open('xb') as stream, tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for name in ['cloudgame', *names]:
            repo = ROOT if name == 'cloudgame' else ROOT / 'third_party' / name
            commit = git(repo, 'rev-parse', 'HEAD').decode().strip()
            if name != 'cloudgame' and commit != PINS[name]:
                raise RuntimeError('Source commit does not match lock: ' + name)
            submodules = git(repo, 'submodule', 'status', '--recursive').decode()
            if any(line.startswith(('-', '+', 'U')) for line in submodules.splitlines()):
                raise RuntimeError('Submodule lock mismatch: ' + name)
            manifest['repositories'][name] = {'commit': commit, 'submodules': submodules.splitlines()}
            files = dict(tracked(repo))
            if name in ('moonlight-qt', 'moonlight-android'):
                stamp = repo / '.git/cloudgame-overlay.json'
                overlays = json.loads(stamp.read_text())
                for relative, digest in overlays.items():
                    path = repo / relative
                    actual = hashlib.sha256(path.read_text(encoding='utf-8').replace('\r\n', '\n').encode()).hexdigest()
                    if actual != digest:
                        raise RuntimeError('Overlay changed after assembly: ' + relative)
                    files[relative] = (path, files.get(relative, (None, 0o644))[1])
            for relative, (path, mode) in sorted(files.items()):
                target = name + '/' + relative
                info = archive.gettarinfo(str(path), arcname=target)
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ''
                if info.issym():
                    link = PurePosixPath(info.linkname)
                    resolved = path.resolve()
                    if link.is_absolute() or not resolved.is_relative_to(repo.resolve()):
                        raise RuntimeError('Source symlink escapes repository: ' + target)
                    archive.addfile(info)
                    manifest['files'][target] = {'symlink': info.linkname}
                elif info.isfile():
                    payload = path.read_bytes()
                    info.mode = mode
                    archive.addfile(info, io.BytesIO(payload))
                    manifest['files'][target] = hashlib.sha256(payload).hexdigest()
                    if legal(relative):
                        notice = notices / target
                        notice.parent.mkdir(parents=True, exist_ok=True)
                        notice.write_bytes(payload)
                else:
                    raise RuntimeError('Unexpected source type: ' + target)
        payload = json.dumps(manifest, indent=2).encode()
        info = tarfile.TarInfo('SOURCE-MANIFEST.json'); info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    print(json.dumps({'archive': str(output), 'files': len(manifest['files']),
                      'sha256': hashlib.sha256(output.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('projects', nargs='+', choices=list(PINS))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--notices', type=Path, required=True)
    args = parser.parse_args()
    bundle(args.projects, args.output, args.notices)
