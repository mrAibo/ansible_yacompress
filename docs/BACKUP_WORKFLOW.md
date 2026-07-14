# Complete backup workflow

This guide combines the four YaCompress modules into an explicit backup lifecycle:

1. create an archive with `multi_archive`;
2. verify the archive structure with `archive_verify`;
3. create and verify a SHA-256 manifest with `archive_manifest`;
4. remove expired backups with `archive_rotate`.

The complete runnable example is in [`examples/complete_backup.yml`](../examples/complete_backup.yml).

## Why the steps remain separate

Each module has one responsibility and a distinct failure mode. Keeping the tasks separate makes an interrupted run observable and safely repeatable:

- archive creation can be retried without changing the retention policy;
- structural verification can be scheduled independently;
- manifest verification detects later byte-level changes;
- rotation runs only after the new backup and manifest exist.

## Recommended ordering

Always rotate after the new archive has passed both structural and checksum verification. Do not delete older recovery points before proving that the newest one is readable.

```yaml
- name: Create verified archive
  mraibo.yacompress.multi_archive:
    source:
      - /etc/myapp
      - /var/lib/myapp
    dest: "{{ backup_path }}"
    state: archived
    compression_level: 3
    threads: auto
    verify_archive: true

- name: Verify native archive structure
  mraibo.yacompress.archive_verify:
    path: "{{ backup_path }}"

- name: Create manifest
  mraibo.yacompress.archive_manifest:
    source: "{{ backup_path }}"
    manifest: "{{ backup_path }}.manifest.json"

- name: Verify manifest immediately
  mraibo.yacompress.archive_manifest:
    source: "{{ backup_path }}"
    manifest: "{{ backup_path }}.manifest.json"
    state: verified

- name: Rotate old archives
  mraibo.yacompress.archive_rotate:
    directory: "{{ backup_directory }}"
    patterns: ['application-*.tar.zst']
    keep_last: 14
    max_age_days: 45
    min_keep: 2
```

## Naming backups

Use sortable timestamps in filenames. `ansible_date_time.iso8601_basic_short` produces names that sort chronologically and avoid characters that are awkward in shell tools:

```yaml
backup_name: "application-{{ ansible_date_time.iso8601_basic_short }}.tar.zst"
```

For multiple hosts writing to one shared directory, include `inventory_hostname`:

```yaml
backup_name: "{{ inventory_hostname }}-application-{{ ansible_date_time.iso8601_basic_short }}.tar.zst"
```

## Retaining manifests

Archive manifests are separate files. Apply the same retention policy to them after rotating archives:

```yaml
- name: Rotate archive manifests
  mraibo.yacompress.archive_rotate:
    directory: "{{ backup_directory }}"
    patterns: ['application-*.tar.zst.manifest.json']
    keep_last: 14
    max_age_days: 45
    min_keep: 2
```

This filename-based policy assumes that every archive has one adjacent manifest. For strict pairing across manual deletions or external storage lifecycle rules, reconcile filenames before rotation.

## Check Mode preview

`archive_rotate` provides a useful deletion preview:

```bash
ansible-playbook backup.yml --check --diff
```

Archive creation and manifest creation report planned changes without writing. Verification still reads existing files. A first-run Check Mode cannot verify an archive that has not yet been created, so preview rotation independently when validating a new playbook.

## Scheduled verification

Creation-time verification proves the archive was readable when written. Schedule recurring verification to detect later storage damage:

```yaml
- name: Find retained archives
  ansible.builtin.find:
    paths: /srv/backups/application
    patterns: 'application-*.tar.zst'
    file_type: file
  register: retained_archives

- name: Verify archive structures
  mraibo.yacompress.archive_verify:
    path: "{{ item.path }}"
  loop: "{{ retained_archives.files }}"

- name: Verify archive manifests
  mraibo.yacompress.archive_manifest:
    source: "{{ item.path }}"
    manifest: "{{ item.path }}.manifest.json"
    state: verified
  loop: "{{ retained_archives.files }}"
```

## Restore testing

Structural checks and SHA-256 checks do not prove that an application can recover from the backup. Periodically restore into an isolated location and run application-specific validation.

For databases and other mutable services, create a consistent source first using the database's backup mechanism, filesystem snapshots, or a documented quiesce procedure. Archiving live files does not create transactional consistency.

## Security notes

A SHA-256 manifest detects accidental changes only while the manifest itself remains trusted. Store manifests separately, protect them with permissions, or sign them when malicious modification is in scope.

Avoid storing credentials, encryption keys, or backup secrets directly in playbooks. Use Ansible Vault or the organization's secret-management system.

## Failure handling

The example intentionally relies on Ansible's default stop-on-failure behavior. Rotation is not reached when archive creation, structural verification, or manifest verification fails.

For notification handlers, wrap the workflow in an Ansible `block` and add a `rescue` section. Do not continue into rotation from `rescue` unless a valid new recovery point has been independently confirmed.
