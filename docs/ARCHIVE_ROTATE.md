# Archive rotation

`mraibo.yacompress.archive_rotate` removes old archive files from a controlled directory. It is deliberately narrower than a general file-deletion module: only regular files matching explicit archive filename patterns are considered, symbolic links are skipped, and every result reports exactly what was matched, kept, planned, and removed.

## Basic count-based rotation

Keep the ten newest archives:

```yaml
- name: Keep the ten newest application backups
  mraibo.yacompress.archive_rotate:
    directory: /srv/backups/application
    patterns:
      - 'application-*.tar.zst'
    keep_last: 10
```

Files are ordered by modification time, newest first. Paths are used as a deterministic tie-breaker when modification times are equal.

## Age-based rotation

Remove archives older than 30 days while always preserving the two newest matching files:

```yaml
- name: Remove old application backups
  mraibo.yacompress.archive_rotate:
    directory: /srv/backups/application
    patterns:
      - 'application-*.tar.zst'
    max_age_days: 30
    min_keep: 2
```

`min_keep` defaults to `1`. Set it to `0` only when deleting every matching archive is an intentional and reviewed policy.

## Combined count and age policy

```yaml
- name: Enforce count and age limits
  mraibo.yacompress.archive_rotate:
    directory: /srv/backups/application
    patterns:
      - 'application-*.tar.zst'
    keep_last: 14
    max_age_days: 45
    min_keep: 2
```

When both limits are set, a file becomes a removal candidate when either condition is true:

- it is outside the newest `keep_last` files; or
- it is older than `max_age_days`.

The newest `min_keep` matching files are protected from both conditions.

## Preview with Check Mode

Always preview a new retention policy before applying it:

```bash
ansible-playbook rotate.yml --check
```

Or force Check Mode for one task:

```yaml
- name: Preview archive rotation
  mraibo.yacompress.archive_rotate:
    directory: /srv/backups/application
    patterns:
      - 'application-*.tar.zst'
    keep_last: 10
    max_age_days: 30
  check_mode: true
  register: rotation_preview

- name: Show planned removals
  ansible.builtin.debug:
    var: rotation_preview.planned_removals
```

In Check Mode:

- no file is removed;
- `changed` is `true` when files would be removed;
- `removed` is empty;
- `planned_removals` contains the proposed deletion list;
- `bytes_reclaimed` reports the space that would be reclaimed.

## Default archive patterns

When `patterns` is omitted, the module considers:

```text
*.tar
*.tar.gz
*.tgz
*.tar.bz2
*.tbz2
*.tar.xz
*.txz
*.tar.zst
*.zip
```

For production backup directories, narrower application-specific patterns are safer:

```yaml
patterns:
  - 'database-prod-*.tar.zst'
```

Patterns match filenames, not full paths.

## Recursive rotation

Subdirectories are ignored by default. Enable recursive discovery explicitly:

```yaml
- name: Rotate archives below per-host directories
  mraibo.yacompress.archive_rotate:
    directory: /srv/backups/hosts
    patterns:
      - '*.tar.zst'
    keep_last: 50
    recursive: true
```

The count and age policy applies to the combined result set. It does not keep a separate quota for each subdirectory. Use one task per subdirectory when each host or application needs an independent retention policy.

## Return values

```yaml
- name: Rotate backups
  mraibo.yacompress.archive_rotate:
    directory: /srv/backups/application
    patterns:
      - 'application-*.tar.zst'
    keep_last: 7
  register: rotation

- name: Report reclaimed space
  ansible.builtin.debug:
    msg: >-
      Removed {{ rotation.removed | length }} archives and reclaimed
      {{ rotation.bytes_reclaimed }} bytes.
```

The module returns:

- `matched`: all matching regular files, newest first;
- `kept`: files retained by the policy;
- `planned_removals`: the complete selected deletion list;
- `removed`: files actually deleted;
- `bytes_reclaimed`: selected byte total, including previews.

## Failure behavior

Deletion is performed one file at a time. If a deletion fails, the task stops and reports:

- files already removed;
- the complete planned removal list;
- files that the policy intended to keep.

A partial deletion cannot be rolled back. Check permissions, filesystem health, mounts, immutable attributes, quotas, and backup ownership before applying rotation.

## Safety boundaries

The module intentionally applies these restrictions:

- the target must be an existing directory;
- at least one of `keep_last` or `max_age_days` is required;
- negative retention values are rejected;
- an empty pattern list is rejected;
- only regular files are considered;
- symbolic links are never followed or removed;
- symlinked directories are not traversed;
- matched real paths must remain beneath the configured directory;
- Check Mode never changes the filesystem.

## Recommended backup workflow

A safe sequence is:

1. create an archive with `multi_archive` and `verify_archive: true`;
2. optionally run `archive_verify` on scheduled or transferred archives;
3. rotate only after the new archive has completed successfully;
4. periodically perform a real restore test.

```yaml
- name: Create verified backup
  mraibo.yacompress.multi_archive:
    source: /srv/application
    dest: "/srv/backups/application/application-{{ ansible_date_time.iso8601_basic_short }}.tar.zst"
    state: archived
    compression_level: 3
    threads: auto
    verify_archive: true

- name: Rotate completed backups
  mraibo.yacompress.archive_rotate:
    directory: /srv/backups/application
    patterns:
      - 'application-*.tar.zst'
    keep_last: 14
    max_age_days: 45
    min_keep: 2
```

Do not run retention against a directory where archives are still being written under their final names. YaCompress creates archives through temporary files and atomic replacement, which avoids exposing incomplete YaCompress archives, but other backup producers may not provide that guarantee.
