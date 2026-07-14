#!/usr/bin/python

# Copyright (c) 2024 Aleksej Voronin
# GNU General Public License v3.0 (see LICENSE)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r'''
---
module: multi_archive

short_description: Archives or unarchives files and directories with optional parallel gzip compression.

version_added: "1.2.0"

description:
    - Archives and unarchives files and directories.
    - Supports tar.gz, tar.bz2, and zip formats.
    - Uses pigz for parallel gzip when compression=pigz or when compression=auto and pigz is available.
    - Includes or excludes specific files and patterns when archiving.
    - Auto-detects format from the destination extension when archiving and the source extension when unarchiving.
    - Creates archives atomically so a failed run does not overwrite a valid destination archive.

options:
    source:
        description: Source file or directory to archive, or archive to unarchive.
        required: true
        type: path
    dest:
        description: Destination archive file or extraction directory.
        required: true
        type: path
    format:
        description: Archive format. Auto-detected from O(dest) for archiving or O(source) for unarchiving when omitted.
        required: false
        type: str
        choices: ['tar.gz', 'tar.bz2', 'zip']
    compression:
        description:
            - Compression method for C(tar.gz).
            - C(auto) uses C(pigz) when available and falls back to C(gzip).
            - C(none) is retained as a compatibility alias for C(gzip).
            - Values other than C(none) are rejected for C(tar.bz2) and C(zip).
        required: false
        type: str
        choices: ['none', 'gzip', 'pigz', 'auto']
        default: none
    state:
        description: C(archived) creates an archive; C(unarchived) extracts one.
        required: true
        type: str
        choices: ['archived', 'unarchived']
    delete_source:
        description:
            - Remove the source only after a successful operation.
            - Newly created archives are verified before an archive source is deleted.
        required: false
        default: false
        type: bool
    creates:
        description: Skip the operation and report no change when this path already exists.
        required: false
        type: path
    include:
        description:
            - Only archive these paths or glob patterns.
            - Entries must be relative to a directory O(source) and must not escape it.
            - Applies only when O(state=archived).
        required: false
        type: list
        elements: str
        default: []
    exclude:
        description:
            - Skip these archive path patterns.
            - Applies only when O(state=archived).
        required: false
        type: list
        elements: str
        default: []

author:
    - Aleksej Voronin (@mrAibo)
'''

EXAMPLES = r'''
- name: Archive a directory with pigz
  multi_archive:
    source: /path/to/directory
    dest: /path/to/archive.tar.gz
    compression: pigz
    state: archived

- name: Prefer pigz and fall back to gzip
  multi_archive:
    source: /path/to/directory
    dest: /path/to/archive.tar.gz
    compression: auto
    state: archived

- name: Extract only once
  multi_archive:
    source: /path/to/archive.tar.gz
    dest: /path/to/directory
    creates: /path/to/directory/.installed
    state: unarchived

- name: Archive selected files
  multi_archive:
    source: /path/to/source
    dest: /path/to/archive.tar.gz
    include:
      - "*.txt"
      - "docs/**"
    exclude:
      - "*.tmp"
    state: archived
'''

RETURN = r'''
original_source:
    description: Source path.
    type: str
    returned: always
    sample: /path/to/directory
destination:
    description: Destination path.
    type: str
    returned: always
    sample: /path/to/archive.tar.gz
compression_used:
    description: Compression method actually applied.
    type: str
    returned: when state=archived and the operation is not skipped
    sample: pigz
format_detected:
    description: Format detected from the source or destination extension.
    type: str
    returned: when format was auto-detected
    sample: tar.gz
