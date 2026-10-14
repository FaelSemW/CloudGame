"""Native policy tests; real capture/cleanup is covered by native-host CI."""
import importlib.util
import os
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

if os.name == 'posix':
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'deploy'))
    import native_helper as native
else:
    native = None


@unittest.skipUnless(os.name == 'posix', 'Native Linux backend')
class NativeTests(unittest.TestCase):
    def test_namespace_policy_never_binds_owner_desktop_or_input_devices(self):
        account = types.SimpleNamespace(pw_uid=900, pw_gid=900)
        with patch.object(Path, 'glob', return_value=[]):
            arguments = native.sandbox(Path('/var/lib/cloudgame/native-volatile/test'), {'renderer': 'software'}, account)
        for flag in ('--unshare-user', '--unshare-pid', '--unshare-ipc', '--clearenv'):
            self.assertIn(flag, arguments)
        for forbidden in ('/dev/uinput', '/dev/uhid', '/dev/input', '/run/dbus', '/var/home', '/root', '/dev/dri/card0'):
            self.assertNotIn(forbidden, arguments)
        writable = [arguments[i + 2] for i, arg in enumerate(arguments) if arg == '--bind']
        self.assertEqual(writable, ['/run/user/900', '/home/player'])
        self.assertNotIn('qemu-system-x86_64', arguments)
        self.assertNotIn('virsh', arguments)

    def test_cleanup_cannot_delete_without_confirmed_tmpfs(self):
        with patch.object(native, 'network'), patch.object(native, 'volatile_mount', side_effect=RuntimeError('not tmpfs')), \
             patch.object(native.shutil, 'rmtree') as remove:
            with self.assertRaisesRegex(RuntimeError, 'not tmpfs'): native.recover()
            remove.assert_not_called()

    def test_unrecorded_network_blocks_reuse(self):
        with patch.object(native, 'network'), patch.object(native, 'volatile_mount'), \
             patch.object(Path, 'exists', return_value=False), patch.object(Path, 'iterdir', return_value=iter([])), \
             patch.object(native, 'run', return_value='cg-native'):
            with self.assertRaisesRegex(RuntimeError, 'Rede sem estado'): native.recover()
