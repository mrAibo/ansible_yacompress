# `archive_verify` guide

`mraibo.yacompress.archive_verify` verifies an existing archive without extracting it and without changing the filesystem.

Use it for scheduled backup checks, pre-restore validation, monitoring, and inventory jobs that must inspect archives independently from archive creation.

## Supported formats

| Format | Common extensions | Native verification backend |
|---|---|---|
| TAR | `.tar` | `tar -tf` |
| gzip-compressed TAR | `.tar.gz`, `.tgz` | `tar -I gzip -tf` |
| bzip2-compressed TAR | `.tar.bz2`, `.tbz2` | `tar -I bzip2 -tf` |
| xz-compressed TAR | `.tar.xz`, `.txz` | `tar -I xz -tf` |
| zstd-compressed TAR | `.tar.zst` | `tar -I zstd -tf` |
| ZIP | `.zip` | `unzip -t` |

The corresponding native tools must be installed on the managed host. The module resolves executables through Ansible and fails clearly when a required tool is missing.

## Basic verification

```yaml
- name: Verify the latest application backup
  mraibo.yacompress.archive_verify:
    path: /srv/backups/application.tar.zst
```

A valid archive returns:

```yaml
changed: false
valid: true
format: tar.zst
backend: tar+zstd
archive_bytes: 2147483648
elapsed_seconds: 4.3271
```

The module is read-only and always reports `changed: false`.

## Verify after creating an archive

`multi_archive` can verify a newly created archive itself. Use `archive_verify` when you want a separate task, a later scheduled check, or an independently registered result.

```yaml
- name: Create a verified backup
  mraibo.yacompress.multi_archive:
    source:
      - /etc/myapp
      - /var/lib/myapp
    dest: /srv/backups/myapp.tar.zst
    state: archived
    compression_level: 3
    threads: auto
    verify_archive: true

- name: Recheck the completed backup independently
  mraibo.yacompress.archive_verify:
    path: /srv/backups/myapp.tar.zst
  register: myapp_backup_check

- name: Display verification metrics
  ansible.builtin.debug:
    msg: >-
      {{ myapp_backup_check.path | default('/srv/backups/myapp.tar.zst') }}
      verified with {{ myapp_backup_check.backend }} in
      {{ myapp_backup_check.elapsed_seconds }} seconds
```

## Inspect a damaged archive without stopping the play

By default, an invalid archive fails the task. Set `fail_on_error: false` when the playbook should collect the result and decide what to do next.

```yaml
- name: Inspect backup validity
  mraibo.yacompress.archive_verify:
    path: /srv/backups/myapp.tar.zst
    fail_on_error: false
  register: backup_check

- name: Report an invalid backup
  ansible.builtin.fail:
    msg: >-
      Backup verification failed with {{ backup_check.backend }}:
      {{ backup_check.error }}
  when: not backup_check.valid
```

This mode still fails for configuration errors such as a missing file, unknown extension, or missing native executable. It only converts archive verification failure into `valid: false`.

## Explicit format

Normally the format is detected from the filename extension. Set `format` explicitly for extensionless files or non-standard names.

```yaml
- name: Verify an extensionless zstd-compressed TAR archive
  mraibo.yacompress.archive_verify:
    path: /srv/backups/nightly-current
    format: tar.zst
```

Supported explicit values:

```text
tar
tar.gz
tar.bz2
tar.xz
tar.zst
zip
```

An explicit format should match the actual archive. The native verification command will fail when the selected format is wrong.

## Check Mode

The module performs the same read-only verification in Check Mode:

```bash
ansible-playbook backup-audit.yml --check
```

Because verification never modifies files, the result remains `changed: false` in both normal and Check Mode runs.

```yaml
- name: Verify backup during a check-mode audit
  mraibo.yacompress.archive_verify:
    path: /srv/backups/myapp.tar.zst
```

## Verify several known archives

```yaml
- name: Verify required backups
  mraibo.yacompress.archive_verify:
    path: "{{ item }}"
    fail_on_error: false
  loop:
    - /srv/backups/config.tar.zst
    - /srv/backups/database.tar.gz
    - /srv/backups/reports.zip
  register: backup_checks

- name: Collect invalid backup paths
  ansible.builtin.set_fact:
    invalid_backups: >-
      {{ backup_checks.results
         | rejectattr('valid', 'equalto', true)
         | map(attribute='item')
         | list }}

- name: Fail when any required backup is invalid
  ansible.builtin.fail:
    msg: "Invalid backups: {{ invalid_backups | join(', ') }}"
  when: invalid_backups | length > 0
```

