#!/usr/bin/env python3
"""Build a fresh disposable-game base locally from verified upstream downloads.

No mounts of guest filesystems, SSH passwords, shared owner folders or public
provisioning ports. Package installation runs only inside the new QEMU guest.
"""
import argparse
import hashlib
import http.server
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import threading
import urllib.request

HERE = Path(__file__).resolve().parent
LOCK = json.loads((HERE / 'image-lock.json').read_text())
MARKER = 'CLOUDGAME_IMAGE_PROVISIONED_V1'


class HttpsOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith('https://'):
            raise RuntimeError('Non-HTTPS download redirect refused')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download(url, digest, path):
    if not url.startswith('https://'):
        raise RuntimeError('HTTPS download required')
    sha = hashlib.sha256()
    with urllib.request.build_opener(HttpsOnly()).open(url, timeout=60) as response, path.open('xb') as target:
        while block := response.read(1024 * 1024):
            sha.update(block)
            target.write(block)
    if sha.hexdigest() != digest:
        raise RuntimeError('Upstream download checksum mismatch: ' + path.name)


def configuration():
    files = []
    for name in ('provision_image.py', 'prepare_guest.py', 'cloud-game-guest',
                 'cloud-game-sunshine.service', 'sunshine.conf', 'apps.json', 'image-lock.json'):
        files.append({'path': '/opt/cloud-game-image/' + name, 'permissions': '0600',
                      'owner': 'root:root', 'content': (HERE / name).read_text(encoding='utf-8')})
    return {
        'users': [{'name': 'player', 'uid': 1000, 'shell': '/bin/bash',
                   'lock_passwd': True, 'groups': ['audio', 'video'], 'sudo': False}],
        'disable_root': True, 'ssh_pwauth': False,
        'write_files': files,
        'runcmd': [['sh', '-c', 'python3 /opt/cloud-game-image/provision_image.py; systemctl poweroff']],
        'final_message': 'CloudGame image preparation finished; success requires the explicit provision marker.'
    }


def build(destination, timeout=2400):
    destination = destination.resolve()
    if os.name != 'posix':
        raise RuntimeError('Build the image on Linux (HOST or CI), not Windows.')
    for command in ('qemu-system-x86_64', 'qemu-img'):
        if not shutil.which(command):
            raise RuntimeError('Missing virtualization tool: ' + command)
    if ',' in str(destination):
        raise RuntimeError('QEMU build path must not contain commas')
    # A fresh directory is mandatory. Never convert or overwrite an owner's disk.
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    image = destination / 'base.qcow2'
    origin = destination / 'ubuntu.img'
    print('Downloading and verifying the clean Ubuntu image...', flush=True)
    download(LOCK['ubuntu']['url'], LOCK['ubuntu']['sha256'], origin)
    subprocess.run(['qemu-img', 'convert', '-f', 'qcow2', '-O', 'qcow2', str(origin), str(image)], check=True)
    subprocess.run(['qemu-img', 'resize', str(image), '128G'], check=True)
    token = secrets.token_hex(24)
    payloads = {
        f'/{token}/user-data': ('#cloud-config\n' + json.dumps(configuration())).encode(),
        f'/{token}/meta-data': json.dumps({'instance-id': 'cloudgame-build-' + token,
                                          'local-hostname': 'cloudgame-player'}).encode(),
        f'/{token}/vendor-data': b'',
        f'/{token}/network-config': json.dumps({'version': 2, 'ethernets': {'guest': {
            'match': {'macaddress': '52:54:00:77:00:02'}, 'dhcp4': True}}}).encode()
    }

    class Seed(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            data = payloads.get(self.path)
            if data is None:
                self.send_error(404); return
            self.send_response(200)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers(); self.wfile.write(data)

        def log_message(self, *_):
            pass

    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Seed)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    accelerated = os.access('/dev/kvm', os.R_OK | os.W_OK)
    command = ['qemu-system-x86_64', '-machine', 'q35', '-accel', 'kvm' if accelerated else 'tcg',
        '-cpu', 'host' if accelerated else 'max', '-m', '4096', '-smp', '2',
        '-drive', f'file={image},format=qcow2,if=virtio', '-display', 'none',
        '-serial', 'stdio', '-monitor', 'none', '-no-reboot',
        '-netdev', 'user,id=network', '-device', 'virtio-net-pci,netdev=network,mac=52:54:00:77:00:02',
        '-smbios', f'type=1,serial=ds=nocloud;s=http://10.0.2.2:{server.server_port}/{token}/']
    print('Provisioning isolated guest; detailed output: ' + str(destination / 'provision.log'), flush=True)
    try:
        with (destination / 'provision.log').open('wb') as log:
            process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
            try:
                if process.wait(timeout=timeout):
                    raise RuntimeError('QEMU image preparation failed; inspect provision.log')
            finally:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=10)
                    except subprocess.TimeoutExpired: process.kill(); process.wait()
    finally:
        server.shutdown(); server.server_close(); thread.join()
    if MARKER not in (destination / 'provision.log').read_text(errors='replace').splitlines():
        # Serial console can include CR and kernel prefixes; marker is emitted
        # explicitly by the provisioner after every check, never by cloud-init data.
        lines = (destination / 'provision.log').read_text(errors='replace').splitlines()
        if not any(line.strip() == MARKER for line in lines):
            raise RuntimeError('Guest did not confirm image completion; base remains unapproved')
    subprocess.run(['qemu-img', 'check', str(image)], check=True)
    info = json.loads(subprocess.check_output(['qemu-img', 'info', '--output=json', str(image)]))
    if info.get('backing-filename') or info.get('format') != 'qcow2':
        raise RuntimeError('Expected standalone qcow2 image')
    evidence = {'upstream': LOCK, 'buildAcceleration': 'kvm' if accelerated else 'tcg',
                'provisioned': True, 'hardwareStreamingValidated': False,
                'templateReviewed': False, 'image': image.name}
    (destination / 'image-build.json').write_text(json.dumps(evidence, indent=2))
    image.chmod(0o444)
    origin.unlink()  # Only the exact downloaded file in this newly created directory.
    print('Image provisioned. GPU streaming and template review are still required.', flush=True)
    return image


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--timeout', type=int, default=2400)
    args = parser.parse_args()
    build(args.destination, args.timeout)
