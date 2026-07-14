#!/usr/bin/python

# Copyright (c) 2024 Aleksej Voronin
# GNU General Public License v3.0 (see LICENSE)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = r"""
---
module: multi_archive
short_description: Creates and extracts archives with native Linux tools
version_added: "1.4.0"
description:
  - Creates and extracts tar, tar.gz, tar.bz2, tar.xz, tar.zst, and zip archives.
  - Supports one source path or multiple source paths for TAR-family archive creation.
  - Supports parallel gzip through pigz and native multithreading for xz and zstd.
  - Creates archives atomically and can verify them before replacing the destination.
options:
  source:
    description:
      - Source path to archive, archive path to extract, or a list of source paths for TAR-family archive creation.
      - Multiple sources are stored under their unique base names.
    type: raw
    required: true
  dest:
    description: Destination archive file or extraction directory.
    type: path
    required: true
  format:
    description: Archive format, inferred from the relevant archive path when omitted.
    type: str
    choices: [tar, tar.gz, tar.bz2, tar.xz, tar.zst, zip]
  compression:
    description:
      - Compression executable selection for C(tar.gz).
      - C(auto) prefers C(pigz) and falls back to C(gzip).
    type: str
    choices: [none, gzip, pigz, auto]
    default: none
  compression_level:
    description: Compression level. The valid range depends on the selected format.
    type: int
  threads:
    description:
      - C(auto) uses the compressor default or all available workers where supported.
      - A positive integer limits C(pigz), C(xz), or C(zstd) worker threads.
    type: raw
    default: auto
  verify_archive:
    description: Verify the completed archive before replacing the destination.
    type: bool
    default: false
  sparse:
    description:
      - Enable GNU tar sparse-file detection while creating TAR-family archives.
      - Useful for virtual disk images, database files, and other files with holes.
    type: bool
    default: false
  state:
    description: Whether to create or extract an archive.
    type: str
    required: true
    choices: [archived, unarchived]
  delete_source:
    description:
      - Delete all sources only after successful archive creation and verification.
      - With multiple sources, deletion stops on the first error and reports deleted and remaining paths.
    type: bool
    default: false
  creates:
    description: Skip the operation when this path already exists.
    type: path
  include:
    description: Relative source paths or glob patterns to include while archiving a single directory source.
    type: list
    elements: str
    default: []
  exclude:
    description: Archive path patterns to exclude while archiving.
    type: list
    elements: str
    default: []
author:
  - Aleksej Voronin (@mrAibo)
"""

EXAMPLES = r"""
- name: Archive several application paths
  multi_archive:
    source:
      - /etc/myapp
      - /opt/myapp-data
      - /var/lib/myapp
    dest: /backup/myapp.tar.zst
    state: archived
    compression_level: 3
    threads: auto
    verify_archive: true

- name: Fast zstd archive
  multi_archive:
    source: /srv/data
    dest: /backup/data.tar.zst
    state: archived
    compression_level: 3
    threads: auto
"""

RETURN = r"""
original_source:
  description: Source path or source-path list supplied to the module.
  type: raw
  returned: always
destination:
  description: Destination path supplied to the module.
  type: str
  returned: always
compression_used:
  description: Native compressor used to create the archive.
  type: str
  returned: state=archived
threads_used:
  description: Thread setting applied to the selected compressor.
  type: raw
  returned: state=archived
sparse_used:
  description: Whether GNU tar sparse-file detection was enabled.
  type: bool
  returned: state=archived
compression_level_used:
  description: Compression level applied to the selected compressor.
  type: int
  returned: state=archived and compression_level was set
elapsed_seconds:
  description: Elapsed archive creation time in seconds.
  type: float
  returned: state=archived
source_bytes:
  description: Total source file payload size measured from filesystem metadata.
  type: int
  returned: state=archived
archive_bytes:
  description: Final archive file size.
  type: int
  returned: state=archived
compression_ratio:
  description: Archive size divided by source payload size.
  type: float
  returned: state=archived and source_bytes is non-zero
throughput_mib_per_second:
  description: Source payload size divided by elapsed archive creation time.
  type: float
  returned: state=archived and elapsed time is non-zero