## Discover and verify archives in a directory

Use `ansible.builtin.find` to select files. Keep discovery separate from verification so the matching policy remains explicit.

```yaml
- name: Find recent zstd backups
  ansible.builtin.find:
    paths: /srv/backups
    patterns: '*.tar.zst'
    file_type: file
    age: -7d
  register: recent_backups

- name: Verify recent zstd backups
  mraibo.yacompress.archive_verify:
    path: "{{ item.path }}"
    fail_on_error: false
  loop: "{{ recent_backups.files }}"
  loop_control:
    label: "{{ item.path }}"
  register: recent_backup_checks

- name: Show failed verifications
  ansible.builtin.debug:
    msg: "{{ item.item.path }}: {{ item.error }}"
  loop: "{{ recent_backup_checks.results }}"
  loop_control:
    label: "{{ item.item.path }}"
  when: not item.valid
```

## Scheduled backup audit

A typical audit playbook can verify archives, report metrics, and fail only after all checks have completed.

```yaml
---
- name: Audit backup archives
  hosts: backup_servers
  gather_facts: false

  vars:
    required_archives:
      - /srv/backups/system.tar.zst
      - /srv/backups/application.tar.gz
      - /srv/backups/export.zip

  tasks:
    - name: Verify every required archive
      mraibo.yacompress.archive_verify:
        path: "{{ item }}"
        fail_on_error: false
      loop: "{{ required_archives }}"
      register: archive_audit

    - name: Display successful checks
      ansible.builtin.debug:
        msg: >-
          {{ item.item }}: {{ item.archive_bytes }} bytes,
          {{ item.backend }}, {{ item.elapsed_seconds }} seconds
      loop: "{{ archive_audit.results }}"
      when: item.valid

    - name: Stop after reporting all invalid archives
      ansible.builtin.fail:
        msg: >-
          Invalid archives:
          {{ archive_audit.results
             | rejectattr('valid', 'equalto', true)
             | map(attribute='item')
             | join(', ') }}
      when: >-
        archive_audit.results
        | rejectattr('valid', 'equalto', true)
        | list
        | length > 0
```

## Error behavior

### Missing archive

A missing path or a path that is not a regular file always fails:

```text
Archive does not exist or is not a regular file: /srv/backups/missing.tar.zst
```

### Unknown extension

When automatic detection is impossible, set `format` explicitly:

```text
Cannot detect archive format from extension; set 'format' explicitly.
```

### Missing native tool

Ansible reports the missing executable. Install the matching package on the managed host or choose a format supported by the installed tools.

### Invalid archive

With the default `fail_on_error: true`, the task fails and includes:

- `valid: false`
- detected `format`
- verification `backend`
- archive size
- elapsed time
- native tool error

With `fail_on_error: false`, the same details are returned without failing the task.

## What verification guarantees

The module asks the native archive tool to read and validate the archive structure and compressed stream. This detects common truncation, corruption, invalid headers, and decompression errors.

Verification does not prove that:

- the backup contains every file you intended to archive;
- files inside the archive match an external checksum or manifest;
- application data was captured in a transactionally consistent state;
- the storage device will remain healthy later;
- a successful restore procedure has been tested.

For stronger guarantees, combine archive verification with application-aware snapshots, `archive_manifest`, periodic restore tests, and independent storage monitoring.

## Performance considerations

Verification reads the complete compressed archive for compressed TAR and ZIP formats. It can therefore consume significant I/O and CPU on large backup sets.

Recommended operational practices:

- schedule verification outside peak backup windows;
- avoid verifying the same large archive concurrently from several hosts;
- monitor storage throughput and CPU usage;
- keep creation and audit schedules separate;
- perform periodic restore tests in addition to structural verification.

## Module reference

```bash
ansible-doc mraibo.yacompress.archive_verify
```

The concise module reference documents all parameters and return values. This guide focuses on operational workflows and examples.
