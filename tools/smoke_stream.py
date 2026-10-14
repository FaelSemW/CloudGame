"""Exercise the real Moonlight/Sunshine transport in an ephemeral Linux CI VM.

No fabricated video: the screenshot is taken from the native player's display.
This checks software streaming, not physical GPU/controller or Bazzite networking.
"""
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deploy'))
from verify_image import execute


def stop(process):
    if process.poll() is None:
        process.terminate()
        try: process.wait(timeout=10)
        except subprocess.TimeoutExpired: process.kill(); process.wait()


def check(channel, binary, output, control=None, host='127.0.0.1'):
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        raise RuntimeError('Streaming smoke test runs only in the disposable CI environment')
    output.mkdir(exist_ok=True)
    if control is None:
        control = lambda op, pin=None: json.loads(execute(channel, '/usr/local/libexec/cloud-game-guest', [op], pin))
    env = dict(os.environ, QT_QUICK_BACKEND='software', SDL_AUDIODRIVER='dummy',
               XDG_CONFIG_HOME=str(output / 'private-config'))
    pin = f'{secrets.randbelow(10000):04d}'
    with (output / 'pair.log').open('w') as log:
        process = subprocess.Popen([str(binary), 'pair', host, '--pin', pin],
                                   stdout=log, stderr=subprocess.STDOUT, env=env)
        try:
            approval = control('pair', pin)
            if approval.get('status') is not True:
                raise RuntimeError('Sunshine did not confirm the native pairing handshake')
            time.sleep(2)  # Allow Qt to persist the completed handshake before closing its dialog.
        finally: stop(process)
    with (output / 'stream.log').open('w') as log:
        process = subprocess.Popen([str(binary), 'stream', host, 'Desktop',
            '--resolution', '640x480', '--fps', '30', '--bitrate', '2000',
            '--video-decoder', 'software', '--video-codec', 'H.264',
            '--display-mode', 'windowed', '--performance-overlay'],
            stdout=log, stderr=subprocess.STDOUT, env=env)
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if process.poll() is not None: raise RuntimeError('Native player exited before connection')
                status = control('status')
                if status.get('connected') is True: break
                time.sleep(2)
            else: raise RuntimeError('Sunshine never confirmed a real stream connection')
            time.sleep(20)
            if process.poll() is not None: raise RuntimeError('Native stream ended unexpectedly')
            subprocess.run(['import', '-window', 'root', str(output / 'stream.png')], check=True)
        finally: stop(process)
    # Upstream logs decoding/rendering statistics only after real rendered frames.
    logs = (output / 'stream.log').read_text(errors='replace')
    if 'Average decoding time:' not in logs:
        raise RuntimeError('No evidence of decoded/rendered frames; inspect stream log and screenshot')
    return {'paired': True, 'hostConfirmedConnection': True, 'decodedFrames': True,
            'physicalGpu': False, 'physicalController': False, 'bazziteNetwork': False}
