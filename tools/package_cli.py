"""Cloud Game package entry point. Python standard library only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile


def unpack(destination):
    with zipfile.ZipFile(Path(sys.argv[0]).resolve()) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        for name, digest in manifest.items():
            relative = Path(name)
            if relative.is_absolute() or '..' in relative.parts or '\\' in name:
                raise RuntimeError('Caminho inválido no pacote.')
            content = archive.read('payload/' + name)
            if hashlib.sha256(content).hexdigest() != digest:
                raise RuntimeError('Integridade inválida: ' + name)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)


def doctor():
    release = Path('/etc/os-release')
    bazzite = release.exists() and 'bazzite' in release.read_text().lower()
    requirements = ('python3', 'virsh', 'qemu-img', 'nft', 'tailscale', 'sudo', 'restorecon', 'semanage')
    result = {'system': platform.system(), 'architecture': platform.machine(),
              'bazzite': bazzite, 'kvm': Path('/dev/kvm').exists(),
              'tools': {name: bool(shutil.which(name)) for name in requirements},
              'template': Path('/var/lib/cloudgame/base.qcow2').is_file(),
              'note': 'Esta verificação não comprova GPU, isolamento ou streaming. Consulte docs/ACCEPTANCE.md.'}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if bazzite and result['kvm'] and all(result['tools'].values()) else 2


def main():
    parser = argparse.ArgumentParser(description='Cloud Game 0.1 — pacote de avaliação, streaming ainda não homologado.')
    parser.add_argument('command', choices=['verify', 'doctor', 'install', 'run', 'logs'])
    parser.add_argument('--lab', action='store_true', help='Instala apenas o controle local; streaming bloqueado explicitamente.')
    args = parser.parse_args()
    if args.command == 'doctor':
        return doctor()
    lab = Path.home() / '.local/share/cloud-game-lab'
    if args.command == 'logs':
        return subprocess.call(['journalctl', '-u', 'cloud-game', '-b', '--no-pager'])
    if args.command == 'run':
        node = lab / 'runtime/node'
        if not node.is_file():
            raise RuntimeError('Instale primeiro: python3 cloud-game.pyz install --lab')
        env = dict(os.environ, CG_LAB='1', CG_DATA=str(lab / 'data'), CG_ORIGIN='http://127.0.0.1:8787', CG_STREAM_HOST='')
        print('Abra http://127.0.0.1:8787 e use o código mostrado abaixo. Ctrl+C encerra o serviço.', flush=True)
        return subprocess.call([str(node), str(lab / 'host/server.mjs')], env=env, cwd=lab)
    with tempfile.TemporaryDirectory(prefix='cloud-game-') as folder:
        source = Path(folder)
        unpack(source)
        if args.command == 'verify':
            print('Integridade de todos os arquivos do pacote: OK')
            return 0
        if platform.system() != 'Linux' or platform.machine() not in ('x86_64', 'amd64'):
            raise RuntimeError('O instalador requer Linux x86_64. Execute dentro do Bazzite.')
        if args.lab:
            if os.geteuid() == 0:
                raise RuntimeError('O laboratório deve ser instalado como usuário comum, sem sudo.')
            if lab.exists() or lab.is_symlink():
                raise RuntimeError(f'Instalação existente preservada em {lab}. Use o comando run.')
            sys.path.insert(0, str(source / 'deploy'))
            from runtime import install_runtime
            install_runtime(source / 'runtime')
            lab.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, lab)
            print('Controle local instalado. Streaming indisponível neste modo.')
        else:
            if doctor() != 0:
                raise RuntimeError('Pré-requisitos ausentes. Use install --lab para testar o painel na VM; consulte docs/BAZZITE.md para o HOST.')
            if os.geteuid() != 0:
                raise RuntimeError('Para o HOST de produção use: sudo python3 cloud-game.pyz install')
            return subprocess.call([sys.executable, str(source / 'deploy/install_host.py')])
    return subprocess.call([sys.executable, str(Path(sys.argv[0]).resolve()), 'run'])


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError, ValueError, zipfile.BadZipFile) as error:
        print(f'Cloud Game: {error}', file=sys.stderr)
        sys.exit(1)
