import importlib.util
import sys
import types
import unittest
from pathlib import Path

ansible = types.ModuleType('ansible')
module_utils = types.ModuleType('ansible.module_utils')
basic = types.ModuleType('ansible.module_utils.basic')
basic.AnsibleModule = object
sys.modules['ansible'] = ansible
sys.modules['ansible.module_utils'] = module_utils
sys.modules['ansible.module_utils.basic'] = basic

module_path = Path(__file__).resolve().parents[1] / 'multi_archive.py'
spec = importlib.util.spec_from_file_location('multi_archive_portable_read', str(module_path))
multi_archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multi_archive)


class FakeModule:
    def get_bin_path(self, name, required=False):
        return '/usr/bin/' + name


class PortableTarReadTests(unittest.TestCase):
    def setUp(self):
        self.module = FakeModule()

    def test_zstd_verification_uses_explicit_decompressor(self):
        calls = []
        original = multi_archive._run
        multi_archive._run = lambda module, command, cwd=None: calls.append(command)
        try:
            multi_archive._verify_archive(self.module, '/tmp/data.tar.zst', 'tar.zst')
        finally:
            multi_archive._run = original
        self.assertEqual(
            calls[0],
            ['/usr/bin/tar', '-I', '/usr/bin/zstd', '-tf', '/tmp/data.tar.zst'],
        )

    def test_xz_extraction_uses_explicit_decompressor(self):
        self.assertEqual(
            multi_archive._unarchive_command(
                self.module, '/tmp/data.tar.xz', '/tmp/out', 'tar.xz'
            ),
            ['/usr/bin/tar', '-I', '/usr/bin/xz', '-xf', '/tmp/data.tar.xz', '-C', '/tmp/out'],
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
