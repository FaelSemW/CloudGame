#!/usr/bin/python3
"""Small optional graphical launcher; privileged installation remains reviewable."""
import pathlib
import shutil
import subprocess
import sys

if not shutil.which('zenity'):
    sys.exit('Zenity não disponível. Use o procedimento documentado em docs/BAZZITE.md.')
if subprocess.run(['zenity', '--question', '--width=540', '--title=Instalar Cloud Game HOST', '--text=Este instalador adicionará o serviço HOST, um controlador de VM e uma bridge privada. Requer Bazzite com virtualização e Tailscale preparados. Não configura automaticamente GPU passthrough nem sua imagem de jogos. Continuar?']).returncode == 0:
    result = subprocess.run(['pkexec', '/usr/bin/python3', str(pathlib.Path(__file__).with_name('install_host.py'))], text=True, capture_output=True)
    subprocess.run(['zenity', '--info' if result.returncode == 0 else '--error', '--width=620', '--text=' + (result.stdout or result.stderr)])
