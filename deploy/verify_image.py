#!/usr/bin/env python3
"""Boot a disposable overlay and verify the actual guest agent/Sunshine contract."""
import argparse
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import time


def agent(path, operation, arguments=None):
    request = {'execute': operation}
    if arguments is not None: request['arguments'] = arguments
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(5)
        connection.connect(str(path))
        connection.sendall((json.dumps(request) + '\n').encode())
        with connection.makefile('rb') as stream:
            reply = json.loads(stream.readline(1024 * 1024))
    if 'error' in reply: raise RuntimeError(str(reply['error']))
    return reply['return']


def execute(channel, path, args, input_data=None):
    arguments = {'path': path, 'arg': args, 'capture-output': True}
    if input_data is not None:
        arguments['input-data'] = base64.b64encode(input_data.encode()).decode()
    pid = agent(channel, 'guest-exec', arguments)['pid']
    for _ in range(60):
        result = agent(channel, 'guest-exec-status', {'pid': pid})
        if result.get('exited'):
            out = base64.b64decode(result.get('out-data', '')).decode(errors='replace')
            err = base64.b64decode(result.get('err-data', '')).decode(errors='replace')
            if result.get('exitcode') or result.get('out-truncated'):
                raise RuntimeError('Guest check failed: ' + err[:1500])
            return out
        time.sleep(0.5)
    raise RuntimeError('Guest command did not finish')


