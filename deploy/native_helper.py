#!/usr/bin/python3
"""Native Linux session: bubblewrap namespaces, host libraries and GPU render nodes."""
import base64
import fcntl
import grp
import json
import os
from pathlib import Path
import pwd
import re
import secrets
import shutil
import ssl
import sys
import time
import urllib.request
from vm_helper import run, trusted, valid_id, peer_ip, network, assert_memory_only_swap

ROOT = Path('/var/lib/cloudgame')
VOL = ROOT / 'native-volatile'
STATE = ROOT / 'native-session.json'
CONFIG = Path('/etc/cloud-game/native.json')
NS = 'cg-native'
LINK = 'cg-native-host'
ACCOUNT = 'cloud-game-player'


def config():
    trusted(CONFIG.parent, True); trusted(CONFIG)
    value = json.loads(CONFIG.read_text())
    if value.get('backend') != 'native' or value.get('renderer') not in ('gpu', 'software'):
        raise RuntimeError('Configuração nativa inválida.')
    return value


def doctor():
    c = config()
    for command in ('bwrap', 'sunshine', 'steam', 'pipewire', 'pipewire-pulse', 'wireplumber', 'ip', 'nft', 'systemd-run'):
        if not shutil.which(command): raise RuntimeError('Componente nativo ausente: ' + command)
    if not shutil.which('Xvfb' if c['renderer'] == 'software' else 'sway'):
        raise RuntimeError('Compositor nativo ausente.')
    if c['renderer'] == 'gpu' and not list(Path('/dev/dri').glob('renderD*')):
        raise RuntimeError('Nenhum render node da GPU disponível.')
    assert_memory_only_swap()
    trusted(ROOT / 'library', True)
    volatile_mount()
    if (ROOT / 'runtime.json').exists():
        raise RuntimeError('Existe uma sessão do backend VM antigo; encerre-a antes de migrar.')
    return {'ok': True, 'profile': 'software' if c['renderer'] == 'software' else 'native',
            'isolation': 'Linux namespaces + usuário dedicado + cgroup + tmpfs', 'backend': 'native',
            'input': ['keyboard-x11', 'mouse-x11'], 'gamepad': False}


def volatile_mount():
    trusted(VOL, True)
    mounts = [line.split() for line in Path('/proc/mounts').read_text().splitlines()]
    if not any(fields[1] == str(VOL) and fields[2] == 'tmpfs' for fields in mounts):
        raise RuntimeError('Diretório temporário precisa ser um mount tmpfs exclusivo.')


def write_state(value):
    with open(ROOT / 'native-session.new', 'w', opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW, 0o600)) as stream:
        json.dump(value, stream); stream.flush(); os.fsync(stream.fileno())
    os.replace(ROOT / 'native-session.new', STATE)


def state(sid=None):
    trusted(STATE)
    value = json.loads(STATE.read_text())
    valid_id(value['id'])
    if sid is not None and valid_id(sid) != value['id']: raise RuntimeError('Sessão diferente.')
    return value


