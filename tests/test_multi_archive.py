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


def call(function, module, **params):
    try:
        function(module, **params)
    except ExitResult as result:
        return result.result
    raise AssertionError('module did not return')


@unittest.skipUnless(shutil.which('tar'), 'tar is required')
class MultiArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        (self.source / 'sub').mkdir(parents=True)
        (self.source / 'one.txt').write_text('one', encoding='utf-8')
        (self.source / 'two.log').write_text('two', encoding='utf-8')
        (self.source / 'sub' / 'three.txt').write_text('three', encoding='utf-8')
        self.module = FakeModule()

    def tearDown(self):
        self.temp.cleanup()

    def params(self, dest, **overrides):
        values = {
            'source': str(self.source), 'dest': str(dest), 'format': 'tar.gz',
            'compression': 'gzip', 'compression_level': None, 'threads': 'auto',
            'verify_archive': False, 'include': [], 'exclude': [],
            'delete_source': False, 'creates': None, 'format_detected': 'tar.gz',
        }
        values.update(overrides)
        return values

    def test_format_detection(self):
        self.assertEqual(multi_archive.detect_archive_format('a.tar'), 'tar')
        self.assertEqual(multi_archive.detect_archive_format('a.tgz'), 'tar.gz')
        self.assertEqual(multi_archive.detect_archive_format('a.tbz2'), 'tar.bz2')
        self.assertEqual(multi_archive.detect_archive_format('a.txz'), 'tar.xz')
        self.assertEqual(multi_archive.detect_archive_format('a.tzst'), 'tar.zst')
        self.assertEqual(multi_archive.detect_archive_format('a.zip'), 'zip')
        self.assertIsNone(multi_archive.detect_archive_format('a.bin'))

    def test_include_globs_and_escape(self):
        selected = multi_archive._expand_includes(
            self.module, str(self.source), ['*.txt', 'sub/*.txt']
        )
        self.assertEqual(selected, ['one.txt', 'sub/three.txt'])
        with self.assertRaises(FailResult):
            multi_archive._expand_includes(self.module, str(self.source), ['../escape'])

    def test_tar_rewrite_include_and_metrics(self):
        archive = self.root / 'archives' / 'all.tar.gz'
        first = call(multi_archive.archive, self.module, **self.params(archive))
        self.assertTrue(first['changed'])
        self.assertGreater(first['source_bytes'], 0)
        (self.source / 'new.txt').write_text('new', encoding='utf-8')
        call(multi_archive.archive, self.module, **self.params(archive))
        members = subprocess.check_output(['tar', '-tzf', str(archive)], text=True).splitlines()
        self.assertIn('source/new.txt', members)
        included = self.root / 'archives' / 'included.tar.gz'
        call(
            multi_archive.archive, self.module,
            **self.params(included, include=['*.txt', 'sub/*.txt'])
        )
        members = subprocess.check_output(['tar', '-tzf', str(included)], text=True).splitlines()
        self.assertEqual(members, ['new.txt', 'one.txt', 'sub/three.txt'])

    @unittest.skipUnless(shutil.which('zip') and shutil.which('unzip'), 'zip is required')
    def test_zip_replacement_and_symlink_containment(self):
        archive = self.root / 'archives' / 'all.zip'
        params = self.params(
            archive, format='zip', compression='none', format_detected='zip'
        )
        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'secret.txt').write_text('secret', encoding='utf-8')
        (self.source / 'link').symlink_to(outside, target_is_directory=True)
        call(multi_archive.archive, self.module, **params)
        members = subprocess.check_output(['unzip', '-Z1', str(archive)], text=True).splitlines()
        self.assertIn('source/link', members)
        self.assertNotIn('source/link/secret.txt', members)
        (self.source / 'two.log').unlink()
        call(multi_archive.archive, self.module, **params)
        members = subprocess.check_output(['unzip', '-Z1', str(archive)], text=True).splitlines()
        self.assertNotIn('source/two.log', members)

    def test_check_mode_is_side_effect_free(self):
        archive = self.root / 'check' / 'all.tar.gz'
        result = call(multi_archive.archive, FakeModule(True), **self.params(archive))
        self.assertTrue(result['changed'])
        self.assertFalse(archive.parent.exists())

    def test_creates_guard(self):
        marker = self.root / 'marker'
        marker.write_text('done', encoding='utf-8')
        params = self.params(self.root / 'unused.tar.gz', creates=str(marker))
        with self.assertRaises(ExitResult) as result:
            multi_archive._skip_if_created(self.module, params)
        self.assertFalse(result.exception.result['changed'])
        self.assertTrue(result.exception.result['skipped'])

    def test_archive_and_unarchive_delete_source(self):
        source_file = self.root / 'delete.txt'
        source_file.write_text('delete after verification', encoding='utf-8')
        archive = self.root / 'archives' / 'delete.tar.gz'
        call(
            multi_archive.archive, self.module,
            **self.params(archive, source=str(source_file), delete_source=True)
        )
        self.assertFalse(source_file.exists())
        extract = self.root / 'extract'
        result = call(
            multi_archive.unarchive, self.module,
            source=str(archive), dest=str(extract), format='tar.gz',
            compression='none', include=[], exclude=[], delete_source=True,
            creates=None, format_detected='tar.gz'
        )
        self.assertTrue(result['changed'])
        self.assertTrue((extract / 'delete.txt').exists())
        self.assertFalse(archive.exists())

    @unittest.skipUnless(shutil.which('bzip2'), 'bzip2 is required')
    def test_bzip2_round_trip(self):
        archive = self.root / 'archives' / 'all.tar.bz2'
        call(
            multi_archive.archive, self.module,
            **self.params(archive, format='tar.bz2', compression='none', format_detected='tar.bz2')
        )
        extract = self.root / 'extract-bzip2'
        call(
            multi_archive.unarchive, self.module,
            source=str(archive), dest=str(extract), format='tar.bz2',
            compression='none', include=[], exclude=[], delete_source=False,
            creates=None, format_detected='tar.bz2'
        )
        self.assertTrue((extract / 'source' / 'one.txt').exists())

    def test_auto_compression_and_destination_validation(self):
        archive = self.root / 'archives' / 'auto.tar.gz'
        result = call(
            multi_archive.archive, self.module,
            **self.params(archive, compression='auto')
        )
        self.assertEqual(result['compression_used'], 'pigz' if shutil.which('pigz') else 'gzip')
        with self.assertRaises(FailResult):
            multi_archive._validate(
                self.module, str(self.source), str(self.source / 'bad.tar.gz'),
                'archived', [], []
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)
