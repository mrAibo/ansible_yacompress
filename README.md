# YaCompress

**A Linux-first archive lifecycle for Ansible.**

Create standard archives with native tools, verify them, record SHA-256 manifests, and rotate retained backups through explicit Ansible modules.

```text
source data
    ↓
multi_archive
    ↓
archive_verify
    ↓
archive_manifest
    ↓
archive_rotate
    ↓
ready for restore testing
```

YaCompress does not invent a backup format. It produces ordinary TAR-family and ZIP archives that remain recoverable with standard system tools.

> YaCompress is not a universal replacement for `community.general.archive`, `ansible.builtin.unarchive`, Borg, Restic, or Kopia. It is designed for Linux environments that want a transparent, Ansible-managed lifecycle for standard archive files.

## Why use it?

Most archive tasks stop after a compressed file is created. Operational backups usually need more:

- native `pigz`, zstd, xz, bzip2, TAR, and ZIP backends;
- verification before optional source deletion;
- scheduled verification of retained archives;
- deterministic SHA-256 manifests;
- explicit count- and age-based retention;
- Check Mode previews for destructive operations;
- standard formats without repository lock-in;
- tested behaviour across major Linux families.

Read [Why YaCompress exists](docs/WHY_YACOMPRESS.md) for the detailed comparison with `community.general.archive`, direct shell commands, `ansible.builtin.unarchive`, and repository-based backup systems.

## Modules

| Module | Responsibility |
|---|---|
| `mraibo.yacompress.multi_archive` | Create and extract native archives with verification, threading, metrics, sparse-file support, and guarded source deletion |
| `mraibo.yacompress.archive_verify` | Perform read-only structural verification of an existing TAR-family or ZIP archive |
| `mraibo.yacompress.archive_manifest` | Create or verify deterministic SHA-256 manifests for a file or selected directory tree |
| `mraibo.yacompress.archive_rotate` | Rotate regular files by count and/or age with `min_keep` protection and Check Mode preview |

The modules remain separate so that creation, verification, checksumming, and deletion can fail, retry, and report independently.

## Quick start

Requires Ansible Core 2.15 or newer and the native tools for the selected format: `tar`, plus `gzip`/`pigz`, `bzip2`, `xz`, `zstd`, or `zip`/`unzip` as needed.

Build and install directly from this repository before the Galaxy release:

```bash
ansible-galaxy collection build --output-path build
ansible-galaxy collection install build/mraibo-yacompress-*.tar.gz
```

After publication, install from Ansible Galaxy:

```bash
ansible-galaxy collection install mraibo.yacompress
```

Create and validate a backup:

```yaml
- name: Create a verified archive
  mraibo.yacompress.multi_archive:
    source:
      - /etc/myapp
      - /var/lib/myapp
    dest: /srv/backups/application.tar.zst
    state: archived
    compression_level: 3
    threads: auto
    verify_archive: true

- name: Verify the retained archive independently
  mraibo.yacompress.archive_verify:
    path: /srv/backups/application.tar.zst

- name: Record its SHA-256 manifest
  mraibo.yacompress.archive_manifest:
    source: /srv/backups/application.tar.zst
    manifest: /srv/backups/application.tar.zst.manifest.json
```

Apply retention only after the new backup passes the required checks:

```yaml
- name: Retain fourteen recent application backups
  mraibo.yacompress.archive_rotate:
    directory: /srv/backups
    patterns:
      - 'application-*.tar.zst'
    keep_last: 14
    max_age_days: 45
    min_keep: 2
```

See [`examples/complete_backup.yml`](examples/complete_backup.yml) for a complete timestamped workflow, including separate archive and manifest retention.

## YaCompress and `community.general.archive`

`community.general.archive` is mature, portable, Python-based, and a strong choice for ordinary archive creation. YaCompress has a different scope: native Linux compression plus the lifecycle around retained archives.

| Need | Suggested choice |
|---|---|
| Straightforward portable archive creation | `community.general.archive` |
| Ordinary extraction | `ansible.builtin.unarchive` |
| Native pigz/zstd, sparse TAR, worker limits | YaCompress |
| Verification before deleting sources | YaCompress |
| Scheduled structural checks and SHA-256 manifests | YaCompress |
| Count/age retention with Check Mode preview | YaCompress |
| Deduplication, encryption, snapshots, remote repository | Borg, Restic, Kopia, or another repository-based system |

This is a scope comparison, not a universal performance claim. Run the included benchmark on the target hardware and dataset before making performance decisions.

