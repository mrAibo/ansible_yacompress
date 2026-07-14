# Enterprise storage and security-profile validation

YaCompress creates its temporary archive in the destination directory and replaces the final archive only after successful creation and optional verification. This design avoids cross-filesystem rename failures between the source and destination and keeps temporary data on the same filesystem as `dest`.

## Continuously tested storage scenario

The `Enterprise storage` workflow runs on every pull request and push to `main`.

It validates:

- a sparse source file with a logical size greater than 5 GiB;
- GNU tar sparse-file detection through `sparse: true`;
- zstd archive creation and integrity verification;
- replacement of an existing destination archive;
- extraction of the replacement archive;
- restored logical size and sentinel content;
- restored sparse allocation;
- cleanup of temporary `.multi_archive-*` directories;
- a destination on `/dev/shm`, which is a separate tmpfs from the source workspace.

The test does not allocate or upload 5 GiB of physical data. It uses filesystem holes and verifies both logical size and allocated blocks.

## Sparse files

Enable sparse-file handling for TAR-family formats:

```yaml
- name: Archive a sparse virtual disk image
  mraibo.yacompress.multi_archive:
    source: /var/lib/libvirt/images/server.raw
    dest: /backup/server.raw.tar.zst
    state: archived
    sparse: true
    compression_level: 1
    threads: auto
    verify_archive: true
```

`sparse` is rejected for ZIP and for `state: unarchived`. GNU tar records sparse extents during archive creation and recreates holes during extraction.

## Real NFS or clustered-filesystem validation

CI cannot reproduce an organization's exact NFS server, mount options, cache behavior, locking, quotas, or clustered filesystem. Run the supplied host validator against the mounted destination:

```bash
./tests/run_host_storage_validation.sh /mnt/backup/yacompress-validation
```

Require an exact filesystem type when desired:

```bash
REQUIRE_FS_TYPE=nfs4 \
./tests/run_host_storage_validation.sh /mnt/backup/yacompress-validation
```

Typical values include `nfs`, `nfs4`, `xfs`, `ext4`, `btrfs`, `gfs2`, and `ocfs2`. Use the value reported by `findmnt -T` on the target host.

The validator builds and installs the collection, runs the same greater-than-5-GiB sparse round trip, replaces an existing archive, verifies restored data, and reports the detected filesystem.

## SELinux enforcing validation

Container tests do not prove SELinux policy compatibility because the host kernel and policy determine enforcement. Run on the exact target host and require enforcing mode:

```bash
REQUIRE_SELINUX_ENFORCING=1 \
./tests/run_host_storage_validation.sh /var/backups/yacompress-validation
```

The test exercises file creation, temporary directories, native compressors, atomic replacement, and extraction under the active host policy. It does not promise preservation of arbitrary SELinux labels from source files; use dedicated Ansible file/SELinux modules when labels must be assigned explicitly.

## FIPS validation

The module does not implement cryptography and does not calculate hashes. It delegates archive operations to installed native tools. FIPS acceptance therefore depends on the operating system, its enabled crypto policy, and the exact native packages.

Run on an actual FIPS-enabled host:

```bash
REQUIRE_FIPS=1 \
./tests/run_host_storage_validation.sh /var/backups/yacompress-validation
```

The validator requires `/proc/sys/crypto/fips_enabled` to equal `1` before running. A normal container on a non-FIPS host is not presented as FIPS validation.

## Operational considerations

Before production use, also validate:

- free space for the temporary archive beside `dest`;
- destination quotas and file-size limits;
- NFS `root_squash`, UID/GID mapping, and mount options;
- backup-window CPU limits and `threads` settings;
- interrupted jobs and cleanup monitoring;
- restore operations on the actual recovery host;
- files that change while they are being archived.

YaCompress provides archive consistency for the bytes read by native tar. It does not provide application-level snapshots. Databases, virtual machines, and active application data may require filesystem snapshots, application quiescing, or native backup APIs before archiving.