'''

import glob
import os
import shutil
import tempfile

from ansible.module_utils.basic import AnsibleModule


def _run(module, cmd, cwd=None):
    rc, out, err = module.run_command(cmd, check_rc=False, cwd=cwd)
    if rc != 0:
        module.fail_json(
            msg="Command failed: %s\n%s" % (' '.join(cmd), err or out),
            rc=rc,
            stdout=out,
            stderr=err,
        )
    return out


def _delete(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


def _ensure_parent(path):
    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    return parent


def detect_archive_format(path):
    lower = path.lower()
    if lower.endswith('.zip'):
        return 'zip'
    if lower.endswith('.tar.gz') or lower.endswith('.tgz'):
        return 'tar.gz'
    if lower.endswith('.tar.bz2') or lower.endswith('.tbz') or lower.endswith('.tbz2'):
        return 'tar.bz2'
    return None


def _is_within(path, directory):
    path = os.path.abspath(path)
    directory = os.path.abspath(directory)
    try:
        return os.path.commonpath([path, directory]) == directory
    except ValueError:
        return False


def _archive_destination_path(dest):
    parent = os.path.realpath(os.path.dirname(os.path.abspath(dest)))
    return os.path.join(parent, os.path.basename(dest))


def _validate(module, source, dest, state, include, exclude):
    if not os.path.lexists(source):
        module.fail_json(msg="Source does not exist: %s" % source)

    if state == 'unarchived':
        if include or exclude:
            module.fail_json(msg="include/exclude only apply when state=archived")
        if os.path.exists(dest) and not os.path.isdir(dest):
            module.fail_json(msg="Unarchive destination is not a directory: %s" % dest)
        return

    if os.path.isdir(dest):
        module.fail_json(msg="Archive destination is a directory: %s" % dest)
    if os.path.abspath(source) == os.path.abspath(dest):
        module.fail_json(msg="Source and destination must be different paths")
    source_is_traversed = os.path.isdir(source) and (include or not os.path.islink(source))
    if source_is_traversed and _is_within(_archive_destination_path(dest), os.path.realpath(source)):
        module.fail_json(msg="Archive destination must not be inside source directory: %s" % dest)
    if include and not os.path.isdir(source):
        module.fail_json(msg="include requires source to be a directory")


def _expand_includes(module, source, include):
    if not include:
        return []

    source = os.path.abspath(source)
    source_real = os.path.realpath(source)
    expanded = []
    selected_dirs = set()
    seen = set()
    for pattern in include:
        if os.path.isabs(pattern):
            module.fail_json(msg="include entries must be relative to source: %s" % pattern)
        normalized = os.path.normpath(pattern)
        if normalized == os.pardir or normalized.startswith(os.pardir + os.sep):
            module.fail_json(msg="include entry escapes source: %s" % pattern)

        matches = glob.glob(os.path.join(source, pattern), recursive=True)
        if not matches:
            module.fail_json(msg="include entry matched nothing: %s" % pattern)
        for match in sorted(matches):
            match = os.path.abspath(match)
            if not _is_within(match, source):
                module.fail_json(msg="include entry escapes source: %s" % pattern)
            if not os.path.islink(match) and not _is_within(os.path.realpath(match), source_real):
                module.fail_json(msg="include entry resolves outside source: %s" % pattern)

            relative = os.path.relpath(match, source)
            if any(
                relative == directory or relative.startswith(directory + os.sep)
                for directory in selected_dirs
            ):
                continue
            if os.path.isdir(match) and not os.path.islink(match):
                prefix = relative + os.sep
                expanded = [item for item in expanded if not item.startswith(prefix)]
                seen = set(expanded)
                selected_dirs.add(relative)
            if relative not in seen:
                seen.add(relative)
                expanded.append(relative)
    return expanded


def _resolve_compression(module, fmt, compression):
    if fmt != 'tar.gz':
        if compression != 'none':
            module.fail_json(
                msg="compression='%s' only applies to format=tar.gz (got '%s')." % (compression, fmt)
            )
        return None, 'bzip2' if fmt == 'tar.bz2' else 'zip'

    if compression == 'pigz':
        return module.get_bin_path('pigz', required=True), 'pigz'
    if compression == 'auto':
        pigz = module.get_bin_path('pigz', required=False)
        return (pigz, 'pigz') if pigz else (None, 'gzip')
    return None, 'gzip'


def _build_archive_command(module, source, dest, fmt, compression, include, exclude):
    source = os.path.abspath(source)
    selected = _expand_includes(module, source, include)
    compressor, used = _resolve_compression(module, fmt, compression)

    if fmt in ('tar.gz', 'tar.bz2'):
        tar = module.get_bin_path('tar', required=True)
        if fmt == 'tar.gz':
            comp = ['-I', compressor] if compressor else ['-z']
        else:
            module.get_bin_path('bzip2', required=True)
            comp = ['-j']
        cmd = [tar] + comp + ['-cf', dest]
        for pattern in exclude:
            cmd += ['--exclude', pattern]
        if selected:
            cmd += ['-C', source, '--'] + selected
        else:
            cmd += ['-C', os.path.dirname(source), '--', os.path.basename(source) or '.']
        return cmd, used, None

    zip_bin = module.get_bin_path('zip', required=True)
    if selected:
        cwd = source
        names = selected
    else:
        cwd = os.path.dirname(source)
        names = [os.path.basename(source) or '.']
    names = [('./' + name) if name.startswith('-') else name for name in names]
    cmd = [zip_bin, '-q', '-r', dest] + names
    for pattern in exclude:
        cmd += ['-x', pattern]
    return cmd, used, cwd


def _unarchive_command(module, source, dest, fmt):
    if fmt == 'zip':
        return [module.get_bin_path('unzip', required=True), '-o', source, '-d', dest]
    tar = module.get_bin_path('tar', required=True)
    if fmt == 'tar.gz':
        return [tar, '-xzf', source, '-C', dest]
    if fmt == 'tar.bz2':
        module.get_bin_path('bzip2', required=True)
        return [tar, '-xjf', source, '-C', dest]
    module.fail_json(msg="Unsupported format: %s" % fmt)


def _temporary_archive(parent, fmt):
    suffix = {'tar.gz': '.tar.gz', 'tar.bz2': '.tar.bz2', 'zip': '.zip'}[fmt]
    directory = tempfile.mkdtemp(prefix='.multi_archive-', dir=parent)
    return directory, os.path.join(directory, 'archive' + suffix)


def _verify_archive(module, path, fmt, compression_used):
    if fmt == 'zip':
        _run(module, [module.get_bin_path('zip', required=True), '-T', path])
    elif fmt == 'tar.gz':
        executable = 'pigz' if compression_used == 'pigz' else 'gzip'
        _run(module, [module.get_bin_path(executable, required=True), '-t', path])
    else:
        _run(module, [module.get_bin_path('bzip2', required=True), '-t', path])


def _skip_if_created(module, params):
    creates = params['creates']
    if creates and os.path.exists(creates):
        module.exit_json(
            changed=False,
            skipped=True,
            original_source=params['source'],
            destination=params['dest'],
            format_detected=params['format_detected'],
            msg="Skipped because creates path exists: %s" % creates,
        )


def archive(module, **params):
    source = params['source']
    dest = params['dest']
    fmt = params['format']
    cmd, used, cwd = _build_archive_command(
        module, source, dest, fmt, params['compression'], params['include'], params['exclude']
    )

    if module.check_mode:
        module.exit_json(
            changed=True,
            original_source=source,
            destination=dest,
            compression_used=used,
            format_detected=params['format_detected'],
            msg="(check mode) would archive %s -> %s" % (source, dest),
        )

    parent = _ensure_parent(dest)
    temporary_dir, temporary = _temporary_archive(parent, fmt)
    try:
        command = list(cmd)
        command[command.index(dest)] = temporary
        _run(module, command, cwd=cwd)
        if params['delete_source']:
            _verify_archive(module, temporary, fmt, used)
        try:
            module.atomic_move(temporary, dest)
        except Exception as exc:
            module.fail_json(msg="Could not replace destination archive: %s" % exc)
    finally:
        shutil.rmtree(temporary_dir, ignore_errors=True)

    if params['delete_source']:
        try:
            _delete(source)
        except OSError as exc:
            module.fail_json(
                changed=True,
                original_source=source,
                destination=dest,
                msg="Archive was created but source could not be deleted: %s" % exc,
            )

    module.exit_json(
        changed=True,
        original_source=source,
        destination=dest,
        compression_used=used,
        format_detected=params['format_detected'],
        msg="%s archived to %s" % (source, dest),
    )


def unarchive(module, **params):
    source = params['source']
    dest = params['dest']
    fmt = params['format']
    cmd = _unarchive_command(module, source, dest, fmt)

    if module.check_mode:
        module.exit_json(
            changed=True,
            original_source=source,
            destination=dest,
            format_detected=params['format_detected'],
            msg="(check mode) would unarchive %s -> %s" % (source, dest),
        )

    if not os.path.isdir(dest):
        os.makedirs(dest, exist_ok=True)
    _run(module, cmd)

    if params['delete_source']:
        try:
            _delete(source)
        except OSError as exc:
            module.fail_json(
                changed=True,
                original_source=source,
                destination=dest,
                msg="Archive was extracted but source could not be deleted: %s" % exc,
            )

    module.exit_json(
        changed=True,
        original_source=source,
        destination=dest,
        format_detected=params['format_detected'],
        msg="%s unarchived to %s" % (source, dest),
    )


def main():
    module = AnsibleModule(
        argument_spec={
            'source': {'type': 'path', 'required': True},
            'dest': {'type': 'path', 'required': True},
            'format': {
                'type': 'str',
                'required': False,
                'default': None,
                'choices': ['tar.gz', 'tar.bz2', 'zip'],
            },
            'compression': {
                'type': 'str',
                'required': False,
                'default': 'none',
                'choices': ['gzip', 'pigz', 'auto', 'none'],
            },
            'state': {'type': 'str', 'required': True, 'choices': ['archived', 'unarchived']},
            'delete_source': {'type': 'bool', 'required': False, 'default': False},
            'creates': {'type': 'path', 'required': False, 'default': None},
            'include': {'type': 'list', 'elements': 'str', 'default': []},
            'exclude': {'type': 'list', 'elements': 'str', 'default': []},
        },
        supports_check_mode=True,
    )

    params = module.params
    detected = params['format'] is None
    params['format'] = params['format'] or detect_archive_format(
        params['dest'] if params['state'] == 'archived' else params['source']
    )
    if not params['format']:
        module.fail_json(msg="Cannot detect format from extension; set 'format' explicitly.")
    params['format_detected'] = params['format'] if detected else None

    _skip_if_created(module, params)
    _validate(
        module,
        params['source'],
        params['dest'],
        params['state'],
        params['include'],
        params['exclude'],
    )

    if params['state'] == 'archived':
        archive(module, **params)
    else:
        unarchive(module, **params)


if __name__ == '__main__':
    main()
