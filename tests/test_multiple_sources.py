#!/usr/bin/env python3

# Regression coverage for list-valued source handling.

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
    def __init__(self, result):
        super().__init__()
        self.result = result


class FakeModule:
    def __init__(self, check_mode=False):
        self.check_mode = check_mode

    def get_bin_path(self, name, required=False):
        path = shutil.which(name)
        if required and not path:
            self.fail_json(msg='Missing executable: %s' % name)
        return path

    def run_command(self, cmd, check_rc=False, cwd=None):
        process = subprocess.run(
            cmd, cwd=cwd, universal_newlines=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        return process.returncode, process.stdout, process.stderr

    def atomic_move(self, source, dest):
        os.replace(source, dest)

    def exit_json(self, **kwargs):
        raise ExitResult(kwargs)

    def fail_json(self, **kwargs):
        raise FailResult(kwargs)


def call_module(function, module, **params):
    try:
        function(module, **params)
    except ExitResult as result:
        return result.result
    raise AssertionError('Module function did not call exit_json')


@unittest.skipUnless(shutil.which('tar') and shutil.which('gzip'), 'tar and gzip are required')
class MultipleSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.first = self.root / 'config'
        self.second = self.root / 'data'
        self.first.mkdir()
        self.second.mkdir()
        (self.first / 'app.conf').write_text('config', encoding='utf-8')
        (self.second / 'payload.bin').write_bytes(b'data' * 1024)
        self.module = FakeModule()

    def tearDown(self):
        self.temp_dir.cleanup()

    def params(self, archive, **overrides):
        params = {
            'source': [str(self.first), str(self.second)],
            'dest': str(archive),
            'format': 'tar.gz',
            'compression': 'gzip',
            'compression_level': 1,
            'threads': 'auto',
            'verify_archive': True,
            'include': [],
            'exclude': [],
            'delete_source': False,
            'creates': None,
            'format_detected': 'tar.gz',
        }
        params.update(overrides)
        return params

    def test_multiple_sources_archive_structure_and_metrics(self):
        archive = self.root / 'archives' / 'bundle.tar.gz'
        multi_archive._validate(
            self.module, [str(self.first), str(self.second)], str(archive),
            'archived', [], [], 'tar.gz',
        )
        result = call_module(multi_archive.archive, self.module, **self.params(archive))
        members = subprocess.check_output(
            ['tar', '-tzf', str(archive)], universal_newlines=True,
        ).splitlines()
        self.assertIn('config/app.conf', members)
        self.assertIn('data/payload.bin', members)
        self.assertEqual(result['source_bytes'], 6 + 4096)
        self.assertEqual(result['original_source'], [str(self.first), str(self.second)])
        self.assertEqual(result['deleted_sources'], [])
        self.assertGreater(result['archive_bytes'], 0)

    def test_delete_source_removes_all_only_after_verified_archive(self):
        archive = self.root / 'archives' / 'delete.tar.gz'
        result = call_module(
            multi_archive.archive,
            self.module,
            **self.params(archive, delete_source=True, verify_archive=False),
        )
        self.assertTrue(archive.exists())
        self.assertFalse(self.first.exists())
        self.assertFalse(self.second.exists())
        self.assertEqual(
            result['deleted_sources'],
            [str(self.first.resolve()), str(self.second.resolve())],
        )
        subprocess.check_call(['tar', '-tzf', str(archive)], stdout=subprocess.DEVNULL)

    def test_rejects_duplicate_names_overlap_zip_and_include(self):
        duplicate_parent = self.root / 'other'
        duplicate = duplicate_parent / 'config'
        duplicate.mkdir(parents=True)
        with self.assertRaises(FailResult):
            multi_archive._validate(
                self.module, [str(self.first), str(duplicate)],
                str(self.root / 'duplicate.tar'), 'archived', [], [], 'tar',
            )
        child = self.first / 'nested'
        child.mkdir()
        with self.assertRaises(FailResult):
            multi_archive._validate(
                self.module, [str(self.first), str(child)],
                str(self.root / 'overlap.tar'), 'archived', [], [], 'tar',
            )
        with self.assertRaises(FailResult):
            multi_archive._validate(
                self.module, [str(self.first), str(self.second)],
                str(self.root / 'bundle.zip'), 'archived', [], [], 'zip',
            )
        with self.assertRaises(FailResult):
            multi_archive._validate(
                self.module, [str(self.first), str(self.second)],
                str(self.root / 'include.tar'), 'archived', ['*.conf'], [], 'tar',
            )

    def test_unarchive_rejects_multiple_archives(self):
        with self.assertRaises(FailResult):
            multi_archive._normalize_sources(
                self.module, ['first.tar', 'second.tar'], 'unarchived',
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)
