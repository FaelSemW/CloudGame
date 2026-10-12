import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_cli', ROOT / 'tools/package_cli.py')
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)


class PackageTests(unittest.TestCase):
    def test_release_extracts_without_user_data(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch('sys.argv', [str(ROOT / 'dist/cloud-game.pyz')]):
                cli.unpack(Path(folder))
            self.assertTrue((Path(folder) / 'host/server.mjs').is_file())
            self.assertFalse((Path(folder) / 'data').exists())
            self.assertFalse((Path(folder) / 'third_party').exists())

    def test_modified_payload_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'bad.pyz'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('manifest.json', json.dumps({'host/server.mjs': '0' * 64}))
                z.writestr('payload/host/server.mjs', 'changed')
            with patch('sys.argv', [str(archive)]), self.assertRaisesRegex(RuntimeError, 'Integridade'):
                cli.unpack(Path(folder) / 'out')

    def test_traversal_is_rejected_before_writing(self):
        with tempfile.TemporaryDirectory() as folder:
            archive = Path(folder) / 'bad.pyz'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('manifest.json', json.dumps({'../outside': '0' * 64}))
            with patch('sys.argv', [str(archive)]), self.assertRaisesRegex(RuntimeError, 'Caminho'):
                cli.unpack(Path(folder) / 'out')
            self.assertFalse((Path(folder) / 'outside').exists())


if __name__ == '__main__':
    unittest.main()
