#!/usr/bin/python3
"""Root-only, fixed-operation controller. No client-supplied paths or commands."""
import fcntl
import ipaddress
import json
import os
import pathlib
import pwd
import re
import stat
import subprocess
import sys
import time
import urllib.request
import uuid
import xml.etree.ElementTree as ET

ROOT = pathlib.Path('/var/lib/cloudgame')
VOL = ROOT / 'volatile'
CONFIG = pathlib.Path('/etc/cloud-game/vm.json')
STATE = ROOT / 'runtime.json'
BRIDGE = 'cgbr0'
GUEST = '10.77.0.2'
GATEWAY = '10.77.0.1'
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')


def run(*args, data=None, timeout=30):
    p = subprocess.run(args, input=data, text=True, capture_output=True, timeout=timeout,
                       env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'})
    if p.returncode:
        # Never include stdin: it can contain pairing PINs.
        raise RuntimeError(f'{args[0]} falhou: {p.stderr.strip()[:1000]}')
    return p.stdout.strip()


def trusted(path, directory=False):
    s = path.lstat()
    if stat.S_ISLNK(s.st_mode) or s.st_uid != 0 or s.st_mode & 0o022:
        raise RuntimeError(f'Propriedade/permissões inseguras: {path}')
    if directory and not stat.S_ISDIR(s.st_mode):
        raise RuntimeError('Diretório obrigatório.')
    if not directory and not stat.S_ISREG(s.st_mode):
        raise RuntimeError('Arquivo regular obrigatório.')


def configuration():
    trusted(CONFIG.parent, True)
    trusted(CONFIG)
    c = json.loads(CONFIG.read_text())
    if c.get('templateReviewed') is not True:
        raise RuntimeError('A imagem-base precisa passar pela revisão descrita em docs/BAZZITE.md.')
    profile = c.get('profile', 'vfio')
    if profile not in ('vfio', 'software'):
        raise RuntimeError('Perfil de virtualização inválido.')
    if not isinstance(c.get('memoryMiB'), int) or not (2048 if profile == 'software' else 4096) <= c['memoryMiB'] <= 65536:
        raise RuntimeError('Memória inválida.')
    if not isinstance(c.get('cpus'), int) or not 2 <= c['cpus'] <= 32:
        raise RuntimeError('Número de CPUs inválido.')
    devices = c.get('gpuDevices', [])
    if profile == 'software':
        if devices != []: raise RuntimeError('Perfil software não pode repassar dispositivos físicos.')
    elif not devices or not all(isinstance(d, str) and re.fullmatch(r'0000:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]', d) for d in devices):
        raise RuntimeError('Informe a GPU dedicada e todas as funções do seu grupo IOMMU.')
    return c


def valid_id(value):
    if not isinstance(value, str) or not UUID.fullmatch(value):
        raise RuntimeError('Identificador de sessão inválido.')
    return value


def peer_ip(value):
    ip = ipaddress.ip_address(value)
    if ip not in ipaddress.ip_network('100.64.0.0/10'):
        raise RuntimeError('Dispositivo fora da rede Tailscale.')
    return str(ip)


def write_state(value):
    tmp = ROOT / 'runtime.new'
    with open(tmp, 'w', opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW, 0o600)) as f:
        json.dump(value, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, STATE)
    fd = os.open(ROOT, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def domains():
    return [x for x in run('virsh', '-c', 'qemu:///system', 'list', '--all', '--name').splitlines() if x.startswith('cg-')]


def assert_memory_only_swap():
    for entry in pathlib.Path('/proc/swaps').read_text().splitlines()[1:]:
        device = entry.split()[0]
        if not re.fullmatch(r'/dev/zram[0-9]+', device):
            raise RuntimeError('Swap persistente não é permitido para sessões temporárias.')
        backing = pathlib.Path('/sys/block') / pathlib.Path(device).name / 'backing_dev'
        if not backing.exists() or backing.read_text().strip() != 'none':
            raise RuntimeError('Zram com writeback ou configuração desconhecida não é permitido.')


def assert_volatile():
    trusted(VOL, True)
    info = json.loads(run('findmnt', '--json', '--mountpoint', str(VOL), '-o', 'TARGET,FSTYPE'))['filesystems']
    if len(info) != 1 or info[0]['target'] != str(VOL) or info[0]['fstype'] != 'tmpfs':
        raise RuntimeError('O volume de sessões precisa ser um tmpfs dedicado.')
    assert_memory_only_swap()


def doctor():
    c = configuration()
    if 'bazzite' not in pathlib.Path('/etc/os-release').read_text().lower():
        raise RuntimeError('Esta versão do controlador exige Bazzite no HOST.')
    if c.get('profile', 'vfio') == 'vfio' and not pathlib.Path('/dev/kvm').exists():
        raise RuntimeError('KVM não disponível.')
    if 'pcie_acs_override=' in pathlib.Path('/proc/cmdline').read_text():
        raise RuntimeError('ACS override não é aceito como fronteira IOMMU segura.')
    for flag in ('/sys/module/vfio/parameters/enable_unsafe_noiommu_mode', '/sys/module/vfio_iommu_type1/parameters/allow_unsafe_interrupts'):
        if pathlib.Path(flag).exists() and pathlib.Path(flag).read_text().strip().lower() in ('y', '1'):
            raise RuntimeError('Modo VFIO inseguro habilitado.')
    assert_volatile()
    base = ROOT / 'base.qcow2'
    trusted(base)
    if base.stat().st_mode & 0o222:
        raise RuntimeError('A imagem-base deve estar em modo somente leitura (0444).')
    info = json.loads(run('qemu-img', 'info', '--output=json', str(base)))
    if info.get('format') != 'qcow2' or info.get('backing-filename') or info.get('snapshots'):
        raise RuntimeError('Use uma imagem qcow2 independente, sem backing ou snapshots.')
    for d in c['gpuDevices']:
        p = pathlib.Path('/sys/bus/pci/devices') / d
        device_class = (p / 'class').read_text().strip()
        if not (device_class.startswith('0x03') or device_class.startswith('0x0403')):
            raise RuntimeError('Somente GPU e função de áudio podem ser repassadas: ' + d)
        if (p / 'driver').resolve().name != 'vfio-pci' or not (p / 'iommu_group').exists():
            raise RuntimeError('GPU sem driver vfio-pci/grupo IOMMU: ' + d)
        group = {x.name for x in (p / 'iommu_group/devices').iterdir()}
        if not group.issubset(set(c['gpuDevices'])):
            raise RuntimeError('O grupo IOMMU contém dispositivos não autorizados: ' + d)
    run('virsh', '-c', 'qemu:///system', 'list', '--all')
    address = peer_ip(run('tailscale', 'ip', '-4').splitlines()[0])
    if pathlib.Path('/proc/sys/net/ipv4/ip_forward').read_text().strip() != '1':
        raise RuntimeError('Encaminhamento IPv4 precisa estar habilitado.')
    if not pathlib.Path('/sys/class/net/' + BRIDGE).exists():
        raise RuntimeError('Bridge cgbr0 ausente. Execute o instalador.')
    return {'ok': True, 'tailscale': address, 'gpuDevices': c['gpuDevices'], 'memoryMiB': c['memoryMiB'],
            'profile': c.get('profile', 'vfio'), 'isolation': 'VM QEMU + qcow2 em tmpfs sem swap',
            'warning': 'Perfil software: desempenho limitado; GPU física não validada.' if c.get('profile') == 'software' else ''}


def network(peer=None):
    # Atomic replacement of our table, never flush the owner's firewall.
    tables = run('nft', 'list', 'tables')
    prefix = 'delete table inet cloud_game\n' if 'table inet cloud_game' in tables.splitlines() else ''
    inbound = ''
    outbound = ''
    peer_return = ''
    blocked = f'iifname "{BRIDGE}" drop\n oifname "{BRIDGE}" drop'
    nat = ''
    if peer:
        blocked = ''
        outbound = f'iifname "{BRIDGE}" ip daddr {peer} ip protocol udp accept'
        outbound += f'\n iifname "{BRIDGE}" ip daddr {peer} ct state established,related accept'
        peer_return = f'iifname "tailscale0" oifname "{BRIDGE}" ip saddr {peer} ct state established,related accept'
        host = peer_ip(run('tailscale', 'ip', '-4').splitlines()[0])
        inbound = f'iifname "tailscale0" ip saddr {peer} ip daddr {GUEST} tcp dport {{47984,47989,48010}} accept\n iifname "tailscale0" ip saddr {peer} ip daddr {GUEST} udp dport {{47998,47999,48000,48002,48010}} accept'
        nat = f'''chain prerouting {{ type nat hook prerouting priority dstnat; policy accept;
          iifname "tailscale0" ip saddr {peer} ip daddr {host} tcp dport {{47984,47989,48010}} dnat ip to {GUEST}
          iifname "tailscale0" ip saddr {peer} ip daddr {host} udp dport {{47998,47999,48000,48002,48010}} dnat ip to {GUEST}
        }}'''
    rules = prefix + f'''table inet cloud_game {{
      set private4 {{ type ipv4_addr; flags interval; elements = {{0.0.0.0/8,10.0.0.0/8,100.64.0.0/10,127.0.0.0/8,169.254.0.0/16,172.16.0.0/12,192.168.0.0/16,198.18.0.0/15,224.0.0.0/3}} }}
      chain input {{ type filter hook input priority -200; policy accept;
        iifname "{BRIDGE}" ip saddr != {GUEST} drop
        iifname "{BRIDGE}" ct state established,related accept
        iifname "{BRIDGE}" drop
      }}
      chain forward {{ type filter hook forward priority -200; policy accept;
        {blocked}
        iifname "{BRIDGE}" meta nfproto ipv6 drop
        oifname "{BRIDGE}" meta nfproto ipv6 drop
        iifname "{BRIDGE}" ip saddr != {GUEST} drop
        {outbound}
        iifname "{BRIDGE}" ip daddr @private4 drop
        iifname "{BRIDGE}" ct state established,related accept
        iifname "{BRIDGE}" accept
        {inbound}
        {peer_return}
        oifname "{BRIDGE}" ip saddr @private4 drop
        oifname "{BRIDGE}" ct state established,related accept
        oifname "{BRIDGE}" drop
      }}
      {nat}
      chain postrouting {{ type nat hook postrouting priority srcnat; policy accept;
        ip saddr {GUEST} oifname != "{BRIDGE}" masquerade
      }}
    }}'''
    run('nft', '-f', '-', data=rules)


def domain_xml(c, sid):
    software = c.get('profile') == 'software'
    accelerated = not software or pathlib.Path('/dev/kvm').exists()
    root = ET.Element('domain', type='kvm' if accelerated else 'qemu')
    ET.SubElement(root, 'name').text = 'cg-' + sid
    ET.SubElement(root, 'uuid').text = sid
    ET.SubElement(root, 'memory', unit='MiB').text = str(c['memoryMiB'])
    ET.SubElement(root, 'vcpu').text = str(c['cpus'])
    if accelerated:
        ET.SubElement(root, 'cpu', mode='host-passthrough')
    else:
        ET.SubElement(root, 'cpu', mode='maximum')
    osel = ET.SubElement(root, 'os')
    ET.SubElement(osel, 'type', arch='x86_64', machine='q35').text = 'hvm'
    ET.SubElement(osel, 'boot', dev='hd')
    features = ET.SubElement(root, 'features')
    ET.SubElement(features, 'acpi')
    ET.SubElement(features, 'apic')
    ET.SubElement(root, 'on_crash').text = 'destroy'
    account = pwd.getpwnam('qemu')
    dac = ET.SubElement(root, 'seclabel', type='static', model='dac', relabel='no')
    ET.SubElement(dac, 'label').text = f'+{account.pw_uid}:+{account.pw_gid}'
    dev = ET.SubElement(root, 'devices')
    disk = ET.SubElement(dev, 'disk', type='file', device='disk')
    ET.SubElement(disk, 'driver', name='qemu', type='qcow2', cache='none')
    ET.SubElement(disk, 'source', file=str(VOL / sid / 'disk.qcow2'))
    ET.SubElement(disk, 'target', dev='vda', bus='virtio')
    interface = ET.SubElement(dev, 'interface', type='bridge')
    ET.SubElement(interface, 'source', bridge=BRIDGE)
    ET.SubElement(interface, 'mac', address='52:54:00:77:00:02')
    ET.SubElement(interface, 'model', type='virtio')
    channel = ET.SubElement(dev, 'channel', type='unix')
    ET.SubElement(channel, 'target', type='virtio', name='org.qemu.guest_agent.0')
    # Guest PulseAudio captures this card; never attach the owner's audio server.
    ET.SubElement(ET.SubElement(dev, 'sound', model='ich9'), 'audio', id='1')
    ET.SubElement(dev, 'audio', id='1', type='none')
    ET.SubElement(dev, 'video').append(ET.Element('model', type='vga' if software else 'none'))
    if software:
        # A virtual framebuffer without a network-accessible SPICE listener.
        ET.SubElement(ET.SubElement(dev, 'graphics', type='spice'), 'listen', type='none')
    for d in c['gpuDevices']:
        domain, bus, slotfn = d.split(':')
        slot, function = slotfn.split('.')
        device = ET.SubElement(dev, 'hostdev', mode='subsystem', type='pci', managed='no')
        source = ET.SubElement(device, 'source')
        ET.SubElement(source, 'address', domain='0x' + domain, bus='0x' + bus, slot='0x' + slot, function='0x' + function)
    return ET.tostring(root, encoding='unicode')


def qga(sid, command, arguments=None):
    request = {'execute': command}
    if arguments is not None:
        request['arguments'] = arguments
    result = json.loads(run('virsh', '-c', 'qemu:///system', 'qemu-agent-command', 'cg-' + valid_id(sid), json.dumps(request), timeout=5))
    if 'error' in result:
        raise RuntimeError('Guest agent recusou a operação.')
    return result['return']


def guest(sid, operation, pin=None):
    import base64
    arguments = {'path': '/usr/local/libexec/cloud-game-guest', 'arg': [operation], 'capture-output': True}
    if pin is not None:
        arguments['input-data'] = base64.b64encode(pin.encode()).decode()
    pid = qga(sid, 'guest-exec', arguments)['pid']
    deadline = time.monotonic() + (50 if operation == 'pair' else 10)
    while time.monotonic() < deadline:
        result = qga(sid, 'guest-exec-status', {'pid': pid})
        if result.get('exited'):
            if result.get('exitcode') != 0 or result.get('out-truncated'):
                raise RuntimeError('O agente interno não confirmou a operação do Sunshine.')
            return json.loads(base64.b64decode(result.get('out-data', '')).decode())
        time.sleep(0.1)
    raise RuntimeError('O agente interno não respondeu a tempo.')


def read_state(sid):
    trusted(STATE)
    state = json.loads(STATE.read_text())
    if state['id'] != valid_id(sid):
        raise RuntimeError('Sessão não corresponde ao registro do HOST.')
    return state


def status(sid):
    read_state(sid)
    if 'cg-' + sid not in domains():
        return {'ready': False, 'connected': False}
    return guest(sid, 'status')


def start(sid, peer):
    valid_id(sid)
    peer = peer_ip(peer)
    doctor()
    if STATE.exists() or domains() or list(VOL.iterdir()):
        raise RuntimeError('Há dados ou uma VM pendentes de limpeza.')
    c = configuration()
    write_state({'id': sid, 'peer': peer, 'expires': time.time() + 4 * 3600, 'paired': False})
    network(peer)
    directory = VOL / sid
    directory.mkdir(mode=0o750)
    account = pwd.getpwnam('qemu')
    os.chown(directory, 0, account.pw_gid)
    disk = directory / 'disk.qcow2'
    run('qemu-img', 'create', '-f', 'qcow2', '-F', 'qcow2', '-b', str(ROOT / 'base.qcow2'), str(disk))
    os.chown(disk, account.pw_uid, account.pw_gid)
    disk.chmod(0o600)
    run('restorecon', '-R', str(VOL))
    run('virsh', '-c', 'qemu:///system', 'create', '/dev/stdin', data=domain_xml(c, sid))
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        try:
            if status(sid).get('ready'):
                return {'ready': True}
        except (RuntimeError, subprocess.SubprocessError):
            pass
        time.sleep(2)
    raise RuntimeError('Sunshine não ficou pronto em 120 segundos.')


def recover():
    # Revoke network access first. Any failure retains the state record.
    network()
    for name in domains():
        valid_id(name[3:])
        run('virsh', '-c', 'qemu:///system', 'destroy', name)
    if domains():
        raise RuntimeError('Ainda existe uma VM de sessão.')
    for path in pathlib.Path('/proc').glob('[0-9]*/cmdline'):
        try:
            command = path.read_bytes()
        except FileNotFoundError:
            continue
        if b'qemu-system' in command and b'guest=cg-' in command:
            raise RuntimeError('Um processo QEMU da sessão ainda está ativo.')
    trusted(VOL, True)
    for directory in VOL.iterdir():
        valid_id(directory.name)
        trusted(directory, True)
        for file in directory.iterdir():
            if file.name != 'disk.qcow2' or file.is_symlink() or not file.is_file():
                raise RuntimeError('Conteúdo inesperado; limpeza automática bloqueada.')
            if file.stat().st_nlink != 1:
                raise RuntimeError('Arquivo com múltiplos links; limpeza bloqueada.')
            file.unlink()
        directory.rmdir()
    if list(VOL.iterdir()):
        raise RuntimeError('O volume temporário não ficou vazio.')
    STATE.unlink(missing_ok=True)
    return {'clean': True}


def dispatch(request):
    op = request.get('op')
    if op == 'doctor':
        return doctor()
    if op == 'recover':
        return recover()
    if op == 'start':
        return start(request.get('id'), request.get('peer'))
    if op == 'stop':
        if STATE.exists():
            read_state(request.get('id'))
        elif request.get('id') is not None:
            valid_id(request['id'])
        recover()
        doctor()
        return {'clean': True}
    if op == 'status':
        return status(request.get('id'))
    if op == 'pair':
        state = read_state(request.get('id'))
        pin = request.get('pin')
        if state.get('paired') or not isinstance(pin, str) or not re.fullmatch(r'\d{4}', pin):
            raise RuntimeError('Pareamento recusado.')
        # Mark before side effect: a crash must not permit a second client.
        state['paired'] = True
        write_state(state)
        result = guest(state['id'], 'pair', pin)
        if result.get('status') is not True:
            raise RuntimeError('Sunshine recusou o PIN. Encerre e crie outra sessão para tentar novamente.')
        return {'paired': True}
    if op == 'watchdog':
        if STATE.exists():
            state = json.loads(STATE.read_text())
            running = subprocess.run(['systemctl', 'is-active', '--quiet', 'cloud-game.service']).returncode == 0
            if time.time() > state['expires'] or not running:
                return recover()
        return {'ok': True}
    raise RuntimeError('Operação não autorizada.')


def main():
    if os.geteuid() != 0:
        raise RuntimeError('O controlador exige root.')
    os.umask(0o077)
    trusted(ROOT, True)
    with open(ROOT / 'controller.lock', 'a', opener=lambda p, f: os.open(p, f | os.O_NOFOLLOW, 0o600)) as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw = sys.stdin.read(8193)
        if len(raw) > 8192:
            raise RuntimeError('Solicitação muito grande.')
        print(json.dumps(dispatch(json.loads(raw))))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
