# YaCompress Ansible Collection

`mraibo.yacompress` is a Linux-focused Ansible Collection for fast archive creation and a transparent backup lifecycle. It uses native `tar`, `pigz`, `zstd`, `xz`, `bzip2`, and ZIP tools, while keeping verification, manifests, and retention as explicit operations.

For ordinary extraction that does not need this interface, consider `ansible.builtin.unarchive` first.

## Modules

| Module | Purpose |
|---|---|
| `mraibo.yacompress.multi_archive` | Create and extract native archives with verification, threading, metrics, sparse-file support, and safe source deletion |
| `mraibo.yacompress.archive_verify` | Read-only structural verification of an existing TAR-family or ZIP archive |
| `mraibo.yacompress.archive_manifest` | Create or verify deterministic SHA-256 manifests for one file or a selected directory tree |
| `mraibo.yacompress.archive_rotate` | Safely rotate regular files by count and/or age with Check Mode previews |

See [`docs/BACKUP_WORKFLOW.md`](docs/BACKUP_WORKFLOW.md) and [`examples/complete_backup.yml`](examples/complete_backup.yml) for the complete create → verify → manifest → rotate workflow.

## Highlights

- `tar`, `tar.gz`, `tar.bz2`, `tar.xz`, `tar.zst`, and ZIP archives
- one source path or multiple source paths for TAR-family archives
- sparse-file handling for virtual disks and other files with holes
- parallel gzip with `pigz`; native zstd and xz threading
- configurable compression levels and worker limits
- atomic archive and manifest replacement
- archive integrity verification before optional source deletion
- standalone structural verification of retained backups
- deterministic SHA-256 manifests detecting missing, changed, and unexpected files
- retention by count and age with `min_keep` protection
- Check Mode support without filesystem changes
- official `ansible-test sanity` and integration coverage
- continuous testing across Debian, Ubuntu, Fedora, Rocky, AlmaLinux, Oracle Linux, Arch, and openSUSE

## Installation

From Ansible Galaxy after publication:

```bash
ansible-galaxy collection install mraibo.yacompress:1.6.0
```

Build and install from a checkout:

```bash
ansible-galaxy collection build --output-path build
ansible-galaxy collection install build/mraibo-yacompress-1.6.0.tar.gz
```

Required commands depend on the selected format: `tar`, `gzip` or `pigz`, `bzip2`, `xz`, `zstd`, and `zip`/`unzip`.

## Quick backup example

```yaml
- name: Create verified archive
  mraibo.yacompress.multi_archive:
    source:
      - /etc/myapp
      - /var/lib/myapp
    dest: /srv/backups/application.tar.zst
    state: archived
    compression_level: 3
    threads: auto
    verify_archive: true

- name: Independently verify archive structure
  mraibo.yacompress.archive_verify:
    path: /srv/backups/application.tar.zst

- name: Create SHA-256 manifest
  mraibo.yacompress.archive_manifest:
    source: /srv/backups/application.tar.zst
    manifest: /srv/backups/application.tar.zst.manifest.json

- name: Rotate retained archives
  mraibo.yacompress.archive_rotate:
    directory: /srv/backups
    patterns: ['application-*.tar.zst']
    keep_last: 14
    max_age_days: 45
    min_keep: 2
```

Rotation should run only after the new archive passes structural and checksum verification. Manifests are separate files and should receive a matching retention policy.

## Format selection

| Scenario | Suggested format |
|---|---|
| Frequent Linux backups | `tar.zst`, level 1–3 |
| Gzip compatibility with parallel compression | `tar.gz` with `compression: pigz` |
| Restrict shared-server CPU use | Set an explicit `threads` value |
| Compact long-term archives | `tar.xz` |
| JPEG, MP4, ZIP, and other already-compressed data | `tar` |
| Broad desktop/Windows exchange | ZIP |

Use the included benchmark suite on the actual target hardware before making performance claims or operational decisions.

## `multi_archive` parameters

| Parameter | Required | Description |
|---|---:|---|
| `source` | yes | One source path, an archive to extract, or a list of source paths for TAR-family creation |
| `dest` | yes | Destination archive or extraction directory |
| `state` | yes | `archived` or `unarchived` |
| `format` | no | `tar`, `tar.gz`, `tar.bz2`, `tar.xz`, `tar.zst`, or `zip`; inferred when omitted |
| `compression` | no | For `tar.gz`: `gzip`, `pigz`, `auto`, or compatibility alias `none` |
| `compression_level` | no | gzip/bzip2 `1-9`, xz `0-9`, zstd `1-19`, ZIP `0-9` |
| `threads` | no | `auto` or a positive integer; explicit limits apply to pigz, xz, and zstd |
| `verify_archive` | no | Verify the completed archive before replacing `dest` |
| `sparse` | no | Enable GNU tar sparse-file detection for TAR-family creation |
| `creates` | no | Skip the operation when this path already exists |
| `delete_source` | no | Delete all sources after a successful, verified operation |
| `include` | no | Relative paths or glob patterns; only with one directory source |
| `exclude` | no | Archive path patterns to exclude |

