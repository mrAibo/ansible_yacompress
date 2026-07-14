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

module_path = Path(__file__).resolve().parents[1] / 'plugins/modules/archive_verify.py'
spec = importlib.util.spec_from_file_location('archive_verify', str(module_path))
archive_verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive_verify)


class FakeModule:
    def get_bin_path(self, name, required=False):
        return '/usr/bin/' + name


class ArchiveVerifyTests(unittest.TestCase):
    def setUp(self):
        self.module = FakeModule()

    def test_detects_supported_extensions(self):
        cases = {
            '/tmp/a.tar': 'tar',
            '/tmp/a.tar.gz': 'tar.gz',
            '/tmp/a.tgz': 'tar.gz',
            '/tmp/a.tar.bz2': 'tar.bz2',
            '/tmp/a.tar.xz': 'tar.xz',
            '/tmp/a.tar.zst': 'tar.zst',
            '/tmp/a.zip': 'zip',
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                self.assertEqual(archive_verify.detect_format(path), expected)

    def test_unknown_extension_returns_none(self):
        self.assertIsNone(archive_verify.detect_format('/tmp/archive.bin'))

    def test_tar_commands_use_explicit_decompressors(self):
        cases = {
            'tar.gz': ('gzip', 'tar+gzip'),
            'tar.bz2': ('bzip2', 'tar+bzip2'),
            'tar.xz': ('xz', 'tar+xz'),
            'tar.zst': ('zstd', 'tar+zstd'),
        }
        for archive_format, (program, backend) in cases.items():
            with self.subTest(archive_format=archive_format):
                command, actual_backend = archive_verify.verification_command(
                    self.module, '/tmp/archive', archive_format,
                )
                self.assertEqual(command, [
                    '/usr/bin/tar', '-I', '/usr/bin/' + program, '-tf', '/tmp/archive',
                ])
                self.assertEqual(actual_backend, backend)

    def test_plain_tar_command(self):
        command, backend = archive_verify.verification_command(
            self.module, '/tmp/archive.tar', 'tar',
        )
        self.assertEqual(command, ['/usr/bin/tar', '-tf', '/tmp/archive.tar'])
        self.assertEqual(backend, 'tar')

    def test_zip_command(self):
        command, backend = archive_verify.verification_command(
            self.module, '/tmp/archive.zip', 'zip',
        )
        self.assertEqual(command, ['/usr/bin/unzip', '-t', '/tmp/archive.zip'])
        self.assertEqual(backend, 'unzip')


if __name__ == '__main__':
    unittest.main(verbosity=2)
