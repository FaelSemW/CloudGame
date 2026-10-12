"""Portable policy tests; subprocesses, /proc and privilege checks are injected.
These do NOT claim to validate KVM, nftables or Bazzite.
"""
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import io
import pathlib
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

if sys.platform == 'win32':
    sys.modules['fcntl'] = types.SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=lambda *a: None)
    sys.modules['pwd'] = types.SimpleNamespace(getpwnam=lambda name: types.SimpleNamespace(pw_uid=107, pw_gid=107))
path = pathlib.Path(__file__).parent.parent / 'deploy/vm_helper.py'
spec = importlib.util.spec_from_file_location('vm_helper', path)
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
SID = '173fd771-0b7c-4c0e-9b5a-7bd07fe9d12f'
guest_path = pathlib.Path(__file__).parent.parent / 'deploy/cloud-game-guest'
guest_spec = importlib.util.spec_from_loader('guest_adapter', SourceFileLoader('guest_adapter', str(guest_path)))
guest_adapter = importlib.util.module_from_spec(guest_spec)
guest_spec.loader.exec_module(guest_adapter)


class PolicyTests(unittest.TestCase):
    def test_pairing_binds_pin_to_upstream_request_id(self):
        responses = [{'pairings': []}, {'pairings': [{'id': 'b'*32}]}, {'status': True}]
        with patch.object(sys, 'argv', ['cloud-game-guest', 'pair']), patch.object(sys, 'stdin', io.StringIO('1234')), patch.object(guest_adapter, 'api', side_effect=responses) as api, patch.object(guest_adapter.time, 'sleep'):
            self.assertEqual(guest_adapter.main(), {'status': True})
            self.assertEqual(api.call_args.args, ('/api/pin', {'pairing_id': 'b'*32, 'pin': '1234', 'name': 'Cloud Game Player'}))

    def test_pairing_refuses_ambiguous_pending_clients(self):
        with patch.object(sys, 'argv', ['cloud-game-guest', 'pair']), patch.object(sys, 'stdin', io.StringIO('1234')), patch.object(guest_adapter, 'api', return_value={'pairings': [{'id': 'b'*32}, {'id': 'c'*32}]}) as api:
            with self.assertRaisesRegex(RuntimeError, 'Mais de um'):
                guest_adapter.main()
            self.assertEqual(api.call_count, 1)

    def test_sunshine_ready_before_first_connection_marker(self):
        journal = types.SimpleNamespace(returncode=1, stdout='', stderr='')
        with patch.object(sys, 'argv', ['cloud-game-guest', 'status']), patch.object(guest_adapter, 'api', return_value={'apps':[{'name':'Desktop'}], 'pairings': []}), patch.object(guest_adapter.subprocess, 'check_output', return_value='a'*32), patch.object(guest_adapter.subprocess, 'run', return_value=journal):
            self.assertEqual(guest_adapter.main(), {'ready':True, 'connected':False})

    def test_sunshine_multiple_connection_markers_fail_closed(self):
        journal = types.SimpleNamespace(returncode=0, stdout='Info: CLIENT CONNECTED\nInfo: CLIENT CONNECTED', stderr='')
        with patch.object(sys, 'argv', ['cloud-game-guest', 'status']), patch.object(guest_adapter, 'api', return_value={'apps':[{'name':'Desktop'}], 'pairings': []}), patch.object(guest_adapter.subprocess, 'check_output', return_value='a'*32), patch.object(guest_adapter.subprocess, 'run', return_value=journal):
            with self.assertRaises(RuntimeError):
                guest_adapter.main()

    def test_rejects_client_paths_and_command_injection(self):
        for value in ('../../owner', '/home/owner', SID + ';id', '', None, 'A' * 36):
            with self.assertRaises(RuntimeError):
                helper.valid_id(value)
        self.assertEqual(helper.valid_id(SID), SID)

    def test_peer_must_be_in_tailscale_ipv4_range(self):
        self.assertEqual(helper.peer_ip('100.64.0.1'), '100.64.0.1')
        for value in ('127.0.0.1', '192.168.1.2', '100.128.1.1', '::1', '1.1.1.1'):
            with self.assertRaises((RuntimeError, ValueError, TypeError)):
                helper.peer_ip(value)

    def test_vm_has_only_temporary_disk_and_no_owner_shares(self):
        account = types.SimpleNamespace(pw_uid=107, pw_gid=107)
        with patch.object(helper.pwd, 'getpwnam', return_value=account):
            xml = ET.fromstring(helper.domain_xml({'memoryMiB':8192, 'cpus':4, 'gpuDevices':['0000:01:00.0']}, SID))
        self.assertEqual(len(xml.findall('./devices/disk')), 1)
        source = xml.find('./devices/disk/source').get('file')
        self.assertEqual(pathlib.Path(source), helper.VOL / SID / 'disk.qcow2')
        self.assertEqual(xml.findall('./devices/filesystem'), [])
        self.assertEqual(xml.findall('./devices/graphics'), [])
        self.assertEqual(xml.find('./devices/interface/source').get('bridge'), 'cgbr0')
        self.assertEqual(xml.find('./seclabel').get('relabel'), 'no')

    def test_firewall_closes_all_bridge_flows_before_cleanup(self):
        commands = []
        def run(*args, **kwargs):
            commands.append((args, kwargs))
            return 'table inet cloud_game' if args == ('nft','list','tables') else ''
        with patch.object(helper, 'run', side_effect=run):
            helper.network()
        rules = commands[-1][1]['data']
        self.assertTrue(rules.startswith('delete table inet cloud_game'))
        forward = rules.split('chain forward')[1]
        self.assertLess(forward.index('iifname "cgbr0" drop'), forward.index('ct state established'))
        self.assertNotIn('dnat',rules)
        self.assertNotIn('flush ruleset',rules)

    def test_stream_forwarding_never_exposes_sunshine_admin(self):
        commands = []
        def run(*args, **kwargs):
            commands.append((args, kwargs))
            return '100.100.1.1' if args[0] == 'tailscale' else ''
        with patch.object(helper, 'run', side_effect=run):
            helper.network('100.100.1.2')
        rules = commands[-1][1]['data']
        self.assertNotIn('47990', rules)
        self.assertIn('ip saddr 100.100.1.2 ip daddr 100.100.1.1',rules)
        self.assertIn('meta nfproto ipv6 drop',rules)
        self.assertIn('ip daddr @private4 drop',rules)

    def test_pair_mark_is_persisted_before_side_effect(self):
        events = []
        state = {'id':SID,'paired':False}
        with patch.object(helper, 'read_state', return_value=state), patch.object(helper, 'write_state', side_effect=lambda value:events.append('persist')), patch.object(helper, 'guest', side_effect=lambda *args:events.append('pair') or {'status':True}):
            helper.dispatch({'op':'pair','id':SID,'pin':'1234'})
        self.assertEqual(events,['persist','pair'])
        self.assertTrue(state['paired'])

    def test_failed_pair_cannot_retry_into_second_client(self):
        with patch.object(helper, 'read_state', return_value={'id':SID,'paired':True}), patch.object(helper, 'guest') as guest:
            with self.assertRaises(RuntimeError):
                helper.dispatch({'op':'pair','id':SID,'pin':'1234'})
            guest.assert_not_called()

    def test_unknown_operations_never_run_a_command(self):
        with patch.object(helper, 'run') as run:
            with self.assertRaises(RuntimeError):
                helper.dispatch({'op':'exec','command':'id'})
            run.assert_not_called()

    def test_stop_checks_health_after_verified_discard(self):
        with tempfile.TemporaryDirectory() as directory:
            events = []
            with patch.object(helper, 'STATE', pathlib.Path(directory)/'missing'), patch.object(helper, 'recover', side_effect=lambda:events.append('clean')), patch.object(helper, 'doctor', side_effect=lambda:events.append('health')):
                helper.dispatch({'op':'stop','id':SID})
            self.assertEqual(events,['clean','health'])


if __name__ == '__main__':
    unittest.main()
