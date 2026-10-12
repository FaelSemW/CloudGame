"""Package the integrated client for Ubuntu 24.04 amd64, using distro runtime libraries."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
QML = ['qml6-module-qtquick','qml6-module-qtquick-controls','qml6-module-qtquick-templates',
       'qml6-module-qtquick-layouts','qml6-module-qtquick-window','qml6-module-qtqml-workerscript']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary',type=Path)
    args=parser.parse_args()
    binary=args.binary.resolve()
    if binary.read_bytes()[:4]!=b'\x7fELF': raise RuntimeError('Expected compiled Linux ELF executable')
    output=ROOT/'dist'
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        stage=Path(directory)
        (stage/'debian').mkdir()
        (stage/'debian/control').write_text('Source: cloud-game-client\nSection: games\nPriority: optional\nMaintainer: CloudGame <cloudgame@localhost>\n\nPackage: cloud-game-client\nArchitecture: amd64\nDescription: Integrated cloud gaming client\n')
        deps=subprocess.check_output(['dpkg-shlibdeps','-O','-e'+str(binary)],cwd=stage,text=True).strip()
        if not deps.startswith('shlibs:Depends='): raise RuntimeError('Could not resolve shared-library dependencies')
        package=stage/'package'
        exe=package/'usr/bin/cloud-game-client'
        exe.parent.mkdir(parents=True)
        shutil.copyfile(binary,exe); exe.chmod(0o755)
        desktop=package/'usr/share/applications/cloud-game.desktop'; desktop.parent.mkdir(parents=True)
        desktop.write_text('[Desktop Entry]\nType=Application\nName=Cloud Game\nExec=cloud-game-client\nIcon=cloud-game\nCategories=Game;\nTerminal=false\n')
        icon=package/'usr/share/icons/hicolor/scalable/apps/cloud-game.svg'; icon.parent.mkdir(parents=True)
        shutil.copyfile(ROOT/'client/icon.svg',icon)
        legal=package/'usr/share/doc/cloud-game-client'; legal.mkdir(parents=True)
        shutil.copyfile(ROOT/'LICENSE',legal/'copyright')
        shutil.copytree(ROOT/'licenses',legal/'licenses')
        (legal/'SOURCE').write_text('CloudGame: https://github.com/FaelSemW/CloudGame\nGPLv3 engine sources and build scripts accompany the release. Runtime libraries are supplied by Ubuntu repositories.\n')
        control=package/'DEBIAN'; control.mkdir()
        (control/'control').write_text('Package: cloud-game-client\nVersion: 0.1.0~dev1\nArchitecture: amd64\nMaintainer: CloudGame <cloudgame@localhost>\nSection: games\nPriority: optional\nDepends: '+deps.removeprefix('shlibs:Depends=')+', '+', '.join(QML)+'\nDescription: Cloud Game with integrated Moonlight streaming\n Platform authentication and native video, audio and controller support.\n')
        subprocess.run(['dpkg-deb','--build','--root-owner-group',str(package),str(output/'CloudGame-Ubuntu24-amd64.deb')],check=True)


if __name__=='__main__': main()
