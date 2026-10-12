#!/usr/bin/python3
import pathlib
import subprocess

def run(*args):
    subprocess.run(args, check=True)

if not pathlib.Path('/sys/class/net/cgbr0').exists():
    run('/usr/sbin/ip', 'link', 'add', 'cgbr0', 'type', 'bridge')
run('/usr/sbin/ip', 'address', 'replace', '10.77.0.1/24', 'dev', 'cgbr0')
run('/usr/sbin/ip', 'link', 'set', 'cgbr0', 'up')
run('/usr/sbin/sysctl', '-w', 'net.ipv4.ip_forward=1')
