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
spec = importlib.util.spec_from_file_location('multi_archive_sparse', str(module_path))
multi_archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multi_archive)


class FailJson(RuntimeError):
    pass


class FakeModule:
    def get_bin_path(self, name, required=False):
        return '/usr/bin/' + name

    def fail_json(self, **kwargs):
        raise FailJson(kwargs['msg'])


class SparseTests(unittest.TestCase):
    def setUp(self):
        self.module = FakeModule()

    def test_tar_command_enables_sparse_detection(self):
        command, used, threads, cwd = multi_archive._build_archive_command(
            self.module, '/tmp/disk.img', '/tmp/disk.tar.zst', 'tar.zst',
            'none', [], [], 1, 1, True,
        )
        self.assertIn('--sparse', command)
        self.assertEqual(used, 'zstd')
        self.assertIsNone(cwd)

    def test_zip_rejects_sparse_mode(self):
        with self.assertRaisesRegex(FailJson, 'TAR-family'):
            multi_archive._validate_sparse(self.module, 'archived', 'zip', True)

    def test_unarchive_rejects_sparse_mode(self):
        with self.assertRaisesRegex(FailJson, 'state=archived'):
            multi_archive._validate_sparse(self.module, 'unarchived', 'tar.zst', True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
