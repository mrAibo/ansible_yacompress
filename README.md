# Multi Archive Ansible Module

`multi_archive.py` creates and extracts `tar.gz`, `tar.bz2`, and ZIP archives on a managed host. Its main reason to exist is parallel gzip compression through `pigz`; for ordinary extraction, consider `ansible.builtin.unarchive` first.

## Features

- `tar.gz`, `tar.bz2`, and ZIP archives
- parallel gzip with `compression: pigz`
- automatic `pigz` fallback with `compression: auto`
- include globs and exclude patterns while archiving
- automatic format detection from the archive extension
- check-mode support without filesystem changes
- explicit idempotency guard through `creates`
- atomic archive replacement
- optional source deletion after success; newly created archives are verified before destructive deletion

## Installation

Place `multi_archive.py` in a `library/` directory next to the playbook, or set `ANSIBLE_LIBRARY` to the directory containing the module.

## Parameters

| Parameter | Required | Description |
|---|---:|---|
| `source` | yes | Source file/directory to archive, or archive to extract |
| `dest` | yes | Destination archive or extraction directory |
| `state` | yes | `archived` or `unarchived` |
| `format` | no | `tar.gz`, `tar.bz2`, or `zip`; inferred from `dest`/`source` when omitted |
| `compression` | no | For `tar.gz`: `gzip`, `pigz`, `auto`, or compatibility alias `none` |
| `creates` | no | Skip the operation when this path already exists |
| `delete_source` | no | Delete the source after a successful operation |
| `include` | no | Relative paths or glob patterns to archive; directory sources only |
| `exclude` | no | Archive path patterns to exclude |

Without `creates`, an executed archive or extraction operation reports `changed: true`. The module does not pretend that rewriting an archive is idempotent.

## Examples

### Fast archive with automatic fallback

```yaml
- name: Archive data using pigz when available
  multi_archive:
    source: /srv/data
    dest: /srv/backups/data.tar.gz
    state: archived
    compression: auto
```

### Archive selected content

```yaml
- name: Archive documents without temporary files
  multi_archive:
    source: /srv/data
    dest: /srv/backups/documents.tar.gz
    state: archived
    include:
      - "*.txt"
      - "docs/**"
    exclude:
      - "*.tmp"
```

### Extract once

```yaml
- name: Extract application bundle once
  multi_archive:
    source: /srv/releases/application.tar.gz
    dest: /opt/application
    creates: /opt/application/bin/application
    state: unarchived
```

For extraction that does not require this module's combined interface, prefer the built-in module:

```yaml
- name: Extract an archive already present on the managed host
  ansible.builtin.unarchive:
    src: /srv/releases/application.tar.gz
    dest: /opt/application
    remote_src: true
    creates: /opt/application/bin/application
```

## Safety behavior

- Check mode creates no files or directories.
- A new archive is written beside the destination and atomically replaces it only after the command succeeds.
- `dest` is rejected when it is inside a directory `source`.
- Include entries must stay inside `source`.
- `delete_source: true` never runs before the archive/extraction command succeeds.
- Archives are verified before deleting an archived source.

## Testing

```bash
python3 tests/test_multi_archive.py
ANSIBLE_LIBRARY=. ansible-playbook -i localhost, -c local tests.yml
```

The fast standard-library tests cover formats, include globs, path validation, check mode, `creates`, atomic ZIP replacement, extraction, and source deletion. The Ansible playbook is a small end-to-end smoke test of module packaging and return values.
