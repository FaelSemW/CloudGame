#!/usr/bin/python3
"""Small optional graphical launcher; privileged installation remains reviewable."""
import pathlib
import shutil
import subprocess
import sys

if not shutil.which('zenity'):
    sys.exit('Zenity não disponível. Use o procedimento documentado em docs/BAZZITE.md.')
profile = subprocess.run(['zenity', '--list', '--radiolist', '--width=620', '--height=280',
    '--title=Instalar Cloud Game HOST', '--text=Escolha o perfil. A imagem com Sunshine será criada automaticamente. Tailscale precisa estar conectado; reserve 16 GiB de disco e 8 GiB de RAM no HOST/VM.',
    '--column=Escolher', '--column=Perfil', 'TRUE', 'GPU dedicada já configurada em VFIO',
    'FALSE', 'Teste em VM por CPU (desempenho limitado)'], text=True, capture_output=True)
if profile.returncode != 0:
    sys.exit(0)
software = profile.stdout.strip() == 'Teste em VM por CPU (desempenho limitado)'
progress = subprocess.Popen(['zenity', '--progress', '--pulsate', '--no-cancel', '--auto-close', '--width=540',
    '--title=Instalando Cloud Game', '--text=Baixando componentes e preparando o ambiente isolado. Esta etapa pode levar vários minutos.'], stdin=subprocess.PIPE)
try:
    result = subprocess.run(['pkexec', '/usr/bin/python3', str(pathlib.Path(__file__).with_name('install_host.py'))]
        + (['--software'] if software else []), text=True, capture_output=True)
finally:
    if progress.stdin:
        try: progress.stdin.close()
        except BrokenPipeError: pass
    try: progress.wait(timeout=5)
    except subprocess.TimeoutExpired: progress.terminate(); progress.wait()
subprocess.run(['zenity', '--info' if result.returncode == 0 else '--error', '--width=620',
    '--text=' + ((result.stdout or result.stderr)[-8000:])])