def sandbox(directory, c, account):
    """No host home, /run, /var, system bus, primary DRM nodes or host PID view."""
    args = ['bwrap', '--unshare-user', '--unshare-pid', '--unshare-ipc', '--unshare-uts',
            '--unshare-cgroup-try', '--die-with-parent', '--new-session',
            '--ro-bind', '/usr', '/usr', '--symlink', 'usr/bin', '/bin',
            '--symlink', 'usr/sbin', '/sbin', '--symlink', 'usr/lib', '/lib',
            '--symlink', 'usr/lib64', '/lib64', '--proc', '/proc', '--dev', '/dev',
            '--tmpfs', '/tmp', '--tmpfs', '/dev/shm', '--tmpfs', '/var', '--dir', '/etc', '--dir', '/run',
            '--dir', '/run/user', '--bind', str(directory / 'runtime'), '/run/user/' + str(account.pw_uid),
            '--bind', str(directory / 'home'), '/home/player',
            '--ro-bind', '/opt/cloud-game', '/opt/cloud-game',
            '--ro-bind', str(ROOT / 'library'), '/games',
            '--ro-bind', str(directory / 'passwd'), '/etc/passwd',
            '--ro-bind', str(directory / 'group'), '/etc/group',
            '--ro-bind', str(directory / 'resolv.conf'), '/etc/resolv.conf',
            '--ro-bind', str(directory / 'machine-id'), '/etc/machine-id']
    for path in ('/etc/ssl', '/etc/pki', '/etc/fonts', '/etc/ld.so.cache', '/etc/alternatives',
                 '/etc/nsswitch.conf', '/etc/hosts', '/etc/drirc', '/etc/steam',
                 '/sys/devices', '/sys/dev/char', '/sys/class/drm'):
        if Path(path).exists(): args += ['--ro-bind', path, path]
    for node in sorted(Path('/dev/dri').glob('renderD*')):
        args += ['--dev-bind', str(node), str(node)]
    args += ['--clearenv', '--setenv', 'PATH', '/usr/bin:/bin',
             '--setenv', 'HOME', '/home/player', '--setenv', 'USER', ACCOUNT,
             '--setenv', 'LOGNAME', ACCOUNT, '--setenv', 'LANG', 'C.UTF-8',
             '--setenv', 'SDL_VIDEODRIVER', 'x11', '--setenv', 'GDK_BACKEND', 'x11',
             '--setenv', 'QT_QPA_PLATFORM', 'xcb',
             '--setenv', 'XDG_RUNTIME_DIR', '/run/user/' + str(account.pw_uid),
             '--chdir', '/home/player', '/usr/bin/python3',
             '/opt/cloud-game/deploy/native_desktop.py', c['renderer']]
    return args


