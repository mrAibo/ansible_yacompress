# Copyright: (c) 2026 Aleksej Voronin
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import annotations

DOCUMENTATION = r'''
---
module: archive_manifest
short_description: Create or verify deterministic SHA-256 manifests
version_added: "1.6.0"
description:
  - Creates an atomic JSON manifest for one regular file or a directory tree.
  - Verifies file sizes, SHA-256 digests, missing entries, and unexpected entries.
  - Symbolic links are never followed or included.
author:
  - Aleksej Voronin (@mrAibo)
options:
  source:
    description: Regular file or directory represented by the manifest.
    type: path
    required: true
  manifest:
    description: JSON manifest file to create or verify.
    type: path
    required: true
  state:
    description: Create/update the manifest or verify it.
    type: str
    choices: [present, verified]
    default: present
  recursive:
    description: Recurse into subdirectories when C(source) is a directory.
    type: bool
    default: true
  patterns:
    description: Relative path patterns included for directory manifests.
    type: list
    elements: str
    default: ['*']
  exclude:
    description: Relative path patterns excluded for directory manifests.
    type: list
    elements: str
    default: []
  fail_on_mismatch:
    description: Fail the task when C(state=verified) finds a mismatch.
    type: bool
    default: true
attributes:
  check_mode:
    description: Creation is previewed without writing; verification runs normally.
    support: full
  diff_mode:
    description: Diff output is not returned.
    support: none
'''

EXAMPLES = r'''
- name: Create a manifest for an archive
  mraibo.yacompress.archive_manifest:
    source: /srv/backups/app.tar.zst
    manifest: /srv/backups/app.tar.zst.manifest.json

- name: Verify an archive manifest
  mraibo.yacompress.archive_manifest:
    source: /srv/backups/app.tar.zst
    manifest: /srv/backups/app.tar.zst.manifest.json
    state: verified

- name: Manifest a backup directory
  mraibo.yacompress.archive_manifest:
    source: /srv/backups
    manifest: /srv/manifests/backups.json
    patterns: ['*.tar.zst', '*.zip']
    exclude: ['temporary-*']
'''

RETURN = r'''
valid:
  description: Whether verification succeeded.
  type: bool
  returned: when state is verified
entries_count:
  description: Number of manifest entries.
  type: int
  returned: always
total_bytes:
  description: Sum of represented file sizes.
  type: int
  returned: always
mismatches:
  description: Missing, unexpected, changed, or unsafe entry descriptions.
  type: list
  elements: str
  returned: when state is verified
manifest_sha256:
  description: SHA-256 digest of the canonical manifest content.
  type: str
  returned: always
'''

import fnmatch
import hashlib
import json
import os
import tempfile

from ansible.module_utils.basic import AnsibleModule


MANIFEST_VERSION = 1
BUFFER_SIZE = 1024 * 1024


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        while True:
            block = stream.read(BUFFER_SIZE)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def matches(path, patterns):
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def selected(path, patterns, exclude):
    return matches(path, patterns) and not matches(path, exclude)


def safe_relative_path(path):
    return (
        path not in ('', '.', '..')
        and not os.path.isabs(path)
        and '..' not in path.replace('\\', '/').split('/')
    )


def directory_files(source, recursive, patterns, exclude, manifest):
    files = []
    manifest_real = os.path.realpath(manifest)
    for root, directories, names in os.walk(source, followlinks=False):
        directories[:] = sorted(
            name for name in directories
            if not os.path.islink(os.path.join(root, name))
        )
        if not recursive and os.path.abspath(root) != source:
            directories[:] = []
            continue
        for name in sorted(names):
            path = os.path.join(root, name)
            if os.path.islink(path) or not os.path.isfile(path):
                continue
            if os.path.realpath(path) == manifest_real:
                continue
            relative = os.path.relpath(path, source).replace(os.sep, '/')
            if selected(relative, patterns, exclude):
                files.append((relative, path))
    return files


def source_files(source, recursive, patterns, exclude, manifest):
    if os.path.isfile(source) and not os.path.islink(source):
        return 'file', [(os.path.basename(source), source)]
    if os.path.isdir(source) and not os.path.islink(source):
        return 'directory', directory_files(source, recursive, patterns, exclude, manifest)
    raise ValueError('Source must be a regular file or directory and must not be a symbolic link: %s' % source)


