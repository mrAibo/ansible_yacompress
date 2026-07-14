# Changelog

All notable changes to this project are documented here.

## 1.5.0 — 2026-07-14

### Added

- Sparse-file support for TAR-family archives through `sparse: true`.
- Continuous validation with a logical sparse file larger than 5 GiB.
- Atomic replacement and temporary-directory cleanup checks on a separate tmpfs destination.
- A reusable real-host validation runner for NFS, clustered filesystems, SELinux enforcing systems, and FIPS-enabled hosts.
- Enterprise storage and security-profile validation documentation.

### Fixed

- Portable compressed TAR verification and extraction on older GNU tar releases by explicitly selecting gzip, bzip2, xz, or zstd.

### Compatibility

- Continuous enterprise validation covers Ubuntu 22.04, Debian 11, AlmaLinux 8/9, and Oracle Linux 8/9 with `ansible-core 2.15`.
- Real NFS, SELinux enforcing, and FIPS claims require the supplied validator to run on the exact target host.

## 1.4.0 — 2026-07-14

### Added

- Ansible Collection packaging as `mraibo.yacompress`.
- Safe multiple-source support for TAR-family archives.
- Native `tar`, `tar.xz`, and `tar.zst` formats.
- Thread limits, compression levels, archive verification, and performance metrics.
- Permanent Linux CI with real native archive tools.

### Fixed

- Correct check-mode and changed-state behavior.
- Atomic archive replacement and destructive-operation safety.
- Path traversal, destination-inside-source, stale ZIP, and symlink handling.
- Archive verification before deleting source data.

### Compatibility

The legacy root `multi_archive.py` path remains available as a symbolic link to the collection module for existing `ANSIBLE_LIBRARY` installations.
