#!/usr/bin/python3
"""Small optional graphical launcher; privileged installation remains reviewable."""
import pathlib
import shutil
import subprocess
import sys

if not shutil.which('zenity'):
    sys.exit('Zenity não disponível. Use o procedimento documentado em docs/BAZZITE.md.')
if subprocess.run(['zenity', '--question', '--width=540', '--title=Instalar Cloud Game HOST', '--text=Este instalador adicionará o HOST, uma bridge privada e HTTPS Tailscale. Baixará uma base Ubuntu e Sunshine oficial e preparará a imagem de jogos automaticamente (16 GiB livres; pode levar vários minutos). Requer virtualização e Tailscale preparados. A GPU dedicada ainda precisa de configuração e teste. Continuar?']).returncode == 0:
    result = subprocess.run(['pkexec', '/usr/bin/python3', str(pathlib.Path(__file__).with_name('install_host.py'))], text=True, capture_output=True)
    subprocess.run(['zenity', '--info' if result.returncode == 0 else '--error', '--width=620', '--text=' + (result.stdout or result.stderr)])
