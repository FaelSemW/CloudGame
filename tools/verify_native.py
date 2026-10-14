"""Real native-session smoke test in a disposable Linux CI runner, without QEMU."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

if os.environ.get('GITHUB_ACTIONS') != 'true' or os.geteuid() != 0:
    sys.exit('Disposable root CI only.')
repo = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(repo / 'deploy'))
import native_helper as native
import vm_helper
import network_setup
from smoke_stream import check

def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout.strip()

output = repo / 'build/native-evidence'
output.mkdir(parents=True, exist_ok=True)
if Path('/opt/cloud-game').exists() or Path('/var/lib/cloudgame').exists():
    raise RuntimeError('Refuse an existing HOST; disposable clean runner required')
shutil.copytree(repo / 'deploy', '/opt/cloud-game/deploy')
run('useradd', '--system', '--home-dir', '/nonexistent', '--shell', '/usr/sbin/nologin', 'cloud-game-player')
Path('/etc/cloud-game').mkdir(mode=0o755)
Path('/etc/cloud-game/native.json').write_text('{"backend":"native","renderer":"software"}')
Path('/etc/cloud-game/native.json').chmod(0o600)
native.ROOT.mkdir(mode=0o751)
(native.ROOT / 'library').mkdir(mode=0o755)
native.VOL.mkdir(mode=0o751)
run('mount', '-t', 'tmpfs', '-o', 'mode=0751,size=2G,nosuid,nodev', 'tmpfs', str(native.VOL))
real_run = vm_helper.run
vm_helper.run = lambda *args, **kwargs: '100.100.1.1' if args[0] == 'tailscale' else real_run(*args, **kwargs)
# Only the reported tailnet address is supplied; stream and cleanup are real.
network_setup.setup()
sid = str(uuid.uuid4())
try:
    native.start(sid, '100.100.1.2')
    sentinel = native.VOL / sid / 'home/previous-session'
    sentinel.write_text('must disappear')
    def control(operation, pin=None):
        if operation == 'pair':
            result = native.dispatch({'op': 'pair', 'id': sid, 'pin': pin})
            return {'status': result['paired']}
        return native.status(sid)
    evidence = check(None, Path('/usr/bin/cloud-game-client'), output / 'stream',
                     control=control, host='10.77.0.2')
    native.recover()
    if sentinel.exists() or native.STATE.exists() or list(native.VOL.iterdir()):
        raise RuntimeError('Native cleanup did not finish')
    evidence.update(backend='native', virtualMachine=False, cleanupConfirmed=True,
                    bazziteValidated=False, controllerValidated=False)
    (output / 'verification.json').write_text(json.dumps(evidence, indent=2))
finally:
    result = subprocess.run(['journalctl', '-u', 'cg-native-' + sid, '--no-pager', '-o', 'cat'],
                            text=True, capture_output=True)
    (output / 'sunshine.log').write_text(result.stdout)
    if native.STATE.exists():
        native.recover()
