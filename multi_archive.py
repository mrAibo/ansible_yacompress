#!/usr/bin/python

# Copyright (c) 2024 Aleksej Voronin
# GNU General Public License v3.0 (see LICENSE)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r"""
---
module: multi_archive
short_description: Creates and extracts archives with native Linux tools.
version_added: "1.3.0"
description:
  - Creates and extracts tar, tar.gz, tar.bz2, tar.xz, tar.zst, and zip archives.
  - Supports parallel gzip through pigz and native multithreading for xz and zstd.
  - Creates archives atomically and can verify them before replacing the destination.
options:
  source:
    type: path
    required: true
  dest:
    type: path
    required: true
  format:
    type: str
    choices: [tar, tar.gz, tar.bz2, tar.xz, tar.zst, zip]
  compression:
    type: str
    choices: [none, gzip, pigz, auto]
    default: none
    description:
      - Applies only to tar.gz.
      - auto prefers pigz and falls back to gzip.
  compression_level:
    type: int
    description: Compression level. Valid range depends on the selected format.
  threads:
    type: raw
    default: auto
    description:
      - auto uses the compressor default or all available threads where supported.
      - A positive integer limits pigz, xz, or zstd worker threads.
  verify_archive:
    type: bool
    default: false
    description: Verify the completed archive before replacing the destination.
  state:
    type: str
    required: true
    choices: [archived, unarchived]
  delete_source:
    type: bool
    default: false
  creates:
    type: path
  include:
    type: list
    elements: str
    default: []
  exclude:
    type: list
    elements: str
    default: []
author:
  - Aleksej Voronin (@mrAibo)
"""

EXAMPLES = r"""
- name: Fast zstd archive
  multi_archive:
    source: /srv/data
    dest: /backup/data.tar.zst
    state: archived
    compression_level: 3
    threads: auto
    verify_archive: true

- name: Limit pigz to four workers
  multi_archive:
    source: /srv/data
    dest: /backup/data.tar.gz
    state: archived
    compression: pigz
    threads: 4
    compression_level: 3
"""

RETURN = r"""
compression_used:
  type: str
  returned: state=archived
threads_used:
  type: raw
  returned: state=archived
compression_level_used:
  type: int
  returned: state=archived and compression_level was set
elapsed_seconds:
  type: float
  returned: state=archived
source_bytes:
  type: int
  returned: state=archived
archive_bytes:
  type: int
  returned: state=archived
compression_ratio:
  type: float
  returned: state=archived and source_bytes is non-zero
throughput_mib_per_second:
  type: float
  returned: state=archived and elapsed time is non-zero
