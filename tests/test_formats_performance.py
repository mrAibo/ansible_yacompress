import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
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
spec = importlib.util.spec_from_file_location('multi_archive', str(module_path))
multi_archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multi_archive)


class ExitResult(Exception):
    def __init__(self, result):
        super().__init__()
        self.result = result


class FailResult(Exception):
    pass


class FakeModule:
    check_mode = False

    def get_bin_path(self, name, required=False):
        path = shutil.which(name)
        if required and not path:
            self.fail_json(msg='Missing executable: %s' % name)
        return path

    def run_command(self, cmd, check_rc=False, cwd=None):
        process = subprocess.run(
            cmd,
            cwd=cwd,
            universal_newlines=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return process.returncode, process.stdout, process.stderr

    def atomic_move(self, source, dest):
        os.replace(source, dest)

    def exit_json(self, **kwargs):
        raise ExitResult(kwargs)

    def fail_json(self, **kwargs):
        raise FailResult(kwargs)


def call(function, module, **params):
    try:
        function(module, **params)
    except ExitResult as result:
        return result.result
    raise AssertionError('module did not return')


@unittest.skipUnless(shutil.which('tar'), 'tar is required')
class FormatPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'data.txt').write_text('compress me\n' * 2000, encoding='utf-8')
        self.module = FakeModule()

    def tearDown(self):
        self.temp.cleanup()

    def params(self, dest, fmt, **overrides):
        values = {
            'source': str(self.source),
            'dest': str(dest),
            'format': fmt,
            'compression': 'none',
            'compression_level': None,
            'threads': 'auto',
            'verify_archive': True,
            'include': [],
            'exclude': [],
            'delete_source': False,
            'creates': None,
            'format_detected': fmt,
        }
        values.update(overrides)
        return values

    def test_new_format_detection(self):
        self.assertEqual(multi_archive.detect_archive_format('a.tar'), 'tar')
        self.assertEqual(multi_archive.detect_archive_format('a.txz'), 'tar.xz')
        self.assertEqual(multi_archive.detect_archive_format('a.tzst'), 'tar.zst')

    def test_plain_tar_metrics_and_verification(self):
        archive = self.root / 'data.tar'
        result = call(multi_archive.archive, self.module, **self.params(archive, 'tar'))
        self.assertEqual(result['compression_used'], 'none')
        self.assertGreater(result['source_bytes'], 0)
        self.assertGreater(result['archive_bytes'], 0)
        self.assertGreaterEqual(result['elapsed_seconds'], 0)
        self.assertIn('compression_ratio', result)
        subprocess.check_call(['tar', '-tf', str(archive)], stdout=subprocess.DEVNULL)

    @unittest.skipUnless(shutil.which('xz'), 'xz is required')
    def test_xz_level_and_threads(self):
        archive = self.root / 'data.tar.xz'
        result = call(
            multi_archive.archive,
            self.module,
            **self.params(archive, 'tar.xz', compression_level=1, threads=1)
        )
        self.assertEqual(result['compression_used'], 'xz')
        self.assertEqual(result['threads_used'], 1)
        self.assertEqual(result['compression_level_used'], 1)
        subprocess.check_call(['tar', '-tf', str(archive)], stdout=subprocess.DEVNULL)

    @unittest.skipUnless(shutil.which('zstd'), 'zstd is required')
    def test_zstd_level_and_auto_threads(self):
        archive = self.root / 'data.tar.zst'
        result = call(
            multi_archive.archive,
            self.module,
            **self.params(archive, 'tar.zst', compression_level=3)
        )
        self.assertEqual(result['compression_used'], 'zstd')
        self.assertEqual(result['threads_used'], 'auto')
        subprocess.check_call(['tar', '-tf', str(archive)], stdout=subprocess.DEVNULL)

    def test_invalid_level_and_threads_are_rejected(self):
        with self.assertRaises(FailResult):
            multi_archive._compressor(self.module, 'tar.gz', 'gzip', 10, 'auto')
        with self.assertRaises(FailResult):
            multi_archive._compressor(self.module, 'tar', 'none', None, 2)
        with self.assertRaises(FailResult):
            multi_archive._normalize_threads(self.module, 0)

    @unittest.skipUnless(shutil.which('pigz'), 'pigz is required')
    def test_pigz_explicit_threads_and_level(self):
        command, used, threads, archive_cwd = multi_archive._build_archive_command(
            self.module,
            str(self.source),
            str(self.root / 'data.tar.gz'),
            'tar.gz',
            'pigz',
            [],
            [],
            3,
            2,
        )
        self.assertEqual(used, 'pigz')
        self.assertEqual(threads, 2)
        self.assertIsNone(archive_cwd)
        compressor = command[command.index('-I') + 1]
        self.assertIn('-p 2', compressor)
        self.assertIn('-3', compressor)


if __name__ == '__main__':
    unittest.main(verbosity=2)
