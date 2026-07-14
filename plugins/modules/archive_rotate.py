# Copyright: (c) 2026 Aleksej Voronin
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r'''
---
module: archive_rotate
short_description: Rotate archive files by count and age
version_added: "1.6.0"
description:
  - Removes old archive files from one directory according to explicit count and age limits.
  - Only regular files matching the configured patterns are considered.
  - Symbolic links are never followed or removed.
options:
  directory:
    description: Directory containing archives to rotate.
    type: path
    required: true
  patterns:
    description: Filename glob patterns to include.
    type: list
    elements: str
    default:
      - '*.tar'
      - '*.tar.gz'
      - '*.tgz'
      - '*.tar.bz2'
      - '*.tbz2'
      - '*.tar.xz'
      - '*.txz'
      - '*.tar.zst'
      - '*.zip'
  keep_last:
    description:
      - Maximum number of newest matching archives to retain.
      - Files beyond this limit become removal candidates.
    type: int
  max_age_days:
    description: Matching archives older than this many days become removal candidates.
    type: float
  min_keep:
    description: Minimum number of newest matching archives preserved regardless of other limits.
    type: int
    default: 1
  recursive:
    description: Search subdirectories recursively.
    type: bool
    default: false
attributes:
  check_mode:
    description: Reports files that would be removed without changing the filesystem.
    support: full
  diff_mode:
    description: Diff mode is not supported.
    support: none
author:
  - Aleksej Voronin (@mrAibo)
'''

EXAMPLES = r'''
- name: Keep the ten newest archives
  mraibo.yacompress.archive_rotate:
    directory: /srv/backups/app
    keep_last: 10

- name: Remove archives older than 30 days but always preserve two
  mraibo.yacompress.archive_rotate:
    directory: /srv/backups/app
    max_age_days: 30
    min_keep: 2

- name: Preview combined count and age rotation
  mraibo.yacompress.archive_rotate:
    directory: /srv/backups/app
    patterns:
      - 'app-*.tar.zst'
    keep_last: 14
    max_age_days: 45
  check_mode: true
'''

RETURN = r'''
matched:
  description: Matching regular archive files, newest first.
  type: list
  elements: str
  returned: always
kept:
  description: Files retained by the policy.
  type: list
  elements: str
  returned: always
removed:
  description: Files actually removed.
  type: list
  elements: str
  returned: always
planned_removals:
  description: Files selected for removal, including in Check Mode.
  type: list
  elements: str
  returned: always
bytes_reclaimed:
  description: Total size of files actually removed, or that would be removed in Check Mode.
  type: int
  returned: always
'''

import fnmatch
import os
import time

from ansible.module_utils.basic import AnsibleModule


DEFAULT_PATTERNS = [
    '*.tar', '*.tar.gz', '*.tgz', '*.tar.bz2', '*.tbz2',
    '*.tar.xz', '*.txz', '*.tar.zst', '*.zip',
]


def _matches(name, patterns):
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)


def find_archives(directory, patterns, recursive):
    root = os.path.realpath(directory)
    found = []
    for current, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if not os.path.islink(os.path.join(current, name))]
        for name in files:
            path = os.path.join(current, name)
            if not _matches(name, patterns) or os.path.islink(path) or not os.path.isfile(path):
                continue
            real_path = os.path.realpath(path)
            if os.path.commonpath((root, real_path)) != root:
                continue
            stat = os.stat(path, follow_symlinks=False)
            found.append((stat.st_mtime, real_path, stat.st_size))
        if not recursive:
            break
    found.sort(key=lambda item: (-item[0], item[1]))
    return found


def select_removals(archives, keep_last, max_age_days, min_keep, now):
    cutoff = None if max_age_days is None else now - (max_age_days * 86400.0)
    selected = []
    for index, archive in enumerate(archives):
        if index < min_keep:
            continue
        too_many = keep_last is not None and index >= keep_last
        too_old = cutoff is not None and archive[0] < cutoff
        if too_many or too_old:
            selected.append(archive)
    return selected


def main():
    module = AnsibleModule(
        argument_spec={
            'directory': {'type': 'path', 'required': True},
            'patterns': {'type': 'list', 'elements': 'str', 'default': DEFAULT_PATTERNS},
            'keep_last': {'type': 'int'},
            'max_age_days': {'type': 'float'},
            'min_keep': {'type': 'int', 'default': 1},
            'recursive': {'type': 'bool', 'default': False},
        },
        required_one_of=[['keep_last', 'max_age_days']],
        supports_check_mode=True,
    )

    directory = os.path.abspath(module.params['directory'])
    keep_last = module.params['keep_last']
    max_age_days = module.params['max_age_days']
    min_keep = module.params['min_keep']

    if not os.path.isdir(directory):
        module.fail_json(msg='Archive directory does not exist or is not a directory: %s' % directory)
    if keep_last is not None and keep_last < 0:
        module.fail_json(msg='keep_last must be zero or greater.')
    if max_age_days is not None and max_age_days < 0:
        module.fail_json(msg='max_age_days must be zero or greater.')
    if min_keep < 0:
        module.fail_json(msg='min_keep must be zero or greater.')
    if not module.params['patterns']:
        module.fail_json(msg='patterns must contain at least one glob pattern.')

    archives = find_archives(directory, module.params['patterns'], module.params['recursive'])
    planned = select_removals(archives, keep_last, max_age_days, min_keep, time.time())
    planned_paths = [item[1] for item in planned]
    planned_set = set(planned_paths)
    removed = []

    if not module.check_mode:
        for path in planned_paths:
            try:
                os.unlink(path)
            except OSError as exc:
                module.fail_json(
                    msg='Failed to remove archive %s: %s' % (path, exc),
                    changed=bool(removed),
                    matched=[item[1] for item in archives],
                    kept=[item[1] for item in archives if item[1] not in planned_set],
                    removed=removed,
                    planned_removals=planned_paths,
                )
            removed.append(path)

    module.exit_json(
        changed=bool(planned_paths),
        matched=[item[1] for item in archives],
        kept=[item[1] for item in archives if item[1] not in planned_set],
        removed=removed,
        planned_removals=planned_paths,
        bytes_reclaimed=sum(item[2] for item in planned),
    )


if __name__ == '__main__':
    main()
