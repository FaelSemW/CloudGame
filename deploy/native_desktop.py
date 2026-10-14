#!/usr/bin/python3
"""Runs only inside the native player's namespaces, never on the owner's desktop."""
import os
from pathlib import Path
import subprocess
import sys
import time

HOME = Path('/home/player')
CONFIG = HOME / '.config/sunshine/sunshine.conf'


def audio_policy():
    version = subprocess.run(['wireplumber', '--version'], check=True, capture_output=True, text=True).stdout
    root = HOME / '.config/wireplumber'
    if '0.4.' in version:
        fragments = {
            'main.lua.d/89-cloud-game.lua': 'alsa_monitor.enabled = false\nv4l2_monitor.enabled = false\nlibcamera_monitor.enabled = false\ndefault_access.properties["enable-flatpak-portal"] = false\n',
            'bluetooth.lua.d/89-cloud-game.lua': 'bluez_monitor.enabled = false\n',
        }
    else:
        fragments = {'wireplumber.conf.d/90-cloud-game.conf':
            'wireplumber.profiles = { main = { hardware.audio = disabled hardware.bluetooth = disabled hardware.video-capture = disabled support.logind = disabled support.reserve-device = disabled support.portal-permissionstore = disabled } }\n'}
    for name, content in fragments.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def run_desktop(mode):
    processes = []
    try:
        if mode == 'software':
            os.environ['DISPLAY'] = ':99'
            processes.append(subprocess.Popen(['Xvfb', ':99', '-screen', '0', '1280x720x24', '-nolisten', 'tcp']))
            for attempt in range(100):
                if subprocess.run(['xdpyinfo'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                    break
                time.sleep(.1)
            else: raise RuntimeError('Display de teste não iniciou.')
            processes.append(subprocess.Popen(['openbox']))
        elif mode == 'gpu':
            # The compositor sets WAYLAND_DISPLAY and DISPLAY for this exec child.
            if not os.environ.get('WAYLAND_DISPLAY'): raise RuntimeError('Compositor Wayland ausente.')
        else: raise RuntimeError('Perfil desconhecido.')
        audio_policy()
        processes.append(subprocess.Popen(['pipewire']))
        processes.append(subprocess.Popen(['pipewire-pulse']))
        processes.append(subprocess.Popen(['wireplumber']))
        for attempt in range(100):
            if subprocess.run(['pactl', 'info'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                break
            time.sleep(.1)
        else: raise RuntimeError('Áudio temporário não iniciou.')
        subprocess.run(['pactl', 'load-module', 'module-null-sink', 'sink_name=cloudgame'], check=True)
        for attempt in range(100):
            if subprocess.run(['pactl', 'set-default-sink', 'cloudgame'], stderr=subprocess.DEVNULL).returncode == 0:
                break
            time.sleep(.1)
        else: raise RuntimeError('Política de áudio temporário não iniciou.')
        subprocess.run(['pactl', 'set-default-source', 'cloudgame.monitor'], check=True)
        password = (HOME / '.sunshine-bootstrap').read_text()
        credentials = subprocess.run(['sunshine', str(CONFIG), '--creds', 'cloudgame', password], capture_output=True)
        if credentials.returncode: raise RuntimeError('Falha ao preparar a credencial temporária Sunshine.')
        (HOME / '.sunshine-bootstrap').unlink()
        processes.append(subprocess.Popen(['steam', '-gamepadui']))
        sunshine = subprocess.Popen(['sunshine', str(CONFIG)])
        processes.append(sunshine)
        return sunshine.wait()
    finally:
        for process in reversed(processes):
            if process.poll() is None: process.terminate()
        for process in reversed(processes):
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired: process.kill(); process.wait()


if __name__ == '__main__':
    mode = sys.argv[1]
    if not os.environ.get('DBUS_SESSION_BUS_ADDRESS'):
        os.execvp('dbus-run-session', ['dbus-run-session', '--', '/usr/bin/python3', __file__, mode])
    if mode == 'gpu' and not os.environ.get('WAYLAND_DISPLAY'):
        config = HOME / 'sway.conf'
        config.write_text('output HEADLESS-1 mode 1920x1080@60Hz\n'
                          'xwayland force\n'
                          'exec /usr/bin/python3 /opt/cloud-game/deploy/native_desktop.py gpu\n')
        os.environ.update(WLR_BACKENDS='headless', WLR_HEADLESS_OUTPUTS='1', WLR_LIBINPUT_NO_DEVICES='1')
        nodes = sorted(Path('/dev/dri').glob('renderD*'))
        if not nodes: raise RuntimeError('Render node ausente.')
        os.environ['WLR_RENDER_DRM_DEVICE'] = str(nodes[0])
        os.execvp('dbus-run-session', ['dbus-run-session', '--', 'sway', '--config', str(config)])
    else:
        sys.exit(run_desktop(mode))
