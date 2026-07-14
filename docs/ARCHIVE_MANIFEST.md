# Archive manifests

`mraibo.yacompress.archive_manifest` creates and verifies deterministic JSON manifests containing SHA-256 digests and file sizes.

The module is intended for backup evidence and later integrity checks. It does not replace application-consistent snapshots, archive-format verification, or restore tests.

## Basic archive manifest

```yaml
- name: Create backup archive
  mraibo.yacompress.multi_archive:
    source: /srv/application
    dest: /srv/backups/application.tar.zst
    state: archived
    verify_archive: true

- name: Create SHA-256 manifest
  mraibo.yacompress.archive_manifest:
    source: /srv/backups/application.tar.zst
    manifest: /srv/backups/application.tar.zst.manifest.json
```

Running the second task again reports `changed: false` when the source content and manifest are unchanged.

## Verify later

```yaml
- name: Verify stored backup against its manifest
  mraibo.yacompress.archive_manifest:
    source: /srv/backups/application.tar.zst
    manifest: /srv/backups/application.tar.zst.manifest.json
    state: verified
```

Verification reports `changed: false`. By default, a mismatch fails the task.

## Soft-failure inspection

```yaml
- name: Inspect backup integrity without stopping the play
  mraibo.yacompress.archive_manifest:
    source: /srv/backups/application.tar.zst
    manifest: /srv/backups/application.tar.zst.manifest.json
    state: verified
    fail_on_mismatch: false
  register: manifest_check

- name: Report mismatches
  ansible.builtin.debug:
    var: manifest_check.mismatches
  when: not manifest_check.valid
```

Possible mismatch messages include:

- `missing: path`
- `unexpected: path`
- `size changed: path`
- `checksum changed: path`
- `source type changed: ...`

## Directory manifests

```yaml
- name: Create a manifest for all retained archives
  mraibo.yacompress.archive_manifest:
    source: /srv/backups/application
    manifest: /srv/manifests/application-backups.json
    patterns:
      - '*.tar.zst'
      - '*.zip'
    exclude:
      - 'temporary-*'
    recursive: true
```

Paths in the manifest are relative to `source`, sorted deterministically, and use `/` separators. Symbolic links are never followed or included.

The manifest stores the selection policy (`patterns`, `exclude`, and `recursive`). Later verification uses that stored policy. This means newly added files matching the policy are reported as `unexpected`.

## Check Mode

For `state: present`, Check Mode hashes the selected files and reports whether the manifest would change, but writes nothing:

```bash
ansible-playbook backup.yml --check
```

For `state: verified`, Check Mode performs the normal read-only verification.

## Manifest format

The output is deterministic JSON:

```json
{
  "algorithm": "sha256",
  "entries": [
    {
      "path": "application.tar.zst",
      "sha256": "...",
      "size": 123456
    }
  ],
  "exclude": [],
  "patterns": [
    "*"
  ],
  "recursive": true,
  "source_type": "file",
  "version": 1
}
```

The module validates the manifest version, algorithm, structure, and every relative entry path before reading files. Absolute paths and `..` traversal are rejected.

## Atomic update behavior

A changed manifest is written to a temporary file in the manifest destination directory, flushed with `fsync`, and moved into place with `os.replace`. This prevents a partially written JSON file from replacing a valid manifest.

The manifest parent directory must already exist. The module does not create it implicitly.

## Recommended backup workflow

```yaml
- name: Create verified archive
  mraibo.yacompress.multi_archive:
    source: /srv/application
    dest: "/srv/backups/application-{{ ansible_date_time.iso8601_basic_short }}.tar.zst"
    state: archived
    verify_archive: true
  register: backup

- name: Create archive manifest
  mraibo.yacompress.archive_manifest:
    source: "{{ backup.dest }}"
    manifest: "{{ backup.dest }}.manifest.json"

- name: Rotate old archives
  mraibo.yacompress.archive_rotate:
    directory: /srv/backups
    patterns:
      - 'application-*.tar.zst'
    keep_last: 14
    max_age_days: 45
```

When archive and manifest files are rotated together, use naming and rotation patterns that keep each pair consistent. A future policy-aware paired rotation feature may make this easier; the current rotation module treats every matching file independently.

## Performance

SHA-256 verification reads every selected byte. For large backups, run it during a suitable maintenance window and avoid verifying the same dataset simultaneously from many hosts against shared storage.

Directory manifests require a metadata scan plus a complete read of every selected regular file. Check Mode for `state: present` performs the same hashing work because it must determine whether the generated manifest would differ.

## What a valid manifest proves

A successful verification proves that the selected bytes match the previously recorded SHA-256 values and sizes.

It does not prove that:

- a database backup is transactionally consistent;
- an archive can be restored into a working application;
- permissions, ACLs, xattrs, SELinux labels, or ownership are correct;
- the manifest itself was protected against malicious replacement;
- SHA-256 values were stored in an independent trust domain.

For stronger assurance, store manifests separately or sign them, verify archive structure with `archive_verify`, and regularly perform real restores.
