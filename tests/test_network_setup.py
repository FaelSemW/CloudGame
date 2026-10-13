import importlib.util
from pathlib import Path
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('network_setup', Path(__file__).resolve().parents[1] / 'deploy/network_setup.py')
network = importlib.util.module_from_spec(spec)
spec.loader.exec_module(network)


class NetworkSetupTests(unittest.TestCase):
    def test_owner_bridge_is_preserved(self):
        for link in [{'ifname': 'cgbr0'}, {'ifname': 'cgbr0', 'ifalias': network.OWNER}]:
            with self.assertRaisesRegex(RuntimeError, 'preservada'):
                network.validate_network([link], [])

    def test_overlapping_routes_are_rejected_except_own_bridge_and_default(self):
        for destination in ['10.77.0.0/24', '10.0.0.0/8', '10.77.0.9/32']:
            with self.assertRaisesRegex(RuntimeError, 'conflita'):
                network.validate_network([], [{'dst': destination, 'dev': 'owner-vpn'}])
        self.assertFalse(network.validate_network([], [{'dst': 'default'}, {'dst': '10.77.0.0/24', 'dev': 'cgbr0'}]))

    def test_firewall_conflict_is_checked_before_any_write(self):
        def read(*args):
            if args[-1] == '--get-zones': return 'libvirt public'
            return 'cgbr0' if '--permanent' in args and '--zone=public' in args else ''
        with patch.object(network.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0)), \
             patch.object(network.shutil, 'which', return_value='/bin/firewall-cmd'), \
             patch.object(network, 'run', side_effect=read) as command:
            with self.assertRaisesRegex(RuntimeError, 'preservada'):
                network.firewall_plan()
            self.assertFalse(any('--add-interface=cgbr0' in call.args for call in command.call_args_list))

    def test_firewall_plan_changes_only_own_interface_without_reload(self):
        with patch.object(network.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0)), \
             patch.object(network.shutil, 'which', return_value='/bin/firewall-cmd'), \
             patch.object(network, 'run', side_effect=lambda *args: 'libvirt public' if args[-1] == '--get-zones' else ''):
            self.assertEqual(network.firewall_plan(), [
                ('firewall-cmd', '--zone=libvirt', '--add-interface=cgbr0'),
                ('firewall-cmd', '--permanent', '--zone=libvirt', '--add-interface=cgbr0')])
