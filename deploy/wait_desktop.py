#!/usr/bin/python3
"""Wait for the player's authenticated X11 display and audio before Sunshine probes them."""
import subprocess
import sys
import time


def ready(command):
    try:
        return subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                              timeout=3).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def main():
    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        if ready(['/usr/bin/xdpyinfo']) and ready(['/usr/bin/pactl', 'info']):
            return 0
        time.sleep(1)
    print('O desktop X11 ou o áudio do jogador não ficou pronto para o Sunshine.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
