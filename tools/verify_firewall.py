"""Real nftables/conntrack regression test, confined to disposable CI namespaces."""
import os
from pathlib import Path
import select
import subprocess
import sys
import uuid

if os.environ.get('GITHUB_ACTIONS') != 'true' or os.geteuid() != 0:
    sys.exit('Run only as root in disposable Linux CI.')
if sys.argv[1:] != ['--isolated']:
    sys.exit(subprocess.call(['unshare', '--net', sys.executable, __file__, '--isolated']))

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deploy'))
import vm_helper
import network_setup


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout.strip()


real_run = vm_helper.run
vm_helper.run = lambda *args, **kwargs: '100.100.1.1' if args[0] == 'tailscale' else real_run(*args, **kwargs)
names = ['cg-test-' + uuid.uuid4().hex[:10] for _ in range(2)]
created = []; processes = []
try:
    for name in names:
        run('ip', 'netns', 'add', name); created.append(name)
        run('ip', '-n', name, 'link', 'set', 'lo', 'up')
    guest, peer = names
    # This namespace has no firewalld daemon. Exercise the actual bridge setup;
    # firewalld coexistence must be validated separately on the target HOST.
    network_setup.firewall_plan = lambda: []
    network_setup.setup()
    network_setup.setup()  # An owned bridge is reusable without replacing it.
    for interface, remote, namespace, address in [('cgport', 'eth0', guest, '10.77.0.2/24'), ('tailscale0', 'eth0', peer, '100.100.1.2/24')]:
        run('ip', 'link', 'add', interface, 'type', 'veth', 'peer', 'name', 'cgremote')
        run('ip', 'link', 'set', 'cgremote', 'netns', namespace)
        run('ip', '-n', namespace, 'link', 'set', 'cgremote', 'name', remote)
        run('ip', '-n', namespace, 'addr', 'add', address, 'dev', remote)
        run('ip', '-n', namespace, 'link', 'set', remote, 'up')
        run('ip', 'link', 'set', interface, 'up')
    run('ip', 'link', 'set', 'cgport', 'master', 'cgbr0')
    run('ip', 'addr', 'add', '100.100.1.1/24', 'dev', 'tailscale0')
    run('ip', '-n', guest, 'route', 'add', 'default', 'via', '10.77.0.1')
    run('ip', '-n', peer, 'addr', 'add', '100.100.1.3/24', 'dev', 'eth0')
    Path('/proc/sys/net/ipv4/ip_forward').write_text('1')
    server = subprocess.Popen(['ip', 'netns', 'exec', guest, sys.executable, '-u', '-c',
        'import socket; s=socket.socket(); s.bind(("10.77.0.2",47989)); s.listen(); print("ready",flush=True); '
        'c,a=s.accept();\nwhile True:\n d=c.recv(1024)\n if not d: break\n c.sendall(d)'], stdout=subprocess.PIPE, text=True)
    processes.append(server)
    if not select.select([server.stdout], [], [], 5)[0] or server.stdout.readline().strip() != 'ready':
        raise RuntimeError('Guest test listener failed')
    vm_helper.network('100.100.1.2')
    client = subprocess.Popen(['ip', 'netns', 'exec', peer, sys.executable, '-u', '-c',
        'import socket,sys; s=socket.socket(); s.settimeout(3); s.bind(("100.100.1.2",0)); '
        's.connect(("100.100.1.1",47989)); s.sendall(b"first"); assert s.recv(5)==b"first"; '
        'print("connected",flush=True); sys.stdin.readline(); s.sendall(b"stale");\n'
        'try: s.recv(5)\nexcept socket.timeout: sys.exit(0)\n'
        'raise RuntimeError("Previous player retained access after reservation changed")'],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    processes.append(client)
    if not select.select([client.stdout], [], [], 8)[0] or client.stdout.readline().strip() != 'connected':
        raise RuntimeError('Authorized peer could not reach guest')
    vm_helper.network()  # Cleanup closes all traffic.
    vm_helper.network('100.100.1.3')  # Conntrack still exists, but the player changed.
    client.stdin.write('continue\n'); client.stdin.flush()
    _, error = client.communicate(timeout=8)
    if client.returncode: raise RuntimeError(error)
    vm_helper.network()
    print('Actual nftables forwarding passed; old connected peer is blocked after reassignment.')
finally:
    for process in processes:
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=3)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
    for name in reversed(created):
        subprocess.run(['ip', 'netns', 'delete', name], check=True)