"""

import glob
import os
import shlex
import shutil
import tempfile
import time

from ansible.module_utils.basic import AnsibleModule

FORMATS = ('tar', 'tar.gz', 'tar.bz2', 'tar.xz', 'tar.zst', 'zip')
SUFFIXES = {
    'tar': '.tar',
    'tar.gz': '.tar.gz',
    'tar.bz2': '.tar.bz2',
    'tar.xz': '.tar.xz',
    'tar.zst': '.tar.zst',
    'zip': '.zip',
}
LEVEL_RANGES = {
    'tar.gz': (1, 9),
    'tar.bz2': (1, 9),
    'tar.xz': (0, 9),
    'tar.zst': (1, 19),
    'zip': (0, 9),
}

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
    endings = (
        (('.tar.zst', '.tzst'), 'tar.zst'),
        (('.tar.bz2', '.tbz', '.tbz2'), 'tar.bz2'),
        (('.tar.xz', '.txz'), 'tar.xz'),
        (('.tar.gz', '.tgz'), 'tar.gz'),
        (('.tar',), 'tar'),
        (('.zip',), 'zip'),
    )
    for suffixes, fmt in endings:
        if lower.endswith(suffixes):
            return fmt
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
    traversed = os.path.isdir(source) and (include or not os.path.islink(source))
    if traversed and _is_within(_archive_destination_path(dest), os.path.realpath(source)):
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
            if any(relative == item or relative.startswith(item + os.sep) for item in selected_dirs):
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

def _normalize_threads(module, threads):
    if threads in (None, 'auto'):
        return 'auto'
    if isinstance(threads, str):
        try:
            threads = int(threads)
        except ValueError:
            module.fail_json(msg="threads must be 'auto' or a positive integer")
    if not isinstance(threads, int) or isinstance(threads, bool) or threads < 1:
        module.fail_json(msg="threads must be 'auto' or a positive integer")
    return threads

def _validate_level(module, fmt, level):
    if level is None:
        return
    if fmt == 'tar':
        module.fail_json(msg="compression_level does not apply to format=tar")
    minimum, maximum = LEVEL_RANGES[fmt]
    if level < minimum or level > maximum:
        module.fail_json(
            msg="compression_level for %s must be between %d and %d" % (fmt, minimum, maximum)
        )

def _compressor(module, fmt, compression, level, threads):
    threads = _normalize_threads(module, threads)
    _validate_level(module, fmt, level)
    if fmt == 'tar':
        if compression != 'none':
            module.fail_json(msg="compression only applies to format=tar.gz")
        if threads != 'auto':
            module.fail_json(msg="threads do not apply to format=tar")
        return [], 'none', 'auto'
    if fmt == 'tar.gz':
        if compression == 'auto':
            executable = module.get_bin_path('pigz', required=False)
            used = 'pigz' if executable else 'gzip'
            executable = executable or module.get_bin_path('gzip', required=True)
        elif compression == 'pigz':
            executable = module.get_bin_path('pigz', required=True)
            used = 'pigz'
        else:
            executable = module.get_bin_path('gzip', required=True)
            used = 'gzip'
        args = [executable]
        if level is not None:
            args.append('-%d' % level)
        if used == 'pigz' and threads != 'auto':
            args += ['-p', str(threads)]
        elif used == 'gzip' and threads != 'auto':
            module.fail_json(msg="explicit threads require pigz for format=tar.gz")
        return ['-I', ' '.join(shlex.quote(item) for item in args)], used, threads
    if compression != 'none':
        module.fail_json(msg="compression only applies to format=tar.gz")
    if fmt == 'tar.bz2':
        if threads != 'auto':
            module.fail_json(msg="threads are not supported for format=tar.bz2")
        executable = module.get_bin_path('bzip2', required=True)
        args = [executable] + ([] if level is None else ['-%d' % level])
        return ['-I', ' '.join(shlex.quote(item) for item in args)], 'bzip2', 'auto'
    if fmt == 'tar.xz':
        executable = module.get_bin_path('xz', required=True)
        args = [executable]
        args.append('-T0' if threads == 'auto' else '-T%d' % threads)
        if level is not None:
            args.append('-%d' % level)
        return ['-I', ' '.join(shlex.quote(item) for item in args)], 'xz', threads
    if fmt == 'tar.zst':
        executable = module.get_bin_path('zstd', required=True)
        args = [executable, '-q']
        args.append('-T0' if threads == 'auto' else '-T%d' % threads)
        if level is not None:
            args.append('-%d' % level)
        return ['-I', ' '.join(shlex.quote(item) for item in args)], 'zstd', threads
    if fmt == 'zip':
        if threads != 'auto':
            module.fail_json(msg="threads are not supported for format=zip")
        return [], 'zip', 'auto'
    module.fail_json(msg="Unsupported format: %s" % fmt)

def _build_archive_command(module, source, dest, fmt, compression, include, exclude,
                           compression_level=None, threads='auto'):
    source = os.path.abspath(source)
    selected = _expand_includes(module, source, include)
    comp, used, threads_used = _compressor(
        module, fmt, compression, compression_level, threads
    )
    if fmt != 'zip':
        tar = module.get_bin_path('tar', required=True)
        cmd = [tar] + comp + ['-cf', dest]
        for pattern in exclude:
            cmd += ['--exclude', pattern]
        if selected:
            cmd += ['-C', source, '--'] + selected
        else:
            cmd += ['-C', os.path.dirname(source), '--', os.path.basename(source) or '.']
        return cmd, used, threads_used, None
    zip_bin = module.get_bin_path('zip', required=True)
    cwd = source if selected else os.path.dirname(source)
    names = selected or [os.path.basename(source) or '.']
    names = [('./' + name) if name.startswith('-') else name for name in names]
    cmd = [zip_bin, '-q', '-y', '-r']
    if compression_level is not None:
        cmd.append('-%d' % compression_level)
    cmd += [dest] + names
    for pattern in exclude:
        cmd += ['-x', pattern]
    return cmd, used, threads_used, cwd

def _unarchive_command(module, source, dest, fmt):
    if fmt == 'zip':
        return [module.get_bin_path('unzip', required=True), '-o', source, '-d', dest]
    tar = module.get_bin_path('tar', required=True)
    if fmt == 'tar':
        return [tar, '-xf', source, '-C', dest]
    compressor = {
        'tar.gz': 'gzip',
        'tar.bz2': 'bzip2',
        'tar.xz': 'xz',
        'tar.zst': 'zstd',
    }.get(fmt)
    module.get_bin_path(compressor, required=True)
    return [tar, '-xf', source, '-C', dest]

def _temporary_archive(parent, fmt):
    directory = tempfile.mkdtemp(prefix='.multi_archive-', dir=parent)
    return directory, os.path.join(directory, 'archive' + SUFFIXES[fmt])

def _verify_archive(module, path, fmt, compression_used=None):
    if fmt == 'zip':
        _run(module, [module.get_bin_path('unzip', required=True), '-tqq', path])
        return
    _run(module, [module.get_bin_path('tar', required=True), '-tf', path])

def _source_size(path):
    if os.path.islink(path):
        return os.lstat(path).st_size
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        for name in files:
            candidate = os.path.join(root, name)
            try:
                total += os.lstat(candidate).st_size
            except OSError:
                pass
        for name in dirs:
            candidate = os.path.join(root, name)
            if os.path.islink(candidate):
                try:
                    total += os.lstat(candidate).st_size
                except OSError:
                    pass
    return total

def _skip_if_created(module, params):
    creates = params['creates']
    if creates and os.path.exists(creates):
        module.exit_json(
            changed=False,
            skipped=True,
            original_source=params['source'],
            destination=params['dest'],
            format_detected=params.get('format_detected'),
            msg="Skipped because creates path exists: %s" % creates,
        )

def archive(module, **params):
    source = params['source']
    dest = params['dest']
    fmt = params['format']
    level = params.get('compression_level')
    threads = params.get('threads', 'auto')
    verify = params.get('verify_archive', False) or params['delete_source']
    cmd, used, threads_used, cwd = _build_archive_command(
        module, source, dest, fmt, params['compression'], params['include'], params['exclude'],
        level, threads
    )
    if module.check_mode:
        module.exit_json(
            changed=True,
            original_source=source,
            destination=dest,
            compression_used=used,
            threads_used=threads_used,
            compression_level_used=level,
            format_detected=params['format_detected'],
            msg="(check mode) would archive %s -> %s" % (source, dest),
        )
    source_bytes = _source_size(source)
    started = time.monotonic()
    parent = _ensure_parent(dest)
    temporary_dir, temporary = _temporary_archive(parent, fmt)
    try:
        command = list(cmd)
        command[command.index(dest)] = temporary
        _run(module, command, cwd=cwd)
        if verify:
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
    elapsed = max(time.monotonic() - started, 0.000001)
    archive_bytes = os.path.getsize(dest)
    result = {
        'changed': True,
        'original_source': source,
        'destination': dest,
        'compression_used': used,
        'threads_used': threads_used,
        'compression_level_used': level,
        'format_detected': params['format_detected'],
        'elapsed_seconds': round(elapsed, 6),
        'source_bytes': source_bytes,
        'archive_bytes': archive_bytes,
        'throughput_mib_per_second': round(source_bytes / 1048576.0 / elapsed, 3),
        'msg': "%s archived to %s" % (source, dest),
    }
    if source_bytes:
        result['compression_ratio'] = round(archive_bytes / float(source_bytes), 6)
    module.exit_json(**result)

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
            'format': {'type': 'str', 'default': None, 'choices': list(FORMATS)},
            'compression': {
                'type': 'str', 'default': 'none',
                'choices': ['gzip', 'pigz', 'auto', 'none'],
            },
            'compression_level': {'type': 'int', 'default': None},
            'threads': {'type': 'raw', 'default': 'auto'},
            'verify_archive': {'type': 'bool', 'default': False},
            'state': {'type': 'str', 'required': True, 'choices': ['archived', 'unarchived']},
            'delete_source': {'type': 'bool', 'default': False},
            'creates': {'type': 'path', 'default': None},
            'include': {'type': 'list', 'elements': 'str', 'default': []},
            'exclude': {'type': 'list', 'elements': 'str', 'default': []},
        },
        supports_check_mode=True,
    )
    params = module.params
    _skip_if_created(module, params)
    detected = params['format'] is None
    params['format'] = params['format'] or detect_archive_format(
        params['dest'] if params['state'] == 'archived' else params['source']
    )
    if not params['format']:
        module.fail_json(msg="Cannot detect format from extension; set 'format' explicitly.")
    params['format_detected'] = params['format'] if detected else None
    _validate(
        module, params['source'], params['dest'], params['state'],
        params['include'], params['exclude']
    )
    if params['state'] == 'archived':
        archive(module, **params)
    else:
        unarchive(module, **params)

if __name__ == '__main__':
    main()
