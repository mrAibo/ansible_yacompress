#!/usr/bin/python

# Copyright (c) 2024 Aleksej Voronin
# MIT License

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: multi_archive

short_description: Archives or unarchives files and directories with optional compression.

version_added: "1.1.8"

description:
    - Archives and unarchives files and directories.
    - Supports tar.gz, tar.bz2, and zip formats.
    - Uses pigz for parallel gzip compression when compression=pigz.
    - Includes/excludes specific files or patterns (archiving only).
    - Auto-detects archive format on unarchive.

options:
    source:
        description: Source file or directory to archive or unarchive.
        required: true
        type: str
    dest:
        description: Destination file or directory for the operation.
        required: true
        type: str
    format:
        description: Archive format. Optional on unarchive (auto-detected from extension).
        required: false
        type: str
        choices: ['tar.gz', 'tar.bz2', 'zip']
    compression:
        description: Compression for tar.gz. 'gzip' single-threaded, 'pigz' parallel, 'none' format default.
        required: false
        type: str
        choices: ['none', 'gzip', 'pigz']
        default: none
    state:
        description: archived = archive, unarchived = extract.
        required: true
        type: str
        choices: ['archived', 'unarchived']
    delete_source:
        description: Remove source after a successful operation.
        required: false
        default: false
        type: bool
    include:
        description: Only archive these files/patterns (archiving only).
        required: false
        type: list
        elements: str
    exclude:
        description: Skip these files/patterns (archiving only).
        required: false
        type: list
        elements: str

author:
    - Aleksej Voronin (@mrAibo)
'''

EXAMPLES = r'''
# Archive a directory with tar.gz using pigz
- name: Archive directory
  multi_archive:
    source: /path/to/directory
    dest: /path/to/archive.tar.gz
    format: tar.gz
    compression: pigz
    state: archived

# Unarchive with auto-detected format
- name: Unarchive
  multi_archive:
    source: /path/to/archive.tar.gz
    dest: /path/to/directory
    state: unarchived

# Archive excluding patterns
- name: Archive with excludes
  multi_archive:
    source: /path/to/source
    dest: /path/to/destination/exclude_specific.tar.gz
    format: tar.gz
    exclude:
      - "*.log"
      - "*.tmp"
    state: archived

# Archive only specific files
- name: Archive specific files
  multi_archive:
    source: /path/to/source
    dest: /path/to/destination/include_specific.tar.gz
    format: tar.gz
    include:
      - "important.txt"
      - "docs/"
    state: archived
'''

RETURN = r'''
original_source:
    description: Source path.
    type: str
    returned: always
    sample: '/path/to/directory'
destination:
    description: Destination path.
    type: str
    returned: always
    sample: '/path/to/archive.tar.gz'
compression_used:
    description: Compression method used.
    type: str
    returned: when relevant
    sample: 'pigz'
format_detected:
    description: Format detected on unarchive.
    type: str
    returned: on unarchive if format was auto-detected
    sample: 'tar.gz'
'''

import os
import shutil
from ansible.module_utils.basic import AnsibleModule


def _run(module, cmd):
    rc, out, err = module.run_command(cmd, check_rc=False)
    if rc != 0:
        module.fail_json(msg="Command failed: %s\n%s" % (' '.join(cmd), err or out))
    return out


def _delete(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def _ensure_parent(path):
    parent = os.path.dirname(path)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)


def _build_archive_command(source, dest, fmt, compression, include, exclude, module):
    if fmt == 'tar.gz':
        comp = ['-I', 'pigz'] if compression == 'pigz' else ['-z']
    elif fmt == 'tar.bz2':
        comp = ['-j']
    elif fmt == 'zip':
        comp = []
    else:
        module.fail_json(msg="Unsupported format: %s" % fmt)

    if fmt in ('tar.gz', 'tar.bz2'):
        cmd = ['tar'] + comp + ['-cf', dest]
        for p in exclude:
            cmd += ['--exclude', p]
        if include:
            base = source if os.path.isdir(source) else os.path.dirname(source)
            cmd += ['-C', base]
            for item in include:
                cmd.append(item if not item.startswith(source) else os.path.relpath(item, base))
        elif os.path.isdir(source):
            cmd += ['-C', os.path.dirname(source), os.path.basename(source)]
        else:
            cmd.append(source)
    else:  # zip
        cmd = ['zip', '-r', dest, source]
        for p in exclude:
            cmd += ['-x', p]
        for p in include:
            cmd += ['-i', p]
    return cmd


def _unarchive_command(source, dest, fmt):
    if fmt == 'zip':
        return ['unzip', '-o', source, '-d', dest]
    if fmt == 'tar.gz':
        return ['tar', '-xzf', source, '-C', dest]
    if fmt == 'tar.bz2':
        return ['tar', '-xjf', source, '-C', dest]
    return None


def detect_archive_format(source):
    if source.endswith('.zip'):
        return 'zip'
    if source.endswith('.tar.gz') or source.endswith('.tgz'):
        return 'tar.gz'
    if source.endswith('.tar.bz2') or source.endswith('.tbz'):
        return 'tar.bz2'
    return None


def archive(module, **params):
    source = params['source']
    dest = params['dest']
    _ensure_parent(dest)
    cmd = _build_archive_command(source, dest, params['format'], params['compression'],
                                 params['include'], params['exclude'], module)
    if module.check_mode:
        module.exit_json(changed=True, msg="(check mode) would archive %s -> %s" % (source, dest))
    _run(module, cmd)
    if params['delete_source']:
        _delete(source)
    module.exit_json(changed=True, msg="%s archived to %s" % (source, dest))


def unarchive(module, **params):
    source = params['source']
    dest = params['dest']
    fmt = params['format'] or detect_archive_format(source)
    if not fmt:
        module.fail_json(msg="Could not detect format for %s; set 'format' explicitly" % source)
    _ensure_parent(dest)
    cmd = _unarchive_command(source, dest, fmt)
    if module.check_mode:
        module.exit_json(changed=True, msg="(check mode) would unarchive %s -> %s" % (source, dest))
    _run(module, cmd)
    if params['delete_source']:
        _delete(source)
    module.exit_json(changed=True, msg="%s unarchived to %s" % (source, dest))


def main():
    module = AnsibleModule(
        argument_spec={
            'source': {'type': 'str', 'required': True},
            'dest': {'type': 'str', 'required': True},
            'format': {'type': 'str', 'required': False, 'default': None,
                       'choices': ['tar.gz', 'tar.bz2', 'zip']},
            'compression': {'type': 'str', 'required': False, 'default': 'none',
                            'choices': ['gzip', 'pigz', 'none']},
            'state': {'type': 'str', 'required': True, 'choices': ['archived', 'unarchived']},
            'delete_source': {'type': 'bool', 'required': False, 'default': False},
            'include': {'type': 'list', 'elements': 'str', 'default': []},
            'exclude': {'type': 'list', 'elements': 'str', 'default': []},
        },
        supports_check_mode=True,
    )

    if not module.params['format']:
        module.params['format'] = detect_archive_format(module.params['source'])

    if module.params['state'] == 'archived':
        archive(module, **module.params)
    else:
        unarchive(module, **module.params)


if __name__ == '__main__':
    main()
