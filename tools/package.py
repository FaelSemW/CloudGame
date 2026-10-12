"""Build a self-contained source installer; excludes private data and checkouts."""
import hashlib
import json
from pathlib import Path
import tempfile
import shutil
import zipapp

ROOT = Path(__file__).resolve().parents[1]


def build():
    out = ROOT / 'dist'
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        stage = Path(directory)
        shutil.copyfile(ROOT / 'tools/package_cli.py', stage / '__main__.py')
        payload = stage / 'payload'
        payload.mkdir()
        for folder in ('host', 'client', 'deploy', 'docs', 'licenses'):
            for source in (ROOT / folder).rglob('*'):
                if source.is_file() and not source.is_symlink() and '__pycache__' not in source.parts:
                    target = payload / source.relative_to(ROOT)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
        for name in ('LICENSE', 'README.md', 'package.json'):
            shutil.copyfile(ROOT / name, payload / name)
        manifest = {p.relative_to(payload).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(payload.rglob('*')) if p.is_file()}
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        artifact = out / 'cloud-game.pyz'
        zipapp.create_archive(stage, artifact, interpreter='/usr/bin/env python3', compressed=True)
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        (out / 'SHA256SUMS').write_text(f'{digest}  {artifact.name}\n')
        shutil.copyfile(ROOT / 'docs/PACKAGE.md', out / 'LEIA-ME.md')
        print(artifact)


if __name__ == '__main__':
    build()
