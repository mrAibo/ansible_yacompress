from __future__ import annotations

import importlib.util
import os
import tempfile
import time


MODULE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    'plugins', 'modules', 'archive_rotate.py',
)
SPEC = importlib.util.spec_from_file_location('archive_rotate', MODULE_PATH)
ARCHIVE_ROTATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ARCHIVE_ROTATE)


def test_selection_by_count_and_minimum():
    now = 1_000_000.0
    archives = [
        (now - 10, '/backup/a.tar.zst', 10),
        (now - 20, '/backup/b.tar.zst', 20),
        (now - 30, '/backup/c.tar.zst', 30),
        (now - 40, '/backup/d.tar.zst', 40),
    ]
    selected = ARCHIVE_ROTATE.select_removals(archives, 2, None, 1, now)
    assert [item[1] for item in selected] == ['/backup/c.tar.zst', '/backup/d.tar.zst']


def test_selection_by_age_preserves_minimum():
    now = 10 * 86400.0
    archives = [
        (0.0, '/backup/newest.tar.zst', 10),
        (0.0, '/backup/old.tar.zst', 20),
    ]
    selected = ARCHIVE_ROTATE.select_removals(archives, None, 1, 1, now)
    assert [item[1] for item in selected] == ['/backup/old.tar.zst']


def test_combined_policy_removes_when_either_limit_is_exceeded():
    now = 100 * 86400.0
    archives = [
        (now - 1, '/backup/a.tar.zst', 10),
        (now - 2, '/backup/b.tar.zst', 20),
        (now - 40 * 86400, '/backup/c.tar.zst', 30),
    ]
    selected = ARCHIVE_ROTATE.select_removals(archives, 10, 30, 1, now)
    assert [item[1] for item in selected] == ['/backup/c.tar.zst']


def test_find_archives_is_deterministic_and_skips_symlinks():
    with tempfile.TemporaryDirectory() as directory:
        older = os.path.join(directory, 'older.tar.gz')
        newer = os.path.join(directory, 'newer.tar.zst')
        ignored = os.path.join(directory, 'notes.txt')
        link = os.path.join(directory, 'linked.tar.gz')
        for path in (older, newer, ignored):
            with open(path, 'w', encoding='utf-8') as stream:
                stream.write(path)
        now = time.time()
        os.utime(older, (now - 20, now - 20))
        os.utime(newer, (now - 10, now - 10))
        os.symlink(older, link)

        found = ARCHIVE_ROTATE.find_archives(
            directory,
            ARCHIVE_ROTATE.DEFAULT_PATTERNS,
            recursive=False,
        )

        assert [os.path.basename(item[1]) for item in found] == [
            'newer.tar.zst', 'older.tar.gz',
        ]


if __name__ == '__main__':
    test_selection_by_count_and_minimum()
    test_selection_by_age_preserves_minimum()
    test_combined_policy_removes_when_either_limit_is_exceeded()
    test_find_archives_is_deterministic_and_skips_symlinks()
    print('archive_rotate tests passed')
