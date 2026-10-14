import importlib.util
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('setup_host', Path(__file__).resolve().parents[1] / 'deploy/setup_host.py')
wizard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wizard)


class SetupTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', 'Requires a real Unix controlling terminal')
    def test_prompt_uses_real_controlling_terminal(self):
        import pty
        import select
        import signal
        import time
        child, descriptor = pty.fork()
        if child == 0:
            try: os._exit(0 if wizard.ask('Confirm?') == 'sim' else 1)
            except BaseException: os._exit(2)
        finished = False
        try:
            self.assertTrue(select.select([descriptor], [], [], 5)[0])
            os.read(descriptor, 4096)
            os.write(descriptor, b'sim\n')
            for attempt in range(100):
                pid, status = os.waitpid(child, os.WNOHANG)
                if pid:
                    finished = True
                    self.assertEqual(os.waitstatus_to_exitcode(status), 0)
                    break
                time.sleep(0.02)
            self.assertTrue(finished, 'Interactive prompt did not finish')
        finally:
            if not finished:
                os.kill(child, signal.SIGKILL); os.waitpid(child, 0)
            os.close(descriptor)

    @unittest.skipUnless(os.name == 'posix', 'Unix permissions and fsync semantics')
    def test_saved_state_is_private_atomic_and_symlink_safe(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(wizard, 'ROOT', Path(directory)), \
             patch.object(wizard, 'STATE', Path(directory) / 'state.json'):
            wizard.save({'phase': 'reboot'})
            self.assertEqual(wizard.STATE.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(wizard.STATE.read_text())['phase'], 'reboot')
            other = Path(directory) / 'owner-data'; other.write_text('preserve')
            (Path(directory) / 'state.new').symlink_to(other)
            with self.assertRaises(OSError): wizard.save({'phase': 'changed'})
            self.assertEqual(other.read_text(), 'preserve')

    def test_same_boot_waits_without_reinstalling_packages(self):
        with patch.object(wizard, 'boot_id', return_value='boot1'), patch.object(wizard, 'offer_reboot') as offer, \
             patch.object(wizard, 'missing_packages') as missing:
            self.assertFalse(wizard.dependencies({'rebootBoot': 'boot1'}))
            offer.assert_called_once(); missing.assert_not_called()

    def test_next_boot_continues_when_dependencies_are_present(self):
        with patch.object(wizard, 'boot_id', return_value='boot2'), patch.object(wizard, 'missing_packages', return_value=[]), \
             patch.object(wizard, 'run') as run:
            self.assertTrue(wizard.dependencies({'rebootBoot': 'boot1'}))
            run.assert_not_called()

    def test_foreign_pending_deployment_is_preserved(self):
        state = {}
        with patch.object(wizard, 'boot_id', return_value='boot1'), patch.object(wizard, 'missing_packages', return_value=['qemu-img']), \
             patch.object(wizard.shutil, 'which', return_value='/usr/bin/rpm-ostree'), patch.object(wizard, 'save'), \
             patch.object(wizard, 'offer_reboot'), patch.object(wizard, 'run', return_value=json.dumps({'deployments': [{'booted': False}, {'booted': True}]})) as run:
            self.assertFalse(wizard.dependencies(state))
            self.assertEqual(state['rebootBoot'], 'boot1')
            self.assertEqual(run.call_count, 1)  # Read-only status; no package transaction.

    def test_layer_failure_does_not_record_success_or_reboot(self):
        state = {}
        with patch.object(wizard, 'boot_id', return_value='boot1'), patch.object(wizard, 'missing_packages', return_value=['qemu-img']), \
             patch.object(wizard.shutil, 'which', return_value='/usr/bin/rpm-ostree'), patch.object(wizard, 'save'), \
             patch.object(wizard, 'offer_reboot') as offer, \
             patch.object(wizard, 'run', side_effect=[json.dumps({'deployments': [{'booted': True}]}), RuntimeError('RPM failure')]):
            with self.assertRaisesRegex(RuntimeError, 'RPM failure'): wizard.dependencies(state)
            self.assertNotIn('rebootBoot', state); offer.assert_not_called()

    def test_successful_layer_records_reboot_before_prompt(self):
        state = {}; saved = []
        with patch.object(wizard, 'boot_id', return_value='boot1'), patch.object(wizard, 'missing_packages', return_value=['qemu-img']), \
             patch.object(wizard.shutil, 'which', return_value='/usr/bin/rpm-ostree'), \
             patch.object(wizard, 'save', side_effect=lambda value: saved.append(dict(value))), \
             patch.object(wizard, 'offer_reboot'), \
             patch.object(wizard, 'run', side_effect=[json.dumps({'deployments': [{'booted': True}]}), None]) as run:
            self.assertFalse(wizard.dependencies(state))
            self.assertEqual(saved[-1]['rebootBoot'], 'boot1')
            self.assertEqual(run.call_args.args, ('rpm-ostree', 'install', '--idempotent', '--allow-inactive', 'qemu-img'))

    def test_existing_tailnet_does_not_reset_preferences_or_serve(self):
        status = json.dumps({'BackendState': 'Running', 'Self': {'DNSName': 'pc.tail.ts.net.'}})
        with tempfile.TemporaryDirectory() as directory, patch.object(wizard, 'ROOT', Path(directory)), \
             patch.object(wizard, 'run', side_effect=[status, status, types.SimpleNamespace(returncode=0)]) as run:
            self.assertEqual(wizard.tailnet(), 'pc.tail.ts.net')
            self.assertFalse(any('up' in call.args or 'serve' in call.args for call in run.call_args_list))
            self.assertEqual(list(Path(directory).iterdir()), [])  # Probe keys discarded.

    def test_https_rejection_never_marks_network_ready(self):
        status = json.dumps({'BackendState': 'Running', 'Self': {'DNSName': 'pc.tail.ts.net'}})
        with tempfile.TemporaryDirectory() as directory, patch.object(wizard, 'ROOT', Path(directory)), \
             patch.object(wizard, 'run', side_effect=[status, status, types.SimpleNamespace(returncode=1)]), \
             patch.object(wizard, 'ask', return_value='q'):
            with self.assertRaisesRegex(RuntimeError, 'Progresso salvo'): wizard.tailnet()
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_failed_service_never_reports_completion(self):
        with patch.object(wizard, 'run', side_effect=RuntimeError('service failed')), \
             patch.object(wizard.urllib.request, 'urlopen') as http:
            with self.assertRaisesRegex(RuntimeError, 'service failed'): wizard.verify_host('pc.tail.ts.net')
            http.assert_not_called()
