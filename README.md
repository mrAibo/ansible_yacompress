# Multi Archive Ansible Module

`multi_archive.py` creates and extracts archives on a managed Linux host. Its main reason to exist is fast native compression through `pigz`, `zstd`, and `xz`; for ordinary extraction, consider `ansible.builtin.unarchive` first.

## Features

- `tar`, `tar.gz`, `tar.bz2`, `tar.xz`, `tar.zst`, and ZIP archives
- parallel gzip with `compression: pigz`
- automatic pigz fallback with `compression: auto`
- native multithreading for zstd and xz
- optional thread limits and compression levels
- optional archive verification
- elapsed time, source/archive size, compression ratio, and throughput results
- include globs and exclude patterns while archiving
- automatic format detection from the archive extension
- check-mode support without filesystem changes
- explicit idempotency guard through `creates`
- atomic archive replacement
- optional source deletion after success; verification is mandatory before destructive deletion

## Installation

Place `multi_archive.py` in a `library/` directory next to the playbook, or set `ANSIBLE_LIBRARY` to the directory containing the module.

Required commands depend on the selected format: `tar`, `gzip` or `pigz`, `bzip2`, `xz`, `zstd`, and `zip`/`unzip`.

## Parameters

| Parameter | Required | Description |
|---|---:|---|
| `source` | yes | Source file/directory to archive, or archive to extract |
| `dest` | yes | Destination archive or extraction directory |
| `state` | yes | `archived` or `unarchived` |
| `format` | no | `tar`, `tar.gz`, `tar.bz2`, `tar.xz`, `tar.zst`, or `zip`; inferred when omitted |
| `compression` | no | For `tar.gz`: `gzip`, `pigz`, `auto`, or compatibility alias `none` |
| `compression_level` | no | gzip/bzip2 `1-9`, xz `0-9`, zstd `1-19`, ZIP `0-9` |
| `threads` | no | `auto` or a positive integer; explicit limits apply to pigz, xz, and zstd |
| `verify_archive` | no | Verify the completed archive before replacing `dest` |
| `creates` | no | Skip the operation when this path already exists |
| `delete_source` | no | Delete the source after a successful, verified operation |
| `include` | no | Relative paths or glob patterns to archive; directory sources only |
| `exclude` | no | Archive path patterns to exclude |

Without `creates`, an executed archive or extraction operation reports `changed: true`. The module does not pretend that rewriting an archive is idempotent.

## Examples

### Fast zstd archive

```yaml
- name: Create and verify a zstd archive
  multi_archive:
    source: /srv/data
    dest: /srv/backups/data.tar.zst
    state: archived
    compression_level: 3
    threads: auto
    verify_archive: true
```

For zstd, `threads: auto` passes the compressor's native all-available-CPU mode. For pigz, `auto` leaves thread selection to pigz. To limit server load, set an explicit positive integer.

### Limit pigz CPU use

```yaml
- name: Archive with four pigz workers
  multi_archive:
    source: /srv/data
    dest: /srv/backups/data.tar.gz
    state: archived
    compression: pigz
    compression_level: 3
    threads: 4
```

### Uncompressed tar

```yaml
- name: Bundle already-compressed media quickly
  multi_archive:
    source: /srv/media
    dest: /srv/backups/media.tar
    state: archived
```

### Extract once

```yaml
- name: Extract application bundle once
  multi_archive:
    source: /srv/releases/application.tar.zst
    dest: /opt/application
    creates: /opt/application/bin/application
    state: unarchived
```

For extraction that does not require this module's combined interface, prefer `ansible.builtin.unarchive`.

## Returned performance data

Successful archive creation returns:

- `compression_used`
- `threads_used`
- `compression_level_used`
- `elapsed_seconds`
- `source_bytes`
- `archive_bytes`
- `compression_ratio`
- `throughput_mib_per_second`

The source-size calculation reads filesystem metadata but does not hash or reread file contents. `verify_archive: true` performs an additional complete archive read.

## Safety behavior

- Check mode creates no files or directories.
- A new archive is written beside the destination and atomically replaces it only after the command succeeds.
- `dest` is rejected when it is inside a directory `source`.
- Include entries must stay inside `source`.
- ZIP archives preserve symbolic links instead of following them outside the source tree.
- `delete_source: true` never runs before successful archive verification.
- Invalid compression levels and unsupported thread settings fail explicitly.

## Testing

```bash
python3 tests/test_multi_archive.py
python3 tests/test_failure_paths.py
python3 tests/test_formats_performance.py
ANSIBLE_LIBRARY=. ansible-playbook -i localhost, -c local tests.yml
```
