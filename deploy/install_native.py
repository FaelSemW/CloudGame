"""Install the control service and native session dependencies; never creates a VM."""
import json
import os
from pathlib import Path
import pwd
import re
import shutil
from install_host import run, write, trusted_directory, serve_available, SOURCE, DEST


def install(software=False):
    if os.geteuid() != 0: raise RuntimeError('Instalação requer root.')
    if DEST.exists() or DEST.is_symlink(): raise RuntimeError('Instalação anterior preservada; migração precisa de revisão.')
    outputs = [Path('/etc/systemd/system') / name for name in (
        'cloud-game.service', 'cloud-game-network.service', 'cloud-game-watchdog.service',
        'cloud-game-watchdog.timer', 'var-lib-cloudgame-native\\x2dvolatile.mount')]
    outputs += [Path('/etc/cloud-game') / name for name in ('native.json', 'host.env', 'installed.json')]
    outputs += [Path('/etc/sudoers.d/cloud-game')]
    for output in outputs:
        if output.exists() or output.is_symlink(): raise RuntimeError('Configuração existente preservada: ' + str(output))
    for command in ('bwrap', 'sunshine', 'steam', 'sway', 'pulseaudio', 'nft', 'tailscale'):
        if not shutil.which(command): raise RuntimeError('Componente ausente: ' + command)
    info = json.loads(run('tailscale', 'status', '--json'))
    dns = info.get('Self', {}).get('DNSName', '').rstrip('.')
    from native_helper import peer_ip
    address = next((ip for ip in info.get('Self', {}).get('TailscaleIPs', []) if ip.startswith('100.')), None)
    if not re.fullmatch(r'[a-z0-9.-]+\.ts\.net', dns) or not address: raise RuntimeError('Tailscale não está pronto.')
    peer_ip(address)
    serve_available(json.loads(run('tailscale', 'serve', 'status', '--json')))
    from network_setup import validate_network, firewall_plan
    validate_network(json.loads(run('ip', '-details', '-json', 'link', 'show')),
                     json.loads(run('ip', '-json', '-4', 'route', 'show', 'table', 'all')))
    firewall_plan('cloud-game')
    root = Path('/var/lib/cloudgame'); trusted_directory(root)
    root.chmod(0o751)
    if (root / 'runtime.json').exists(): raise RuntimeError('Sessão VM anterior ainda registrada.')
    for user, home in [('cloud-game', '/var/lib/cloudgame/control'), ('cloud-game-player', '/nonexistent')]:
        try:
            account = pwd.getpwnam(user)
            if account.pw_shell not in ('/usr/sbin/nologin', '/sbin/nologin'):
                raise RuntimeError('Conta existente não é uma conta de serviço: ' + user)
        except KeyError:
            run('useradd', '--system', '--home-dir', home, '--shell', '/usr/sbin/nologin', user)
    control = root / 'control'; trusted_directory(control)
    account = pwd.getpwnam('cloud-game')
    os.chown(control, account.pw_uid, account.pw_gid); control.chmod(0o700)
    trusted_directory(root / 'library')
    (root / 'library').chmod(0o755)
    trusted_directory(root / 'native-volatile')
    DEST.mkdir(mode=0o755)
    for folder in ('host', 'client', 'deploy', 'docs', 'licenses'):
        for file in (SOURCE / folder).rglob('*'):
            if file.is_symlink(): raise RuntimeError('Symlink recusado no pacote.')
            if file.is_file() and '__pycache__' not in file.parts:
                target = DEST / file.relative_to(SOURCE)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, target); target.chmod(0o644)
    from runtime import install_runtime
    install_runtime(DEST / 'runtime')
    DEST.chmod(0o755)
    for folder in DEST.rglob('*'):
        if folder.is_dir(): folder.chmod(0o755)
    directory = Path('/etc/cloud-game'); trusted_directory(directory)
    write(directory / 'native.json', json.dumps({'backend': 'native', 'renderer': 'software' if software else 'gpu'}), 0o600)
    write(directory / 'host.env', f'CG_ORIGIN=https://{dns}\nCG_STREAM_HOST={address}\nCG_BACKEND=native\n', 0o600)
    sudoers = Path('/etc/sudoers.d/cloud-game')
    write(sudoers, 'cloud-game ALL=(root) NOPASSWD: /usr/bin/python3 /opt/cloud-game/deploy/native_helper.py\n', 0o440)
    run('visudo', '-cf', str(sudoers))
    units = Path('/etc/systemd/system')
    for name in ('cloud-game.service', 'cloud-game-network.service', 'cloud-game-watchdog.service', 'cloud-game-watchdog.timer'):
        content = (SOURCE / 'deploy' / name).read_text()
        content = content.replace('libvirtd.service ', '').replace('var-lib-cloudgame-volatile.mount', 'var-lib-cloudgame-native\\x2dvolatile.mount')
        content = content.replace('/deploy/vm_helper.py', '/deploy/native_helper.py')
        content = content.replace('ExecStart=/usr/bin/node ', 'ExecStart=/opt/cloud-game/runtime/node ')
        write(units / name, content)
    write(units / 'var-lib-cloudgame-native\\x2dvolatile.mount',
          '[Unit]\nDescription=Cloud Game native temporary files\nBefore=cloud-game.service\n'
          '[Mount]\nWhat=tmpfs\nWhere=/var/lib/cloudgame/native-volatile\nType=tmpfs\n'
          'Options=mode=0751,size=8G,nosuid,nodev\n[Install]\nWantedBy=multi-user.target\n')
    run('systemctl', 'daemon-reload')
    run('systemctl', 'enable', '--now', 'cloud-game.service', 'cloud-game-watchdog.timer')
    run('tailscale', 'serve', '--bg', '--https=443', 'http://127.0.0.1:8787')
    write(directory / 'installed.json', json.dumps({'installer': 'cloud-game-native-v1', 'backend': 'native'}), 0o600)
    print('HOST nativo instalado. Nenhum disco Ubuntu ou QEMU foi criado.')