Full capability comparison: [`docs/WHY_YACOMPRESS.md`](docs/WHY_YACOMPRESS.md).

## Supported formats

| Format | Native backend | Notable use |
|---|---|---|
| `tar` | GNU tar | Already-compressed data or fastest bundling |
| `tar.gz` | gzip or pigz | Broad compatibility; optional parallel gzip |
| `tar.bz2` | bzip2 | Compatibility with existing bzip2 workflows |
| `tar.xz` | xz | Compact long-term archives |
| `tar.zst` | zstd | Fast Linux backup workflows |
| ZIP | zip/unzip | Desktop and Windows-oriented exchange |

Compression levels and worker counts are explicit. Use `threads: auto` or a positive integer for supported native backends.

## Safety model

YaCompress is intentionally conservative around destructive operations:

- Check Mode does not change the filesystem;
- new archives and manifests are written beside the destination and replaced atomically;
- unsafe source, destination, include, and manifest paths are rejected;
- verification, manifest discovery, and rotation do not follow symbolic links;
- `delete_source: true` runs only after successful archive verification;
- partial deletion failures report deleted and remaining paths;
- rotation protects the newest `min_keep` files;
- a checksum manifest is explicitly not treated as a digital signature.

Structural checks and checksums do not replace restore testing. Active databases and mutable applications require an application-aware dump, snapshot, lock, or quiesce step before archiving.

## Compatibility and quality

Every pull request runs:

- Python behaviour and destructive failure-path tests;
- native gzip, pigz, bzip2, xz, zstd, TAR, and ZIP round trips;
- tests for multiple sources, sparse files, verification, manifests, and rotation;
- `ansible-test sanity` without ignore files;
- `ansible-test integration` for all Collection modules;
- modern and enterprise Linux matrices;
- openSUSE validation;
- a sparse-file storage test with a logical file larger than 5 GiB.

Continuously tested families include Debian, Ubuntu, Fedora, Rocky Linux, AlmaLinux, Oracle Linux, Arch Linux, and openSUSE. Container validation is a strong compatibility signal, but production use should still be tested on the exact OS release, storage, security policy, and native tool versions.

## Documentation

### Start here

- [`docs/WHY_YACOMPRESS.md`](docs/WHY_YACOMPRESS.md) — purpose, alternatives, honest capability comparison, and use-case boundaries
- [`docs/BACKUP_WORKFLOW.md`](docs/BACKUP_WORKFLOW.md) — complete create → verify → manifest → rotate workflow
- [`examples/complete_backup.yml`](examples/complete_backup.yml) — runnable workflow example

### Module guides

- [`docs/ARCHIVE_VERIFY.md`](docs/ARCHIVE_VERIFY.md)
- [`docs/ARCHIVE_MANIFEST.md`](docs/ARCHIVE_MANIFEST.md)
- [`docs/ARCHIVE_ROTATE.md`](docs/ARCHIVE_ROTATE.md)

### Operations and maintenance

- [`docs/COMPATIBILITY.md`](docs/COMPATIBILITY.md) — tested systems and support boundaries
- [`docs/ENTERPRISE_STORAGE.md`](docs/ENTERPRISE_STORAGE.md) — NFS, SELinux, FIPS, sparse files, and large-file validation
- [`docs/BENCHMARKING.md`](docs/BENCHMARKING.md) — reproducible performance methodology
- [`docs/RELEASING.md`](docs/RELEASING.md) — releases and Galaxy publication

## Build from source

```bash
ansible-galaxy collection build --output-path build
ansible-galaxy collection install build/mraibo-yacompress-1.6.0.tar.gz
```

Native command requirements depend on the selected format: `tar`, `gzip` or `pigz`, `bzip2`, `xz`, `zstd`, and `zip`/`unzip`.

## Benchmark on your system

```bash
ANSIBLE_COLLECTIONS_PATH="$PWD/collections" \
python3 benchmarks/run.py \
  --size-mib 512 \
  --small-files 10000 \
  --iterations 3
```

The benchmark records raw CSV and Markdown results. Small CI smoke runs validate the framework but are not suitable for marketing conclusions.

## Project direction

The project goal is precise:

> Become a dependable Ansible solution for managing the lifecycle of standard Linux archives—not a proprietary backup repository and not a replacement for every existing archive tool.

New features should improve recoverability, operational safety, or transparency. Features that only increase surface area should remain out.

## License

GPL-3.0-or-later.
