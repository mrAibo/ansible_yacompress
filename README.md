# YaCompress Ansible Collection

`mraibo.yacompress` creates and extracts archives on managed Linux hosts with native `tar`, `pigz`, `zstd`, `xz`, `bzip2`, and ZIP tools. Its purpose is fast, controllable Linux archiving with explicit safety guarantees. For ordinary extraction that does not need this combined interface, consider `ansible.builtin.unarchive` first.

## Features

- `tar`, `tar.gz`, `tar.bz2`, `tar.xz`, `tar.zst`, and ZIP archives
- one source path or multiple source paths for TAR-family archives
- parallel gzip with `compression: pigz`
- automatic pigz fallback with `compression: auto`
- native multithreading for zstd and xz
- optional thread limits and compression levels
- optional archive verification
- elapsed time, source/archive size, compression ratio, and throughput results
- include globs and exclude patterns with a single directory source
- automatic format detection from the archive extension
- check-mode support without filesystem changes
- explicit idempotency guard through `creates`
- atomic archive replacement
- source deletion only after successful verification
- official `ansible-test sanity` and integration coverage
- automated Ubuntu 24.04 and openSUSE Leap 15.6 validation

## Installation

Build and install the collection from a checkout:

```bash
ansible-galaxy collection build --output-path build
ansible-galaxy collection install build/mraibo-yacompress-1.4.0.tar.gz
```

Use the fully qualified collection name:

```yaml
- name: Create verified archive
  mraibo.yacompress.multi_archive:
    source: /srv/data
    dest: /srv/backups/data.tar.zst
    state: archived
    compression_level: 3
    threads: auto
    verify_archive: true
```

For legacy playbooks, the root `multi_archive.py` symlink can still be exposed through `ANSIBLE_LIBRARY`.

Required commands depend on the selected format: `tar`, `gzip` or `pigz`, `bzip2`, `xz`, `zstd`, and `zip`/`unzip`.

## Format selection

| Scenario | Suggested format |
|---|---|
| Frequent Linux backups | `tar.zst`, level 1–3 |
| Gzip compatibility with parallel compression | `tar.gz` with `compression: pigz` |
| Restrict shared-server CPU use | Set an explicit `threads` value |
| Compact long-term archives | `tar.xz` |
| JPEG, MP4, ZIP, and other already-compressed data | `tar` |
| Broad desktop/Windows exchange | ZIP |

These are starting points. Use the included benchmark suite on the actual target hardware before making performance claims or operational decisions.

## Parameters

| Parameter | Required | Description |
|---|---:|---|
| `source` | yes | One source path, an archive to extract, or a list of source paths for TAR-family archive creation |
| `dest` | yes | Destination archive or extraction directory |
| `state` | yes | `archived` or `unarchived` |
| `format` | no | `tar`, `tar.gz`, `tar.bz2`, `tar.xz`, `tar.zst`, or `zip`; inferred when omitted |
| `compression` | no | For `tar.gz`: `gzip`, `pigz`, `auto`, or compatibility alias `none` |
| `compression_level` | no | gzip/bzip2 `1-9`, xz `0-9`, zstd `1-19`, ZIP `0-9` |
| `threads` | no | `auto` or a positive integer; explicit limits apply to pigz, xz, and zstd |
| `verify_archive` | no | Verify the completed archive before replacing `dest` |
| `creates` | no | Skip the operation when this path already exists |
| `delete_source` | no | Delete all sources after a successful, verified operation |
| `include` | no | Relative paths or glob patterns; only with one directory source |
| `exclude` | no | Archive path patterns to exclude |

Without `creates`, an executed archive or extraction operation reports `changed: true`. The module does not pretend that rewriting an archive is idempotent.

## Examples

### Archive multiple paths

```yaml
- name: Archive application configuration and data
  mraibo.yacompress.multi_archive:
    source:
      - /etc/myapp
      - /opt/myapp-data
      - /var/lib/myapp
    dest: /srv/backups/myapp.tar.zst
    state: archived
    compression_level: 3
    threads: auto
    verify_archive: true
```

Each source is stored under its base name. Base names must be unique, source paths must not overlap, and `dest` must not be inside any source. Multiple sources are intentionally limited to TAR-family formats; ZIP lists are rejected to avoid surprising path layouts.

### Limit pigz CPU use

```yaml
- name: Archive with four pigz workers
  mraibo.yacompress.multi_archive:
    source: /srv/data
    dest: /srv/backups/data.tar.gz
    state: archived
    compression: pigz
    compression_level: 3
    threads: 4
```

For zstd, `threads: auto` selects its native all-available-CPU mode. For pigz, `auto` leaves worker selection to pigz. Set a positive integer to limit shared-server load.

### Uncompressed tar

```yaml
- name: Bundle already-compressed media quickly
  mraibo.yacompress.multi_archive:
    source: /srv/media
    dest: /srv/backups/media.tar
    state: archived
```

### Extract once

```yaml
- name: Extract application bundle once
  mraibo.yacompress.multi_archive:
    source: /srv/releases/application.tar.zst
    dest: /opt/application
    creates: /opt/application/bin/application
    state: unarchived
```

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
- `deleted_sources`

The source-size calculation reads filesystem metadata but does not hash or reread file contents. `verify_archive: true` performs an additional complete archive read.

## Safety behavior

- Check mode creates no files or directories.
- A new archive is written beside the destination and atomically replaces it only after the command succeeds.
- `dest` is rejected when it is inside any directory source.
- Multiple sources must have unique base names and must not overlap.
- Include entries must stay inside the single directory source.
- ZIP archives preserve symbolic links instead of following them outside the source tree.
- `delete_source: true` never runs before successful archive verification.
- With multiple sources, a deletion error reports both deleted and remaining paths.
- Invalid compression levels and unsupported thread settings fail explicitly.

## Quality and compatibility

Every pull request runs:

- Python behavior and destructive failure-path tests;
- real gzip, pigz, bzip2, xz, zstd, TAR, and ZIP tests;
- legacy and installed-collection smoke tests;
- `ansible-test sanity` without ignore files;
- `ansible-test integration` against the FQCN module;
- openSUSE Leap 15.6 collection build/install and native pigz/zstd smoke tests.

The SUSE container test is a useful compatibility signal, but it does not replace validation on the exact SLES service pack, repositories, Python, Ansible, storage, and security policy used in production.

## Benchmarking

A reproducible comparison with `community.general.archive` is included. It generates large-file, many-small-file, and mixed datasets, validates each archive, and writes raw CSV plus a Markdown summary.

```bash
ANSIBLE_COLLECTIONS_PATH="$PWD/collections" \
python3 benchmarks/run.py \
  --size-mib 512 \
  --small-files 10000 \
  --iterations 3
```

See [`docs/BENCHMARKING.md`](docs/BENCHMARKING.md) for methodology, caveats, local setup, and the manual GitHub Actions workflow.

## Local testing

```bash
python3 tests/test_multi_archive.py
python3 tests/test_failure_paths.py
python3 tests/test_formats_performance.py
python3 tests/test_multiple_sources.py
ANSIBLE_LIBRARY=. ansible-playbook -i localhost, -c local tests.yml

# Run from an ansible_collections/mraibo/yacompress checkout:
ansible-test sanity --python 3.12
ansible-test integration --python 3.12 multi_archive
```