deleted_sources:
  description: Source paths removed after successful verified archive creation.
  type: list
  elements: str
  returned: state=archived and delete_source=true
format_detected:
  description: Archive format inferred from the source or destination extension.
  type: str
  returned: when format was inferred
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
    'tar': '.tar', 'tar.gz': '.tar.gz', 'tar.bz2': '.tar.bz2',
    'tar.xz': '.tar.xz', 'tar.zst': '.tar.zst', 'zip': '.zip',
}
LEVEL_RANGES = {
    'tar.gz': (1, 9), 'tar.bz2': (1, 9), 'tar.xz': (0, 9),
    'tar.zst': (1, 19), 'zip': (0, 9),
}


def _run(module, cmd, cwd=None):
    rc, out, err = module.run_command(cmd, check_rc=False, cwd=cwd)
    if rc != 0:
        module.fail_json(
            msg="Command failed: %s\n%s" % (' '.join(cmd), err or out),
            rc=rc, stdout=out, stderr=err,
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


def _normalize_sources(module, source, state):
    if isinstance(source, (list, tuple)):
        sources = list(source)
    else:
        sources = [source]
    if not sources or any(not isinstance(item, str) or not item for item in sources):
        module.fail_json(msg="source must be a path or a non-empty list of paths")
    sources = [os.path.abspath(item) for item in sources]
    if state == 'unarchived' and len(sources) != 1:
        module.fail_json(msg="unarchived state requires exactly one source archive")
    return sources


def _is_within(path, directory):
    try:
        return os.path.commonpath([os.path.abspath(path), os.path.abspath(directory)]) == os.path.abspath(directory)
    except ValueError:
        return False


def _archive_destination_path(dest):
    parent = os.path.realpath(os.path.dirname(os.path.abspath(dest)))
    return os.path.join(parent, os.path.basename(dest))


def _validate(module, source, dest, state, include, exclude, fmt=None):
    sources = _normalize_sources(module, source, state)
    for item in sources:
        if not os.path.lexists(item):
            module.fail_json(msg="Source does not exist: %s" % item)
    if state == 'unarchived':
        if include or exclude:
            module.fail_json(msg="include/exclude only apply when state=archived")
        if os.path.exists(dest) and not os.path.isdir(dest):
            module.fail_json(msg="Unarchive destination is not a directory: %s" % dest)
        return sources
    if len(sources) > 1 and fmt == 'zip':
        module.fail_json(msg="multiple sources are supported only for TAR-family formats")
    if len(sources) > 1 and include:
        module.fail_json(msg="include is supported only with a single directory source")
    if os.path.isdir(dest):
        module.fail_json(msg="Archive destination is a directory: %s" % dest)
    destination = _archive_destination_path(dest)
    names = {}
    for item in sources:
        if os.path.abspath(item) == os.path.abspath(dest):
            module.fail_json(msg="Source and destination must be different paths")
        traversed = os.path.isdir(item) and (include or not os.path.islink(item))
        if traversed and _is_within(destination, os.path.realpath(item)):
            module.fail_json(msg="Archive destination must not be inside source directory: %s" % dest)
        name = os.path.basename(item.rstrip(os.sep)) or os.path.basename(item)
        if name in names:
            module.fail_json(msg="multiple sources must have unique base names: %s" % name)
        names[name] = item
    for index, left in enumerate(sources):
        left_real = os.path.realpath(left)
        for right in sources[index + 1:]:
            right_real = os.path.realpath(right)
            if _is_within(left_real, right_real) or _is_within(right_real, left_real):
                module.fail_json(msg="source paths must not overlap: %s and %s" % (left, right))
    if include and not os.path.isdir(sources[0]):
        module.fail_json(msg="include requires source to be a directory")
    return sources


def _expand_includes(module, source, include):
    if not include:
        return []
    source = os.path.abspath(source)
    source_real = os.path.realpath(source)
    expanded, selected_dirs, seen = [], set(), set()
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
        module.fail_json(msg="compression_level for %s must be between %d and %d" % (fmt, minimum, maximum))


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
            executable, used = module.get_bin_path('pigz', required=True), 'pigz'
        else:
            executable, used = module.get_bin_path('gzip', required=True), 'gzip'
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
        args = [executable, '-T0' if threads == 'auto' else '-T%d' % threads]
        if level is not None:
            args.append('-%d' % level)
        return ['-I', ' '.join(shlex.quote(item) for item in args)], 'xz', threads
    if fmt == 'tar.zst':
        executable = module.get_bin_path('zstd', required=True)
        args = [executable, '-q', '-T0' if threads == 'auto' else '-T%d' % threads]
        if level is not None:
            args.append('-%d' % level)
        return ['-I', ' '.join(shlex.quote(item) for item in args)], 'zstd', threads
    if fmt == 'zip':
        if threads != 'auto':
            module.fail_json(msg="threads are not supported for format=zip")
        return [], 'zip', 'auto'
    module.fail_json(msg="Unsupported format: %s" % fmt)


def _build_archive_command(module, source, dest, fmt, compression, include, exclude,
                           compression_level=None, threads='auto', sparse=False):
    sources = source if isinstance(source, list) else [source]
    sources = [os.path.abspath(item) for item in sources]
    selected = _expand_includes(module, sources[0], include) if include else []
    comp, used, threads_used = _compressor(module, fmt, compression, compression_level, threads)
    if fmt != 'zip':
        tar = module.get_bin_path('tar', required=True)
        cmd = [tar] + comp + ['-cf', dest]
        if sparse:
            cmd.append('--sparse')
        for pattern in exclude:
            cmd += ['--exclude', pattern]
        if selected:
            cmd += ['-C', sources[0], '--'] + selected
        elif len(sources) == 1:
            item = sources[0]
            cmd += ['-C', os.path.dirname(item), '--', os.path.basename(item) or '.']
        else:
            for item in sources:
                name = os.path.basename(item) or '.'
                if name.startswith('-'):
                    name = './' + name
                cmd += ['-C', os.path.dirname(item), name]
        return cmd, used, threads_used, None
    source_path = sources[0]
    zip_bin = module.get_bin_path('zip', required=True)
    cwd = source_path if selected else os.path.dirname(source_path)
    names = selected or [os.path.basename(source_path) or '.']
    names = [('./' + name) if name.startswith('-') else name for name in names]
    cmd = [zip_bin, '-q', '-y', '-r']
    if compression_level is not None:
        cmd.append('-%d' % compression_level)
    cmd += [dest] + names
    for pattern in exclude:
        cmd += ['-x', pattern]
    return cmd, used, threads_used, cwd


def _tar_read_options(module, fmt):
    if fmt == 'tar':
        return []
    compressor = {
        'tar.gz': 'gzip', 'tar.bz2': 'bzip2',
        'tar.xz': 'xz', 'tar.zst': 'zstd',
    }[fmt]
    return ['-I', module.get_bin_path(compressor, required=True)]


def _unarchive_command(module, source, dest, fmt):
    if fmt == 'zip':
        return [module.get_bin_path('unzip', required=True), '-o', source, '-d', dest]
    tar = module.get_bin_path('tar', required=True)
    return [tar] + _tar_read_options(module, fmt) + ['-xf', source, '-C', dest]


def _validate_sparse(module, state, fmt, sparse):
    if not sparse:
        return
    if state != 'archived':
        module.fail_json(msg="sparse applies only when state=archived")
    if fmt == 'zip':
        module.fail_json(msg="sparse is supported only for TAR-family formats")


def _temporary_archive(parent, fmt):
    directory = tempfile.mkdtemp(prefix='.multi_archive-', dir=parent)
    return directory, os.path.join(directory, 'archive' + SUFFIXES[fmt])


def _verify_archive(module, path, fmt, compression_used=None):
    if fmt == 'zip':
        _run(module, [module.get_bin_path('unzip', required=True), '-tqq', path])
    else:
        command = [module.get_bin_path('tar', required=True)]
        command += _tar_read_options(module, fmt) + ['-tf', path]
        _run(module, command)


def _source_size(path):
    if os.path.islink(path):
        return os.lstat(path).st_size
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
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
            changed=False, skipped=True, original_source=params['source'],
            destination=params['dest'], format_detected=params.get('format_detected'),
            msg="Skipped because creates path exists: %s" % creates,
        )


