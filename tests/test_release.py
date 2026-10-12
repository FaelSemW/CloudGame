import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('release', Path(__file__).resolve().parents[1] / 'tools/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_requires_https_without_credentials(self):
        for url in ['http://example.org/v1', 'https://user:pass@example.org/v1',
                    'https://example.org/v1?token=secret', 'https://example.org/v1\ncommand']:
            with self.assertRaises(ValueError):
                release.installer(url, 'a' * 64)

    def test_installer_verifies_before_privilege(self):
        script = release.installer('https://example.org/releases/0.1', 'a' * 64)
        self.assertIn('https://example.org/releases/0.1/cloud-game.pyz', script)
        self.assertLess(script.index('sha256sum --check'), script.index('pkexec /usr/bin'))
        self.assertLess(script.index('" doctor'), script.index('pkexec /usr/bin'))
        self.assertNotIn('--lab', script)
        self.assertIn("--proto-redir '=https'", script)

    def test_rejects_invalid_digest(self):
        with self.assertRaises(ValueError):
            release.installer('https://example.org/v1', 'a' * 63 + ';')


if __name__ == '__main__':
    unittest.main()