Without `creates`, an executed archive or extraction operation reports `changed: true`. The module does not pretend that rewriting an archive is idempotent.

## Archive examples

### Multiple sources

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

Each source is stored under its base name. Base names must be unique, source paths must not overlap, and `dest` must not be inside a source. Multiple sources are intentionally limited to TAR-family formats.

### Sparse virtual disk

```yaml
- name: Archive a sparse virtual disk image
  mraibo.yacompress.multi_archive:
    source: /var/lib/libvirt/images/server.raw
    dest: /srv/backups/server.raw.tar.zst
    state: archived
    sparse: true
    compression_level: 1
    threads: auto
    verify_archive: true
```

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

### Extract once

```yaml
- name: Extract application bundle once
  mraibo.yacompress.multi_archive:
    source: /srv/releases/application.tar.zst
    dest: /opt/application
    creates: /opt/application/bin/application
    state: unarchived
```

## Safety behavior

- Check Mode creates no files or directories; rotation reports planned removals.
- New archives and manifests are written beside their destinations and replaced atomically.
- Source/destination overlap, unsafe include paths, and overlapping multiple sources are rejected.
- Symbolic links are not followed by verification, rotation, or manifest discovery.
- `delete_source: true` never runs before successful archive verification.
- Rotation preserves the newest `min_keep` files, defaulting to one.
- Manifest entry paths are validated before filesystem access.
- A checksum manifest is not a digital signature. Protect or sign it when malicious modification is in scope.

Structural and checksum verification do not replace restore testing. Mutable databases and applications require their own snapshot, dump, or quiesce procedure before archiving.

## Documentation

- [`docs/BACKUP_WORKFLOW.md`](docs/BACKUP_WORKFLOW.md) — complete lifecycle and operational ordering
- [`docs/ARCHIVE_VERIFY.md`](docs/ARCHIVE_VERIFY.md) — structural verification
- [`docs/ARCHIVE_ROTATE.md`](docs/ARCHIVE_ROTATE.md) — retention and deletion safety
- [`docs/ARCHIVE_MANIFEST.md`](docs/ARCHIVE_MANIFEST.md) — SHA-256 manifests
- [`docs/ENTERPRISE_STORAGE.md`](docs/ENTERPRISE_STORAGE.md) — NFS, SELinux, FIPS, sparse and large-file validation
- [`docs/BENCHMARKING.md`](docs/BENCHMARKING.md) — reproducible performance comparison
- [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) — tested Linux matrix and support boundaries
- [`docs/RELEASING.md`](docs/RELEASING.md) — release and Galaxy publishing process

## Quality and compatibility

Every pull request runs:

- Python behavior and destructive failure-path tests;
- real gzip, pigz, bzip2, xz, zstd, TAR, and ZIP tests;
- tests for verification, rotation, manifests, multiple sources, and sparse files;
- legacy and installed-collection smoke tests;
- `ansible-test sanity` without ignore files;
- `ansible-test integration` for all collection modules;
- modern, enterprise, SUSE, and large-file storage workflows.

The container matrix is a strong compatibility signal, but it does not replace validation on the exact SLES/RHEL service pack, repositories, Python, Ansible, storage, and security policy used in production.

## Benchmarking

```bash
ANSIBLE_COLLECTIONS_PATH="$PWD/collections" \
python3 benchmarks/run.py \
  --size-mib 512 \
  --small-files 10000 \
  --iterations 3
```

See [`docs/BENCHMARKING.md`](docs/BENCHMARKING.md) for methodology and caveats.

## Local testing

```bash
python3 tests/test_multi_archive.py
python3 tests/test_failure_paths.py
python3 tests/test_formats_performance.py
python3 tests/test_multiple_sources.py
python3 tests/test_sparse.py
python3 tests/test_archive_verify.py
python3 tests/test_archive_rotate.py
python3 tests/test_archive_manifest.py
python3 tests/test_release.py
ANSIBLE_LIBRARY=. ansible-playbook -i localhost, -c local tests.yml

# Run from an ansible_collections/mraibo/yacompress checkout:
ansible-test sanity --python 3.12
ansible-test integration --python 3.12 multi_archive archive_verify archive_rotate archive_manifest
```

For legacy playbooks, the root `multi_archive.py` symlink can still be exposed through `ANSIBLE_LIBRARY`.