def archive(module, **params):
    sources = _normalize_sources(module, params['source'], 'archived')
    original_source = params['source']
    dest, fmt = params['dest'], params['format']
    level, threads = params.get('compression_level'), params.get('threads', 'auto')
    verify = params.get('verify_archive', False) or params['delete_source']
    cmd, used, threads_used, cwd = _build_archive_command(
        module, sources, dest, fmt, params['compression'], params['include'], params['exclude'],
        level, threads, params.get('sparse', False),
    )
    if module.check_mode:
        module.exit_json(
            changed=True, original_source=original_source, destination=dest,
            compression_used=used, threads_used=threads_used,
            compression_level_used=level, sparse_used=params.get('sparse', False),
            format_detected=params['format_detected'],
            msg="(check mode) would archive %s -> %s" % (original_source, dest),
        )
    source_bytes = sum(_source_size(item) for item in sources)
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
    deleted = []
    if params['delete_source']:
        for item in sources:
            try:
                _delete(item)
                deleted.append(item)
            except OSError as exc:
                module.fail_json(
                    changed=True, original_source=original_source, destination=dest,
                    deleted_sources=deleted,
                    remaining_sources=[path for path in sources if path not in deleted],
                    msg="Archive was created but source could not be deleted: %s" % exc,
                )
    elapsed = max(time.monotonic() - started, 0.000001)
    archive_bytes = os.path.getsize(dest)
    result = {
        'changed': True, 'original_source': original_source, 'destination': dest,
        'compression_used': used, 'threads_used': threads_used,
        'compression_level_used': level, 'sparse_used': params.get('sparse', False),
        'format_detected': params['format_detected'],
        'elapsed_seconds': round(elapsed, 6), 'source_bytes': source_bytes,
        'archive_bytes': archive_bytes,
        'throughput_mib_per_second': round(source_bytes / 1048576.0 / elapsed, 3),
        'deleted_sources': deleted,
        'msg': "%s archived to %s" % (original_source, dest),
    }
    if source_bytes:
        result['compression_ratio'] = round(archive_bytes / float(source_bytes), 6)
    module.exit_json(**result)