def verify(image, directory, timeout=300, client=None):
    image = image.resolve(); directory = directory.resolve()
    directory.mkdir(parents=True, mode=0o700, exist_ok=False)
    if ',' in str(directory) or len(str(directory / 'agent.sock')) >= 104:
        raise RuntimeError('Use a short verification path without commas')
    overlay = directory / 'test.qcow2'; channel = directory / 'agent.sock'
    subprocess.run(['qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(image), str(overlay)], check=True)
    accelerated = os.access('/dev/kvm', os.R_OK | os.W_OK)
    net = 'user,id=network,net=10.77.0.0/24,host=10.77.0.1'
    if client:
        if os.environ.get('GITHUB_ACTIONS') != 'true': raise RuntimeError('Client transport test is CI-only')
        for protocol, ports in [('tcp', (47984, 47989, 48010)), ('udp', (47998, 47999, 48000, 48002, 48010))]:
            for port in ports: net += f',hostfwd={protocol}:127.0.0.1:{port}-10.77.0.2:{port}'
    command = ['qemu-system-x86_64', '-machine', 'q35', '-accel', 'kvm' if accelerated else 'tcg',
        '-cpu', 'host' if accelerated else 'max', '-m', '4096', '-smp', '2', '-display', 'none',
        '-serial', 'stdio', '-monitor', 'none', '-no-reboot',
        '-drive', f'file={overlay},format=qcow2,if=virtio',
        '-netdev', net,
        '-device', 'virtio-net-pci,netdev=network,mac=52:54:00:77:00:02',
        '-device', 'virtio-serial-pci', '-chardev', f'socket,path={channel},server=on,wait=off,id=agent',
        '-device', 'virtserialport,chardev=agent,name=org.qemu.guest_agent.0',
        '-audiodev', 'none,id=audio', '-device', 'ich9-intel-hda', '-device', 'hda-duplex,audiodev=audio']
    last = 'Guest has not booted'
    with (directory / 'boot.log').open('wb') as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if process.poll() is not None: raise RuntimeError('Verification VM exited unexpectedly')
                try:
                    status = json.loads(execute(channel, '/usr/local/libexec/cloud-game-guest', ['status']))
                    if status.get('ready') is not True or status.get('connected') is not False:
                        raise RuntimeError('Sunshine not ready or contains an unexpected client')
                    checks = execute(channel, '/usr/bin/python3', ['-c',
                        'import pwd,grp,pathlib; p=pwd.getpwnam("player"); assert p.pw_uid==1000; '
                        'g={x.gr_name for x in grp.getgrall() if "player" in x.gr_mem or x.gr_gid==p.pw_gid}; '
                        'assert not g & {"sudo","wheel","docker","libvirt","disk","lxd"}; '
                        'assert not pathlib.Path("/home/player/.steam").exists(); '
                        'assert not pathlib.Path("/home/player/.cloudgame-session-check").exists(); '
                        'assert pathlib.Path("/var/lib/cloudgame-image-ready").is_file(); '
                        'assert not any(x in {"9p","virtiofs","nfs","cifs"} for x in '
                        '[line.split()[2] for line in pathlib.Path("/proc/mounts").read_text().splitlines()]); '
                        'print("guest account and mount checks passed")'])
                    break
                except (OSError, RuntimeError, ValueError, KeyError) as error:
                    if last != str(error): print('Waiting for guest: ' + str(error), flush=True)
                    last = str(error)
                    time.sleep(2)
            else:
                # Service log excludes credential command arguments, which the
                # provisioner captures privately rather than journaling.
                try:
                    diagnostic = execute(channel, '/usr/bin/journalctl', ['-u', 'cloud-game-sunshine', '-b', '--no-pager', '-n', '80'])
                    (directory / 'sunshine.log').write_text(diagnostic)
                    diagnostic = execute(channel, '/usr/bin/python3', ['-c',
                        'import runpy\nm=runpy.run_path("/usr/local/libexec/cloud-game-guest")\n'
                        'for path in ("/api/apps", "/api/pin"):\n'
                        ' try: print(path, sorted(m["api"](path).keys()))\n'
                        ' except Exception as e: print(path, type(e).__name__, str(e))\n'])
                    (directory / 'api-diagnostic.log').write_text(diagnostic)
                    diagnostic = execute(channel, '/usr/bin/python3', ['-c',
                        'import pathlib,subprocess\n'
                        'print(subprocess.check_output(["journalctl", "-u", "lightdm", "-b", "--no-pager"], text=True))\n'
                        'for name in ("/var/log/lightdm/lightdm.log", "/var/log/lightdm/x-0.log", "/var/log/Xorg.0.log"):\n'
                        ' p=pathlib.Path(name)\n'
                        ' if p.is_file(): print(name, p.read_text()[-30000:])\n'])
                    (directory / 'display-diagnostic.log').write_text(diagnostic)
                except Exception:
                    pass
                raise RuntimeError('Guest verification failed: ' + last)
            transport = None
            if client:
                execute(channel, '/usr/bin/python3', ['-c',
                    'from pathlib import Path; Path("/home/player/.cloudgame-session-check").write_text("discard this session")'])
                import sys
                sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
                from smoke_stream import check
                transport = check(channel, client.resolve(), directory / 'stream')
            (directory / 'verification.json').write_text(json.dumps({
                'sunshine': status, 'guestChecks': checks.strip(),
                'realStreamValidated': transport is not None, 'transport': transport,
                'physicalGpuValidated': False}, indent=2))
        finally:
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=10)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
    # Remove only our generated disposable disk after QEMU is confirmed stopped.
    overlay.unlink()
    print('Second boot, Sunshine API and guest isolation checks passed; streaming remains unverified.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image', type=Path); parser.add_argument('directory', type=Path)
    parser.add_argument('--timeout', type=int, default=300)
    parser.add_argument('--client', type=Path, help='CI-only native transport verification')
    args = parser.parse_args()
    verify(args.image, args.directory, args.timeout, args.client)
    if args.client:
        # A new boot must not retain a file written during the previous real stream.
        cleanup = args.directory.with_name(args.directory.name + '-clean')
        verify(args.image, cleanup, args.timeout)
        evidence = args.directory / 'verification.json'
        value = json.loads(evidence.read_text())
        value['discardedSessionFileAbsentOnNextBoot'] = True
        evidence.write_text(json.dumps(value, indent=2))
