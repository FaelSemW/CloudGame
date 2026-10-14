#!/usr/bin/python3
"""Configure only the CloudGame bridge; preserve unrelated host networking."""
import ipaddress
import json
import shutil
import subprocess

BRIDGE = 'cgbr0'
OWNER = 'cloud-game-managed-v1'
SUBNET = ipaddress.ip_network('10.77.0.0/24')


def run(*args):
    return subprocess.run(args, check=True, text=True, capture_output=True, timeout=30).stdout.strip()


def validate_network(links, routes):
    bridge = next((link for link in links if link['ifname'] == BRIDGE), None)
    if bridge and (bridge.get('ifalias') != OWNER or
                   bridge.get('linkinfo', {}).get('info_kind') != 'bridge'):
        raise RuntimeError('cgbr0 já existe e não pertence ao CloudGame; interface preservada.')
    for route in routes:
        destination = route.get('dst', 'default')
        if destination == 'default' or route.get('dev') == BRIDGE:
            continue
        if ipaddress.ip_network(destination, strict=False).overlaps(SUBNET):
            raise RuntimeError('A rede 10.77.0.0/24 conflita com uma rota existente; rede preservada.')
    return bridge is not None


def firewall_plan(zone_name=None):
    """Read both configurations before any mutation; never reload all rules."""
    active = subprocess.run(['systemctl', 'is-active', '--quiet', 'firewalld'], timeout=10)
    if active.returncode == 3:
        return []
    if active.returncode == 4 and run('systemctl', 'show', '--property=LoadState', '--value', 'firewalld.service') == 'not-found':
        return []
    if active.returncode != 0:
        raise RuntimeError('Não foi possível determinar o estado do firewalld.')
    if not shutil.which('firewall-cmd'):
        raise RuntimeError('firewalld ativo, mas firewall-cmd ausente.')
    zone_name = zone_name or ('cloud-game' if __import__('pathlib').Path('/etc/cloud-game/native.json').exists() else 'libvirt')
    commands = []
    for scope in [(), ('--permanent',)]:
        zones = run('firewall-cmd', *scope, '--get-zones').split()
        if zone_name not in zones:
            raise RuntimeError('Zona ' + zone_name + ' ausente no firewalld; reinicie após preparar a rede.')
        assigned = []
        for zone in zones:
            if BRIDGE in run('firewall-cmd', *scope, '--zone=' + zone, '--list-interfaces').split():
                assigned.append(zone)
        if assigned and assigned != [zone_name]:
            raise RuntimeError('cgbr0 pertence a outra zona do firewalld; configuração preservada.')
        if not assigned:
            commands.append(('firewall-cmd', *scope, '--zone=' + zone_name, '--add-interface=' + BRIDGE))
    return commands


def setup():
    exists = validate_network(json.loads(run('ip', '-details', '-json', 'link', 'show')),
                              json.loads(run('ip', '-json', '-4', 'route', 'show', 'table', 'all')))
    commands = firewall_plan()
    # Close guest access before bringing up a bridge or assigning its firewall zone.
    from vm_helper import network
    network()
    if not exists:
        run('ip', 'link', 'add', BRIDGE, 'type', 'bridge')
        run('ip', 'link', 'set', BRIDGE, 'alias', OWNER)
    for command in commands:
        run(*command)
    run('ip', 'address', 'replace', '10.77.0.1/24', 'dev', BRIDGE)
    run('ip', 'link', 'set', BRIDGE, 'up')
    run('sysctl', '-w', 'net.ipv4.ip_forward=1')


if __name__ == '__main__':
    setup()