def api(value, path, body=None):
    directory = VOL / value['id']
    certificate = directory / 'home/.config/sunshine/credentials/cacert.pem'
    context = ssl.create_default_context(cafile=str(certificate))
    context.check_hostname = False
    auth = base64.b64encode(('cloudgame:' + value['password']).encode()).decode()
    request = urllib.request.Request('https://10.77.0.2:47990' + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={'Authorization': 'Basic ' + auth, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(request, context=context, timeout=35 if body else 3) as response:
        return json.load(response)


def status(sid):
    value = state(sid)
    unit = 'cg-native-' + value['id'] + '.service'
    if run('systemctl', 'show', '-p', 'ActiveState', '--value', unit) != 'active':
        return {'ready': False, 'connected': False}
    invocation = run('systemctl', 'show', '-p', 'InvocationID', '--value', unit)
    if not re.fullmatch('[a-f0-9]{32}', invocation): raise RuntimeError('Invocação inválida.')
    lines = run('journalctl', '--no-pager', '-o', 'cat', '_SYSTEMD_INVOCATION_ID=' + invocation)
    apps = api(value, '/api/apps')
    ready = 'Found H.264 encoder:' in lines and any(a.get('name') == 'Desktop' for a in apps.get('apps', []))
    connected = 0
    for line in lines.splitlines():
        if 'CLIENT CONNECTED' in line: connected += 1
        if 'CLIENT DISCONNECTED' in line: connected = max(0, connected - 1)
    if connected > 1: raise RuntimeError('Mais de um cliente conectado.')
    return {'ready': ready, 'connected': ready and connected == 1}


def start(sid, peer):
    valid_id(sid); peer = peer_ip(peer); doctor()
    if STATE.exists() or list(VOL.iterdir()): raise RuntimeError('Sessão anterior não descartada.')
    if NS in [line.split()[0] for line in run('ip', 'netns', 'list').splitlines()]:
        raise RuntimeError('Namespace existente preservado.')
    if Path('/sys/class/net/' + LINK).exists(): raise RuntimeError('Interface existente preservada.')
    account = pwd.getpwnam(ACCOUNT)
    directory = VOL / sid
    directory.mkdir(mode=0o755)
    directory.chmod(0o751)
    for name in ('home', 'runtime'):
        target = directory / name; target.mkdir(mode=0o700); os.chown(target, account.pw_uid, account.pw_gid)
    (directory / 'passwd').write_text(f'{ACCOUNT}:x:{account.pw_uid}:{account.pw_gid}::/home/player:/usr/bin/bash\n')
    (directory / 'group').write_text(f'{ACCOUNT}:x:{account.pw_gid}:\n')
    (directory / 'resolv.conf').write_text('nameserver 1.1.1.1\nnameserver 9.9.9.9\n')
    (directory / 'machine-id').write_text(secrets.token_hex(16) + '\n')
    for name in ('passwd', 'group', 'resolv.conf', 'machine-id'): (directory / name).chmod(0o644)
    value = {'id': sid, 'peer': peer, 'password': secrets.token_urlsafe(32), 'paired': False,
             'expires': time.time() + 6 * 3600}
    write_state(value)
    network()
    run('ip', 'netns', 'add', NS)
    run('ip', 'link', 'add', LINK, 'type', 'veth', 'peer', 'name', 'cg-native-peer')
    run('ip', 'link', 'set', 'cg-native-peer', 'netns', NS)
    run('ip', 'link', 'set', LINK, 'master', 'cgbr0')
    run('ip', 'link', 'set', LINK, 'up')
    run('ip', '-n', NS, 'link', 'set', 'lo', 'up')
    run('ip', '-n', NS, 'address', 'add', '10.77.0.2/24', 'dev', 'cg-native-peer')
    run('ip', '-n', NS, 'link', 'set', 'cg-native-peer', 'up')
    run('ip', '-n', NS, 'route', 'add', 'default', 'via', '10.77.0.1')
    # Allow only the reserved player and public egress; management stays separate.
    network(peer)
    settings = directory / 'home/.config/sunshine'
    settings.mkdir(parents=True)
    shutil.copyfile('/opt/cloud-game/deploy/apps.json', settings / 'apps.json')
    (settings / 'sunshine.conf').write_text(
        'sunshine_name = Cloud Game\nupnp = disabled\naddress_family = ipv4\norigin_web_ui_allowed = lan\n'
        'controller = disabled\n'
        'capture = ' + ('x11' if config()['renderer'] == 'software' else 'wlr') + '\n'
        'file_apps = /home/player/.config/sunshine/apps.json\n'
        'file_state = /home/player/.config/sunshine/sunshine_state.json\n')
    # Temporary credentials are passed in a private file, never a command line.
    (directory / 'home/.sunshine-bootstrap').write_text(value['password'])
    for path in (directory / 'home').rglob('*'): os.chown(path, account.pw_uid, account.pw_gid)
    os.chmod(directory / 'home/.sunshine-bootstrap', 0o600)
    groups = sorted({Path(node).stat().st_gid for node in Path('/dev/dri').glob('renderD*')})
    drop = ['setpriv', '--reuid=' + str(account.pw_uid), '--regid=' + str(account.pw_gid),
            '--groups=' + ','.join(map(str, groups))] if groups else [
            'setpriv', '--reuid=' + str(account.pw_uid), '--regid=' + str(account.pw_gid), '--clear-groups']
    drop += ['--no-new-privs', '--bounding-set=-all', '--inh-caps=-all']
    run('systemd-run', '--unit=cg-native-' + sid, '--service-type=exec',
        '--property=KillMode=control-group', '--property=TimeoutStopSec=15',
        '--property=Delegate=no', '--property=Restart=no',
        'ip', 'netns', 'exec', NS, *drop, *sandbox(directory, config(), account))
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            if status(sid)['ready']: return {'ready': True}
        except (OSError, ValueError): pass
        time.sleep(1)
    raise RuntimeError('Sunshine nativo não confirmou captura/encoder. Consulte o journal da sessão.')


def recover():
    network()
    volatile_mount()
    if not STATE.exists():
        if list(VOL.iterdir()): raise RuntimeError('Dados sem estado: revisão administrativa necessária.')
        if Path('/sys/class/net/' + LINK).exists() or NS in [line.split()[0] for line in run('ip', 'netns', 'list').splitlines()]:
            raise RuntimeError('Rede sem estado registrado; revisão administrativa necessária.')
        return {'clean': True}
    value = state(); sid = value['id']; unit = 'cg-native-' + sid + '.service'
    active = run('systemctl', 'show', '-p', 'ActiveState', '--value', unit)
    if active not in ('inactive', 'failed', ''):
        run('systemctl', 'stop', unit)
    cgroup = run('systemctl', 'show', '-p', 'ControlGroup', '--value', unit)
    if cgroup:
        if not cgroup.startswith('/system.slice/cg-native-'): raise RuntimeError('Cgroup inesperado.')
        directory = Path('/sys/fs/cgroup') / cgroup.lstrip('/')
        if directory.exists() and any(p.read_text().strip() for p in directory.rglob('cgroup.procs')):
            raise RuntimeError('Processos da sessão ainda ativos.')
    namespaces = [line.split()[0] for line in run('ip', 'netns', 'list').splitlines()]
    if NS in namespaces:
        if run('ip', 'netns', 'pids', NS): raise RuntimeError('Processos ainda ligados ao namespace.')
        run('ip', 'netns', 'delete', NS)
    if Path('/sys/class/net/' + LINK).exists():
        try: run('ip', 'link', 'delete', LINK)
        except RuntimeError:
            # Deleting a netns asynchronously removes its veth peer too.
            if Path('/sys/class/net/' + LINK).exists(): raise
    target = VOL / sid
    if target.is_symlink(): raise RuntimeError('Diretório temporário inválido.')
    if not shutil.rmtree.avoids_symlink_attacks: raise RuntimeError('Limpeza segura indisponível.')
    if target.exists(): shutil.rmtree(target)
    if list(VOL.iterdir()): raise RuntimeError('Ambiente temporário não ficou vazio.')
    STATE.unlink()
    return {'clean': True}


def dispatch(request):
    op = request.get('op')
    if op == 'doctor': return doctor()
    if op == 'recover': return recover()
    if op == 'start': return start(request.get('id'), request.get('peer'))
    if op == 'stop':
        if STATE.exists(): state(request.get('id'))
        return recover()
    if op == 'status': return status(request.get('id'))
    if op == 'watchdog':
        if STATE.exists() and (time.time() > state()['expires'] or run('systemctl', 'show', '-p', 'ActiveState', '--value', 'cloud-game.service') != 'active'): return recover()
        return {'ok': True}
    if op == 'pair':
        value = state(request.get('id')); pin = request.get('pin')
        if value['paired'] or not isinstance(pin, str) or not re.fullmatch(r'\d{4}', pin):
            raise RuntimeError('Pareamento recusado.')
        value['paired'] = True; write_state(value)
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            pending = api(value, '/api/pin').get('pairings', [])
            if len(pending) > 1: raise RuntimeError('Múltiplos pedidos de pareamento.')
            if pending:
                identity = pending[0].get('id', '')
                if not re.fullmatch('[a-fA-F0-9]{32}', identity): raise RuntimeError('Identificador inválido.')
                result = api(value, '/api/pin', {'pairing_id': identity, 'pin': pin, 'name': 'Cloud Game Player'})
                return {'paired': result.get('status') is True}
            time.sleep(0.25)
        raise RuntimeError('Moonlight não iniciou o pareamento.')
    raise RuntimeError('Operação não autorizada.')


if __name__ == '__main__':
    try:
        if os.geteuid() != 0: raise RuntimeError('Controlador requer root.')
        os.umask(0o077); trusted(ROOT, True)
        with open(ROOT / 'native.lock', 'a', opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW, 0o600)) as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            raw = sys.stdin.read(8193)
            if len(raw) > 8192: raise RuntimeError('Solicitação grande demais.')
            print(json.dumps(dispatch(json.loads(raw))))
    except Exception as error:
        print(str(error), file=sys.stderr); sys.exit(1)
