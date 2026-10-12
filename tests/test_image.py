import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

spec = importlib.util.spec_from_file_location('build_image', Path(__file__).resolve().parents[1] / 'deploy/build_image.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ImageTests(unittest.TestCase):
    def test_guest_seed_has_one_locked_non_administrative_player(self):
        seed = builder.configuration()
        self.assertEqual(len(seed['users']), 1)
        player = seed['users'][0]
        self.assertEqual((player['name'], player['uid']), ('player', 1000))
        self.assertTrue(player['lock_passwd'])
        self.assertFalse(player['sudo'])
        self.assertFalse(seed['ssh_pwauth'])
        self.assertTrue(seed['disable_root'])
        self.assertFalse(set(player['groups']) & {'sudo', 'wheel', 'docker', 'libvirt', 'disk'})
        self.assertTrue(all(f['permissions'] == '0600' and f['path'].startswith('/opt/cloud-game-image/') for f in seed['write_files']))

    def test_download_checks_content_and_refuses_overwrite(self):
        data = b'verified upstream data'
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'image'
            opener = Mock()
            opener.open.return_value = io.BytesIO(data)
            with patch.object(builder.urllib.request, 'build_opener', return_value=opener):
                builder.download('https://example.invalid/image', hashlib.sha256(data).hexdigest(), target)
            self.assertEqual(target.read_bytes(), data)
            opener.open.return_value = io.BytesIO(b'overwrite')
            with patch.object(builder.urllib.request, 'build_opener', return_value=opener), self.assertRaises(FileExistsError):
                builder.download('https://example.invalid/image', '0' * 64, target)
            self.assertEqual(target.read_bytes(), data)

    def test_bad_hash_and_cleartext_url_are_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'image'
            with self.assertRaises(RuntimeError):
                builder.download('http://example.invalid/image', '0' * 64, target)
            self.assertFalse(target.exists())
            opener = Mock(); opener.open.return_value = io.BytesIO(b'changed')
            with patch.object(builder.urllib.request, 'build_opener', return_value=opener), self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                builder.download('https://example.invalid/image', '0' * 64, target)


if __name__ == '__main__':
    unittest.main()