def build_manifest(source, manifest, recursive, patterns, exclude):
    source_type, files = source_files(source, recursive, patterns, exclude, manifest)
    entries = []
    for relative, path in sorted(files):
        size = os.path.getsize(path)
        entries.append({'path': relative, 'size': size, 'sha256': sha256_file(path)})
    return {
        'version': MANIFEST_VERSION,
        'algorithm': 'sha256',
        'source_type': source_type,
        'recursive': bool(recursive),
        'patterns': list(patterns),
        'exclude': list(exclude),
        'entries': entries,
    }


def canonical_bytes(data):
    return (json.dumps(data, sort_keys=True, indent=2, ensure_ascii=False) + '\n').encode('utf-8')


def atomic_write(path, content):
    parent = os.path.dirname(path) or '.'
    if not os.path.isdir(parent):
        raise OSError('Manifest parent directory does not exist: %s' % parent)
    handle, temporary = tempfile.mkstemp(prefix='.archive-manifest-', dir=parent)
    try:
        with os.fdopen(handle, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def load_manifest(path):
    with open(path, 'r', encoding='utf-8') as stream:
        data = json.load(stream)
    if data.get('version') != MANIFEST_VERSION or data.get('algorithm') != 'sha256':
        raise ValueError('Unsupported manifest version or algorithm')
    if data.get('source_type') not in ('file', 'directory') or not isinstance(data.get('entries'), list):
        raise ValueError('Invalid manifest structure')
    for entry in data['entries']:
        if not isinstance(entry, dict) or not safe_relative_path(entry.get('path')):
            raise ValueError('Manifest contains an unsafe entry path')
        if not isinstance(entry.get('size'), int) or not isinstance(entry.get('sha256'), str):
            raise ValueError('Manifest contains an invalid entry')
    return data


def verify_manifest(source, manifest_path, data):
    patterns = data.get('patterns', ['*'])
    exclude = data.get('exclude', [])
    recursive = data.get('recursive', True)
    source_type, files = source_files(source, recursive, patterns, exclude, manifest_path)
    mismatches = []
    if source_type != data['source_type']:
        mismatches.append('source type changed: expected %s, found %s' % (data['source_type'], source_type))

    current = dict(files)
    expected = {entry['path']: entry for entry in data['entries']}
    for relative in sorted(expected):
        path = current.get(relative)
        if path is None:
            mismatches.append('missing: %s' % relative)
            continue
        entry = expected[relative]
        size = os.path.getsize(path)
        if size != entry['size']:
            mismatches.append('size changed: %s' % relative)
            continue
        if sha256_file(path) != entry['sha256']:
            mismatches.append('checksum changed: %s' % relative)
    for relative in sorted(set(current) - set(expected)):
        mismatches.append('unexpected: %s' % relative)
    return mismatches


def main():
    module = AnsibleModule(
        argument_spec={
            'source': {'type': 'path', 'required': True},
            'manifest': {'type': 'path', 'required': True},
            'state': {'type': 'str', 'choices': ['present', 'verified'], 'default': 'present'},
            'recursive': {'type': 'bool', 'default': True},
            'patterns': {'type': 'list', 'elements': 'str', 'default': ['*']},
            'exclude': {'type': 'list', 'elements': 'str', 'default': []},
            'fail_on_mismatch': {'type': 'bool', 'default': True},
        },
        supports_check_mode=True,
    )
    source = os.path.abspath(module.params['source'])
    manifest = os.path.abspath(module.params['manifest'])

    try:
        if module.params['state'] == 'present':
            data = build_manifest(
                source,
                manifest,
                module.params['recursive'],
                module.params['patterns'],
                module.params['exclude'],
            )
            content = canonical_bytes(data)
            old = None
            try:
                with open(manifest, 'rb') as stream:
                    old = stream.read()
            except FileNotFoundError:
                pass
            changed = old != content
            if changed and not module.check_mode:
                atomic_write(manifest, content)
            module.exit_json(
                changed=changed,
                entries_count=len(data['entries']),
                total_bytes=sum(entry['size'] for entry in data['entries']),
                manifest_sha256=hashlib.sha256(content).hexdigest(),
            )

        data = load_manifest(manifest)
        content = canonical_bytes(data)
        mismatches = verify_manifest(source, manifest, data)
        result = {
            'changed': False,
            'valid': not mismatches,
            'entries_count': len(data['entries']),
            'total_bytes': sum(entry['size'] for entry in data['entries']),
            'manifest_sha256': hashlib.sha256(content).hexdigest(),
            'mismatches': mismatches,
        }
        if mismatches and module.params['fail_on_mismatch']:
            module.fail_json(msg='Manifest verification failed', **result)
        module.exit_json(**result)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        module.fail_json(msg=str(error))


if __name__ == '__main__':
    main()
