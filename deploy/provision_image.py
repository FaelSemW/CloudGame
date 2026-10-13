#!/usr/bin/env python3
"""Only for the new locked Ubuntu guest created by build_image.py."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import subprocess
import urllib.request

HERE = Path(__file__).resolve().parent


def run(*args):
    return subprocess.run(args, check=True, env=dict(os.environ, DEBIAN_FRONTEND='noninteractive'))


def put(path, text, mode=0o644):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text); path.chmod(mode)


def main():
    if os.geteuid() != 0 or 'VERSION_ID="24.04"' not in Path('/etc/os-release').read_text():
        raise RuntimeError('Expected fresh Ubuntu 24.04 guest')
    if not Path('/sys/class/dmi/id/product_serial').read_text().strip().startswith('ds=nocloud;s=http://10.0.2.2:'):
        raise RuntimeError('Expected dedicated CloudGame image-builder VM')
    player = pwd.getpwnam('player')
    if player.pw_uid != 1000 or Path('/var/lib/cloudgame-image-ready').exists():
        raise RuntimeError('Refusing to provision a previously configured image')
    run('dpkg', '--add-architecture', 'i386')
    run('apt-get', 'update')
    run('apt-get', 'install', '-y', '--no-install-recommends', 'xfce4', 'xorg', 'lightdm',
        'dbus-x11', 'pulseaudio', 'qemu-guest-agent', 'curl', 'ca-certificates',
        'mesa-va-drivers', 'mesa-vulkan-drivers', 'libgl1-mesa-dri', 'linux-firmware',
        'linux-generic', 'steam-installer')
    lock = json.loads((HERE / 'image-lock.json').read_text())['sunshine']
    package = Path('/var/tmp/cloudgame-sunshine.deb')
    # curl refuses HTTPS-to-HTTP redirects; the fixed upstream checksum is mandatory.
    run('curl', '--fail', '--location', '--proto', '=https', '--proto-redir', '=https',
        '--output', str(package), lock['url'])
    with package.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != lock['sha256']:
            raise RuntimeError('Sunshine checksum mismatch')
    run('apt-get', 'install', '-y', str(package))
    package.unlink()
    put('/etc/lightdm/lightdm.conf.d/90-cloudgame.conf',
        '[Seat:*]\nautologin-user=player\nautologin-user-timeout=0\nuser-session=xfce\nxserver-command=X -nolisten tcp\n')
    # Player cannot use polkit to alter machine policy, accounts or packages.
    put('/etc/polkit-1/rules.d/00-cloudgame-player.rules',
        'polkit.addRule(function(action, subject) { if (subject.user == "player") return polkit.Result.NO; });\n')
    run('passwd', '-l', 'root')
    run('systemctl', 'mask', 'ssh.service', 'ssh.socket')
    run('systemctl', 'set-default', 'graphical.target')
    run('python3', str(HERE / 'prepare_guest.py'))
    # Disable upstream user autostart; only our system-managed instance may run.
    put('/etc/systemd/user/sunshine.service', '[Unit]\nDescription=Disabled; managed by CloudGame system service\nRefuseManualStart=yes\n')
    for conf in Path('/etc/netplan').glob('*.yaml'):
        conf.unlink()  # Inside the newly created guest, never the HOST.
    put('/etc/netplan/90-cloudgame.yaml', 'network:\n  version: 2\n  ethernets:\n    game:\n      match:\n        macaddress: "52:54:00:77:00:02"\n      dhcp4: false\n      dhcp6: false\n      addresses: [10.77.0.2/24]\n      routes:\n        - to: default\n          via: 10.77.0.1\n      nameservers:\n        addresses: [1.1.1.1]\n', 0o600)
    put('/etc/sysctl.d/90-cloudgame-ipv6.conf', 'net.ipv6.conf.all.disable_ipv6=1\nnet.ipv6.conf.default.disable_ipv6=1\n')
    put('/etc/cloud/cloud-init.disabled', '')
    run('systemctl', 'stop', 'cloud-game-sunshine.service', 'lightdm.service')
    run('apt-get', 'clean')
    packages = subprocess.check_output(['dpkg-query', '-W', '-f=${Package}\t${Version}\n'], text=True)
    put('/var/lib/cloudgame-image-packages.txt', packages)
    put('/var/lib/cloudgame-image-ready', json.dumps({'sunshine': lock, 'hardwareValidated': False}))
    run('sync')
    with open('/dev/ttyS0', 'w') as console:
        console.write('CLOUDGAME_IMAGE_PROVISIONED_V1\n')


if __name__ == '__main__':
    main()