def unarchive(module, **params):
    source = _normalize_sources(module, params['source'], 'unarchived')[0]
    dest, fmt = params['dest'], params['format']
    cmd = _unarchive_command(module, source, dest, fmt)
    if module.check_mode:
        module.exit_json(
            changed=True, original_source=source, destination=dest,
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
                changed=True, original_source=source, destination=dest,
                msg="Archive was extracted but source could not be deleted: %s" % exc,
            )
    module.exit_json(
        changed=True, original_source=source, destination=dest,
        format_detected=params['format_detected'],
        msg="%s unarchived to %s" % (source, dest),
    )


def main():
    module = AnsibleModule(
        argument_spec={
            'source': {'type': 'raw', 'required': True},
            'dest': {'type': 'path', 'required': True},
            'format': {'type': 'str', 'default': None, 'choices': list(FORMATS)},
            'compression': {'type': 'str', 'default': 'none', 'choices': ['gzip', 'pigz', 'auto', 'none']},
            'compression_level': {'type': 'int', 'default': None},
            'threads': {'type': 'raw', 'default': 'auto'},
            'verify_archive': {'type': 'bool', 'default': False},
            'sparse': {'type': 'bool', 'default': False},
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
    sources = _normalize_sources(module, params['source'], params['state'])
    detected = params['format'] is None
    archive_path = params['dest'] if params['state'] == 'archived' else sources[0]
    params['format'] = params['format'] or detect_archive_format(archive_path)
    if not params['format']:
        module.fail_json(msg="Cannot detect format from extension; set 'format' explicitly.")
    params['format_detected'] = params['format'] if detected else None
    _validate_sparse(module, params['state'], params['format'], params['sparse'])
    _validate(
        module, params['source'], params['dest'], params['state'],
        params['include'], params['exclude'], params['format'],
    )
    if params['state'] == 'archived':
        archive(module, **params)
    else:
        unarchive(module, **params)


if __name__ == '__main__':
    main()
