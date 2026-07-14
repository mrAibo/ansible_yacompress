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


def call_module(function, module, **params):
    try:
        function(module, **params)
    except ExitResult as result:
        return result.result
    raise AssertionError('Module function did not call exit_json')


@unittest.skipUnless(shutil.which('tar'), 'tar is required')
class MultiArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.source = self.root / 'source'
        (self.source / 'sub').mkdir(parents=True)
        (self.source / 'one.txt').write_text('one', encoding='utf-8')
        (self.source / 'two.log').write_text('two', encoding='utf-8')
        (self.source / 'sub' / 'three.txt').write_text('three', encoding='utf-8')
        self.module = FakeModule()

    def tearDown(self):
        self.temp_dir.cleanup()

    def archive_params(self, dest, **overrides):
        params = {
            'source': str(self.source),
            'dest': str(dest),
            'format': 'tar.gz',
            'compression': 'gzip',
            'include': [],
            'exclude': [],
            'delete_source': False,
            'creates': None,
            'format_detected': 'tar.gz',
        }
        params.update(overrides)
        return params

    def test_format_detection(self):
        self.assertEqual(multi_archive.detect_archive_format('ARCHIVE.TGZ'), 'tar.gz')
        self.assertEqual(multi_archive.detect_archive_format('ARCHIVE.TBZ2'), 'tar.bz2')
        self.assertEqual(multi_archive.detect_archive_format('ARCHIVE.ZIP'), 'zip')
        self.assertIsNone(multi_archive.detect_archive_format('archive.tar'))

    def test_include_globs_and_path_escape(self):
        selected = multi_archive._expand_includes(
            self.module,
            str(self.source),
            ['*.txt', 'sub/*.txt'],
        )
        self.assertEqual(selected, ['one.txt', 'sub/three.txt'])

        with self.assertRaises(FailResult):
            multi_archive._expand_includes(self.module, str(self.source), ['../escape'])

        outside = self.root / 'outside'
        outside.mkdir()
        (outside / 'outside.txt').write_text('outside', encoding='utf-8')
        (self.source / 'link').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(FailResult):
            multi_archive._expand_includes(self.module, str(self.source), ['link/*.txt'])

    def test_tar_archive_rewrite_and_include(self):
        archive = self.root / 'archives' / 'all.tar.gz'
        result = call_module(
            multi_archive.archive,
            self.module,
            **self.archive_params(archive),
        )
        self.assertTrue(result['changed'])

        (self.source / 'new.txt').write_text('new', encoding='utf-8')
        result = call_module(
            multi_archive.archive,
            self.module,
            **self.archive_params(archive),
        )
        self.assertTrue(result['changed'])
        members = subprocess.check_output(
            ['tar', '-tzf', str(archive)],
            universal_newlines=True,
        ).splitlines()
        self.assertIn('source/new.txt', members)

        included = self.root / 'archives' / 'included.tar.gz'
        call_module(
            multi_archive.archive,
            self.module,
            **self.archive_params(included, include=['*.txt', 'sub/*.txt']),
        )
        members = subprocess.check_output(
            ['tar', '-tzf', str(included)],
            universal_newlines=True,
        ).splitlines()
        self.assertEqual(members, ['new.txt', 'one.txt', 'sub/three.txt'])

    @unittest.skipUnless(shutil.which('zip') and shutil.which('unzip'), 'zip and unzip are required')
    def test_zip_replacement_removes_stale_members(self):
        archive = self.root / 'archives' / 'all.zip'
        params = self.archive_params(
            archive,
            format='zip',
            compression='none',
            format_detected='zip',
        )
        call_module(multi_archive.archive, self.module, **params)
        (self.source / 'two.log').unlink()
        call_module(multi_archive.archive, self.module, **params)

        members = subprocess.check_output(
            ['unzip', '-Z1', str(archive)],
            universal_newlines=True,
        ).splitlines()
        self.assertNotIn('source/two.log', members)
        self.assertIn('source/one.txt', members)

    def test_check_mode_does_not_create_paths(self):
        archive = self.root / 'check-archive' / 'all.tar.gz'
        result = call_module(
            multi_archive.archive,
            FakeModule(check_mode=True),
            **self.archive_params(archive),
        )
        self.assertTrue(result['changed'])
        self.assertFalse(archive.parent.exists())

        real_archive = self.root / 'archives' / 'all.tar.gz'
        call_module(
            multi_archive.archive,
            self.module,
            **self.archive_params(real_archive),
        )
        extract = self.root / 'check-extract'
        result = call_module(
            multi_archive.unarchive,
            FakeModule(check_mode=True),
            source=str(real_archive),
            dest=str(extract),
            format='tar.gz',
            compression='none',
            include=[],
            exclude=[],
            delete_source=False,
            creates=None,
            format_detected='tar.gz',
        )
        self.assertTrue(result['changed'])
        self.assertFalse(extract.exists())

    def test_creates_guard_skips_before_execution(self):
        marker = self.root / 'marker'
        marker.write_text('done', encoding='utf-8')
        params = self.archive_params(self.root / 'unused.tar.gz', creates=str(marker))
        with self.assertRaises(ExitResult) as result:
            multi_archive._skip_if_created(self.module, params)
        self.assertFalse(result.exception.result['changed'])
        self.assertTrue(result.exception.result['skipped'])

    def test_unarchive_and_delete_source(self):
        archive = self.root / 'archives' / 'all.tar.gz'
        call_module(
            multi_archive.archive,
            self.module,
            **self.archive_params(archive),
        )
        extract = self.root / 'extract'
        result = call_module(
            multi_archive.unarchive,
            self.module,
            source=str(archive),
            dest=str(extract),
            format='tar.gz',
            compression='none',
            include=[],
            exclude=[],
            delete_source=True,
            creates=None,
            format_detected='tar.gz',
        )
        self.assertTrue(result['changed'])
        self.assertTrue((extract / 'source' / 'one.txt').exists())
        self.assertFalse(archive.exists())

    def test_archive_delete_source_after_verification(self):
        source_file = self.root / 'delete.txt'
        source_file.write_text('delete after verification', encoding='utf-8')
        archive = self.root / 'archives' / 'delete.tar.gz'
        result = call_module(
            multi_archive.archive,
            self.module,
            **self.archive_params(archive, source=str(source_file), delete_source=True),
        )
        self.assertTrue(result['changed'])
        self.assertFalse(source_file.exists())
        subprocess.check_call(['tar', '-tzf', str(archive)], stdout=subprocess.DEVNULL)

    @unittest.skipUnless(shutil.which('bzip2'), 'bzip2 is required')
    def test_bzip2_archive_and_extract(self):
        archive = self.root / 'archives' / 'all.tar.bz2'
        params = self.archive_params(
            archive,
            format='tar.bz2',
            compression='none',
            format_detected='tar.bz2',
        )
        call_module(multi_archive.archive, self.module, **params)
        extract = self.root / 'extract-bzip2'
        call_module(
            multi_archive.unarchive,
            self.module,
            source=str(archive),
            dest=str(extract),
            format='tar.bz2',
            compression='none',
            include=[],
            exclude=[],
            delete_source=False,
            creates=None,
            format_detected='tar.bz2',
        )
        self.assertTrue((extract / 'source' / 'one.txt').exists())

    def test_auto_compression_and_destination_validation(self):
        archive = self.root / 'archives' / 'auto.tar.gz'
        result = call_module(
            multi_archive.archive,
            self.module,
            **self.archive_params(archive, compression='auto'),
        )
        expected = 'pigz' if shutil.which('pigz') else 'gzip'
        self.assertEqual(result['compression_used'], expected)

        with self.assertRaises(FailResult):
            multi_archive._validate(
                self.module,
                str(self.source),
                str(self.source / 'bad.tar.gz'),
                'archived',
                [],
                [],
            )

        alias = self.root / 'source-alias'
        alias.symlink_to(self.source, target_is_directory=True)
        with self.assertRaises(FailResult):
            multi_archive._validate(
                self.module,
                str(self.source),
                str(alias / 'bad.tar.gz'),
                'archived',
                [],
                [],
            )


if __name__ == '__main__':
    unittest.main(verbosity=2)
