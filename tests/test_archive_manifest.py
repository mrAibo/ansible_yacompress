from __future__ import annotations

import importlib.util
import json
import os
import tempfile


MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'plugins', 'modules', 'archive_manifest.py',
)
SPEC = importlib.util.spec_from_file_location('archive_manifest', MODULE_PATH)
ARCHIVE_MANIFEST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ARCHIVE_MANIFEST)


def test_file_manifest_is_deterministic():
    with tempfile.TemporaryDirectory() as directory:
        source = os.path.join(directory, 'backup.tar.zst')
        manifest = os.path.join(directory, 'backup.manifest.json')
        with open(source, 'wb') as stream:
            stream.write(b'backup data')
        first = ARCHIVE_MANIFEST.build_manifest(source, manifest, True, ['*'], [])
        second = ARCHIVE_MANIFEST.build_manifest(source, manifest, True, ['*'], [])
        assert first == second
        assert first['source_type'] == 'file'
        assert first['entries'][0]['path'] == 'backup.tar.zst'
        assert len(first['entries'][0]['sha256']) == 64


def test_directory_manifest_filters_and_skips_symlinks():
    with tempfile.TemporaryDirectory() as directory:
        source = os.path.join(directory, 'source')
        os.mkdir(source)
        with open(os.path.join(source, 'keep.tar.zst'), 'w', encoding='utf-8') as stream:
            stream.write('keep')
        with open(os.path.join(source, 'ignore.tmp'), 'w', encoding='utf-8') as stream:
            stream.write('ignore')
        os.symlink(os.path.join(source, 'keep.tar.zst'), os.path.join(source, 'link.tar.zst'))
        data = ARCHIVE_MANIFEST.build_manifest(
            source,
            os.path.join(directory, 'manifest.json'),
            True,
            ['*.tar.zst'],
            ['ignore*'],
        )
        assert [entry['path'] for entry in data['entries']] == ['keep.tar.zst']


def test_verification_detects_changed_and_unexpected_files():
    with tempfile.TemporaryDirectory() as directory:
        source = os.path.join(directory, 'source')
        os.mkdir(source)
        original = os.path.join(source, 'one.txt')
        with open(original, 'w', encoding='utf-8') as stream:
            stream.write('one')
        manifest_path = os.path.join(directory, 'manifest.json')
        data = ARCHIVE_MANIFEST.build_manifest(source, manifest_path, True, ['*'], [])
        with open(original, 'w', encoding='utf-8') as stream:
            stream.write('changed')
        with open(os.path.join(source, 'two.txt'), 'w', encoding='utf-8') as stream:
            stream.write('two')
        mismatches = ARCHIVE_MANIFEST.verify_manifest(source, manifest_path, data)
        assert 'size changed: one.txt' in mismatches
        assert 'unexpected: two.txt' in mismatches


def test_atomic_write_and_load_round_trip():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'manifest.json')
        data = {
            'version': 1,
            'algorithm': 'sha256',
            'source_type': 'directory',
            'recursive': True,
            'patterns': ['*'],
            'exclude': [],
            'entries': [],
        }
        ARCHIVE_MANIFEST.atomic_write(path, ARCHIVE_MANIFEST.canonical_bytes(data))
        assert ARCHIVE_MANIFEST.load_manifest(path) == data
        assert not [name for name in os.listdir(directory) if name.startswith('.archive-manifest-')]


def test_unsafe_manifest_entry_is_rejected():
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'manifest.json')
        data = {
            'version': 1,
            'algorithm': 'sha256',
            'source_type': 'directory',
            'recursive': True,
            'patterns': ['*'],
            'exclude': [],
            'entries': [{'path': '../outside', 'size': 1, 'sha256': '0' * 64}],
        }
        with open(path, 'w', encoding='utf-8') as stream:
            json.dump(data, stream)
        try:
            ARCHIVE_MANIFEST.load_manifest(path)
        except ValueError as error:
            assert 'unsafe' in str(error)
        else:
            raise AssertionError('unsafe entry was accepted')


if __name__ == '__main__':
    test_file_manifest_is_deterministic()
    test_directory_manifest_filters_and_skips_symlinks()
    test_verification_detects_changed_and_unexpected_files()
    test_atomic_write_and_load_round_trip()
    test_unsafe_manifest_entry_is_rejected()
    print('archive_manifest tests passed')
