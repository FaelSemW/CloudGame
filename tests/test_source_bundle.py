import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('source_bundle', Path(__file__).resolve().parents[1] / 'tools/source_bundle.py')
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


class SourceBundleTests(unittest.TestCase):
    def test_only_tracked_sources_and_notices_are_packaged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            (root / 'LICENSE').write_text('Example notice')
            (root / 'run.sh').write_text('#!/bin/sh\nexit 0\n')
            (root / 'private-token.txt').write_text('Must never be archived')
            subprocess.run(['git', '-C', str(root), 'add', 'LICENSE', 'run.sh'], check=True)
            subprocess.run(['git', '-C', str(root), 'update-index', '--chmod=+x', 'run.sh'], check=True)
            subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'source'], check=True)
            output = root / 'output.tar.gz'
            with patch.object(bundle, 'ROOT', root):
                bundle.bundle([], output, root / 'notices')
            with tarfile.open(output) as archive:
                self.assertEqual(set(archive.getnames()), {'cloudgame/LICENSE', 'cloudgame/run.sh', 'SOURCE-MANIFEST.json'})
                self.assertEqual(archive.getmember('cloudgame/run.sh').mode, 0o755)
                manifest = json.load(archive.extractfile('SOURCE-MANIFEST.json'))
                self.assertEqual(len(manifest['files']), 2)
            self.assertEqual((root / 'notices/cloudgame/LICENSE').read_text(), 'Example notice')
            with patch.object(bundle, 'ROOT', root), self.assertRaises(FileExistsError):
                bundle.bundle([], output, root / 'notices')


if __name__ == '__main__':
    unittest.main()
