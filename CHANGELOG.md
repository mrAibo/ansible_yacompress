# Changelog

All notable changes to this project are documented here.

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
