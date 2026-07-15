# Changelog

All notable changes to this project are documented here.

## 1.6.0 — 2026-07-15

### Added

- `mraibo.yacompress.archive_verify` for read-only structural verification of existing TAR-family and ZIP archives.
- `mraibo.yacompress.archive_rotate` for deterministic retention by count and age, with Check Mode previews, `min_keep`, path confinement, and symlink protection.
- `mraibo.yacompress.archive_manifest` for deterministic, atomically written SHA-256 manifests covering one archive or a selected directory tree.
- Detection of missing, changed, and unexpected files during manifest verification.
- Detailed operational guides for archive verification, rotation, manifests, performance, security, acceptance testing, and the complete backup lifecycle.
- A runnable end-to-end workflow that creates, verifies, manifests, and rotates application backups.
- Honest comparison with `community.general.archive`, direct shell commands, `ansible.builtin.unarchive`, and repository-based backup systems.
- A practical FAQ, contributor workflow, architecture decisions, and project roadmap with explicit non-goals.
- A reproducible benchmark framework and a documented CachyOS reference run.
- An Ansible Galaxy release checklist for immutable, clean-install-verified publication.

### Changed

- README is now a project landing page with a source-build Quick Start that works before Galaxy publication.
- Compression defaults and pigz selection are documented explicitly without changing existing playbook behavior.
- Release and operational documentation now distinguish CI evidence, real-host acceptance evidence, and environment-specific validation.

### Fixed

- `run_host_storage_validation.sh` now isolates its collection path from an inherited external `ANSIBLE_COLLECTIONS_PATH`.
- Absolute and parent-traversal `exclude` patterns are rejected before archive creation.
- Benchmark build instructions no longer depend on a stale hard-coded archive version.

### Safety

- Verification and manifest checks are read-only and report `changed: false`.
- Rotation preserves at least one newest archive by default and never follows symbolic links.
- Manifest paths are validated before use, and changed manifests are replaced atomically beside their destination.
- Source, destination, include, exclude, and manifest path relationships are validated before native commands run.
- The documented workflow rotates older recovery points only after the new archive passes structural and checksum verification.
- Private vulnerability reports are accepted through GitHub Private Vulnerability Reporting.

### Quality

- Unit and official `ansible-test integration` coverage for all four collection modules.
- Continuous validation across modern, enterprise, and SUSE Linux matrices remains part of every pull request.
- Real-host acceptance passed on CachyOS with `ansible-core 2.19.11`, including Check Mode, corruption detection, manifest mismatches, rotation, and a sparse-file round trip larger than 5 GiB.
- The reference benchmark recorded zstd and pigz throughput gains over `community.general.archive` gzip on the tested host; the documentation explicitly limits those findings to the measured environment and datasets.

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
