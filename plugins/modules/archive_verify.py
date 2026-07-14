# Copyright: (c) 2026 Aleksej Voronin
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r'''
---
module: archive_verify
short_description: Verify an existing archive without extracting it
description:
  - Verifies an existing archive with native Linux archive tools.
  - Does not modify the archive or filesystem.
version_added: "1.6.0"
author:
  - Aleksej Voronin (@mrAibo)
options:
  path:
    description: Archive file to verify.
    type: path
    required: true
  format:
    description:
      - Archive format.
      - Detected from the file extension when omitted.
    type: str
    choices: [tar, tar.gz, tar.bz2, tar.xz, tar.zst, zip]
  fail_on_error:
    description:
      - Fail the task when verification fails.
      - When disabled, return C(valid=false) and the native tool error.
    type: bool
    default: true
attributes:
  check_mode:
    description: Performs the same read-only verification in check mode.
    support: full
  diff_mode:
    description: Diff mode is not applicable because the module never changes files.
    support: none
'''

EXAMPLES = r'''
- name: Verify a zstd archive
  mraibo.yacompress.archive_verify:
    path: /srv/backups/data.tar.zst

- name: Inspect validity without failing the play
  mraibo.yacompress.archive_verify:
    path: /srv/backups/data.zip
    fail_on_error: false
  register: archive_check
'''

RETURN = r'''
valid:
  description: Whether the archive passed native verification.
  type: bool
  returned: always
format:
  description: Detected or explicitly selected archive format.
  type: str
  returned: always
backend:
  description: Native verification tool used.
  type: str
  returned: always
archive_bytes:
  description: Archive size in bytes.
  type: int
  returned: always
elapsed_seconds:
  description: Verification duration in seconds.
  type: float
  returned: always
error:
  description: Native tool error when verification fails and C(fail_on_error=false).
  type: str
  returned: on failure without task failure
'''

import os
import time

from ansible.module_utils.basic import AnsibleModule


FORMATS = ('tar', 'tar.gz', 'tar.bz2', 'tar.xz', 'tar.zst', 'zip')
SUFFIXES = (
    ('.tar.zst', 'tar.zst'),
    ('.tar.bz2', 'tar.bz2'),
    ('.tar.gz', 'tar.gz'),
    ('.tgz', 'tar.gz'),
    ('.tar.xz', 'tar.xz'),
    ('.txz', 'tar.xz'),
    ('.tbz2', 'tar.bz2'),
    ('.zip', 'zip'),
    ('.tar', 'tar'),
)


def detect_format(path):
    lower = path.lower()
    for suffix, archive_format in SUFFIXES:
        if lower.endswith(suffix):
            return archive_format
    return None


def verification_command(module, path, archive_format):
    if archive_format == 'zip':
        unzip = module.get_bin_path('unzip', required=True)
        return [unzip, '-t', path], 'unzip'

    tar = module.get_bin_path('tar', required=True)
    compressors = {
        'tar.gz': 'gzip',
        'tar.bz2': 'bzip2',
        'tar.xz': 'xz',
        'tar.zst': 'zstd',
    }
    compressor = compressors.get(archive_format)
    if compressor:
        program = module.get_bin_path(compressor, required=True)
        return [tar, '-I', program, '-tf', path], 'tar+' + compressor
    return [tar, '-tf', path], 'tar'


def main():
    module = AnsibleModule(
        argument_spec={
            'path': {'type': 'path', 'required': True},
            'format': {'type': 'str', 'choices': list(FORMATS)},
            'fail_on_error': {'type': 'bool', 'default': True},
        },
        supports_check_mode=True,
    )

    path = os.path.abspath(module.params['path'])
    if not os.path.isfile(path):
        module.fail_json(msg='Archive does not exist or is not a regular file: %s' % path)

    archive_format = module.params['format'] or detect_format(path)
    if archive_format is None:
        module.fail_json(msg="Cannot detect archive format from extension; set 'format' explicitly.")

    command, backend = verification_command(module, path, archive_format)
    started = time.monotonic()
    rc, stdout, stderr = module.run_command(command)
    elapsed = round(max(time.monotonic() - started, 0.0), 6)
    result = {
        'changed': False,
        'valid': rc == 0,
        'format': archive_format,
        'backend': backend,
        'archive_bytes': os.path.getsize(path),
        'elapsed_seconds': elapsed,
    }

    if rc != 0:
        error = (stderr or stdout or 'archive verification failed').strip()
        if module.params['fail_on_error']:
            module.fail_json(msg='Archive verification failed: %s' % error, **result)
        result['error'] = error

    module.exit_json(**result)


if __name__ == '__main__':
    main()
