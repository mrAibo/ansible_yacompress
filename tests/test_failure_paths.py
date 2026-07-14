#!/usr/bin/env python3

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

ansible = types.ModuleType('ansible')
module_utils = types.ModuleType('ansible.module_utils')
basic = types.ModuleType('ansible.module_utils.basic')
basic.AnsibleModule = object
sys.modules['ansible'] = ansible
sys.modules['ansible.module_utils'] = module_utils
sys.modules['ansible.module_utils.basic'] = basic

module_path = Path(__file__).resolve().parents[1] / 'multi_archive.py'
spec = importlib.util.spec_from_file_location('multi_archive_failure_tests', str(module_path))
multi_archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(multi_archive)


class ExitResult(Exception):
    def __init__(self, result):
        super().__init__()
        self.result = result


class FailResult(Exception):
    def __init__(self, result):
        super().__init__()
        self.result = result


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


@unittest.skipUnless(shutil.which('tar') and shutil.which('gzip'), 'tar and gzip are required')
class DestructiveFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.source / 'payload.txt').write_text('payload', encoding='utf-8')
        self.dest = self.root / 'archive.tar.gz'
        self.module = FakeModule()

    def tearDown(self):
        self.temp_dir.cleanup()

    def params(self):
        return {
            'source': str(self.source),
            'dest': str(self.dest),
            'format': 'tar.gz',
            'compression': 'gzip',
            'include': [],
            'exclude': [],
            'delete_source': True,
            'creates': None,
            'format_detected': 'tar.gz',
        }

    def test_archive_command_failure_preserves_source_and_existing_destination(self):
        self.dest.write_bytes(b'previous archive')

        with mock.patch.object(
            multi_archive,
            '_run',
            side_effect=FailResult({'msg': 'simulated archive command failure'}),
        ):
            with self.assertRaises(FailResult):
                multi_archive.archive(self.module, **self.params())

        self.assertTrue(self.source.exists())
        self.assertEqual(self.dest.read_bytes(), b'previous archive')

    def test_verification_failure_preserves_source_and_existing_destination(self):
        self.dest.write_bytes(b'previous archive')

        with mock.patch.object(
            multi_archive,
            '_verify_archive',
            side_effect=FailResult({'msg': 'simulated verification failure'}),
        ):
            with self.assertRaises(FailResult):
                multi_archive.archive(self.module, **self.params())

        self.assertTrue(self.source.exists())
        self.assertEqual(self.dest.read_bytes(), b'previous archive')

    def test_delete_failure_reports_created_archive_and_preserves_source(self):
        with mock.patch.object(
            multi_archive,
            '_delete',
            side_effect=OSError('simulated delete failure'),
        ):
            with self.assertRaises(FailResult) as failure:
                multi_archive.archive(self.module, **self.params())

        result = failure.exception.result
        self.assertTrue(result['changed'])
        self.assertIn('Archive was created but source could not be deleted', result['msg'])
        self.assertTrue(self.source.exists())
        self.assertTrue(self.dest.exists())
        subprocess.check_call(['gzip', '-t', str(self.dest)])


if __name__ == '__main__':
    unittest.main(verbosity=2)
