# YaCompress Design Philosophy

YaCompress is deliberately narrow: it manages the lifecycle of standard archives on Linux hosts through Ansible. It does not try to become a proprietary backup repository, a cross-platform compression library, or a wrapper around every archive command.

The project follows a small set of principles that guide implementation, review, documentation, and future scope.

## 1. Solve the archive lifecycle, not only archive creation

Creating a compressed file is only the first step of an operational backup workflow. YaCompress keeps the lifecycle visible as separate Ansible operations:

```text
create → structural verify → checksum manifest → retention → restore test
```

Each operation has a distinct responsibility:

- `multi_archive` creates or extracts an archive;
- `archive_verify` checks whether an existing archive can be read structurally;
- `archive_manifest` records or verifies file identity with SHA-256;
- `archive_rotate` applies an explicit retention policy.

The modules are separate because failure handling, Check Mode behavior, idempotency, and permissions differ. A single all-purpose module would hide those differences behind mutually exclusive parameters and make incidents harder to diagnose.

## 2. Linux-first, not universal by accident

YaCompress uses native Linux archive tools such as GNU tar, pigz, zstd, xz, bzip2, zip, and unzip. This is intentional.

The approach provides:

- native threading where the backend supports it;
- standard command-line behavior familiar to Linux administrators;
- compatibility with existing operational tooling;
- no additional Python compression dependency;
- direct use of formats that remain readable without YaCompress.

The consequence is equally explicit: managed Windows hosts, BSD-specific tar variants, and platforms without the required native tools are outside the current support claim.

Portability matters, but pretending to support every platform without continuous testing would be less reliable than a clear Linux boundary.

## 3. Prefer standard formats over private repositories

YaCompress produces standard TAR-family and ZIP archives. It does not define a repository database, chunk format, pack file, or catalog that is required for recovery.

A backup can therefore be inspected or restored with ordinary tools:

```bash
tar -I zstd -tf application.tar.zst
tar -I zstd -xf application.tar.zst
unzip application.zip
```

This reduces recovery dependencies and vendor lock-in. It also means YaCompress does not provide native deduplication, incremental snapshot graphs, encryption repositories, or content-addressed storage. Borg, Restic, and Kopia are better choices when those properties are required.

## 4. Native capability before new code

The project follows the Ponytail ladder:

1. confirm the feature is needed;
2. reuse existing project behavior;
3. use the Python standard library;
4. use native platform functionality;
5. add the minimum new code only after the earlier options fail.

Examples:

- compression is delegated to native tools instead of reimplementing codecs;
- atomic replacement uses the filesystem rename semantics already provided by the operating system;
- SHA-256 uses Python's standard `hashlib`;
- JSON manifests use the standard `json` module;
- Ansible Check Mode and module result conventions are used instead of custom dry-run protocols.

No abstraction is added merely to make the code look more framework-like. Shared helpers are introduced only when multiple real callers need identical behavior.

## 5. Safety before convenience

Archive workflows can destroy source data or old backups. YaCompress therefore treats destructive behavior as a separate safety boundary.

Key rules include:

- source deletion occurs only after successful archive creation and verification;
- archives and manifests are built in temporary paths beside their destination;
- completed files replace the destination atomically;
- unsafe source/destination overlap is rejected;
- traversal outside an intended source root is rejected;
- symbolic links are not silently followed by verification, rotation, or manifest discovery;
- rotation protects at least the configured `min_keep` newest files;
- partial deletion failures report what was removed and what remains;
- Check Mode does not modify the filesystem.

The project prefers an explicit failure over a convenient but ambiguous fallback.

## 6. Atomic replacement, not in-place mutation

Writing directly into the final archive path creates a dangerous state: a failed compressor can leave a truncated file with the expected production name.

YaCompress instead follows this pattern:

```text
create temporary file beside destination
        ↓
run verification when requested
        ↓
atomically replace destination
```

The temporary file is created on the same filesystem as the destination so the final rename does not cross filesystem boundaries.

The trade-off is temporary storage: enough free space must exist near the destination for the new archive while an old archive may still be present.

## 7. Honest idempotency

Ansible modules should not report `changed: false` merely because repeated execution is expected.

If YaCompress rewrites an archive, it reports a change. Idempotency is available only when the requested operation has a meaningful guard, for example:

- `creates` for one-time extraction or creation;
- unchanged deterministic manifest content;
- a rotation policy with nothing eligible for removal;
- read-only verification modules that always return `changed: false`.

This makes playbook output useful during operations and avoids false confidence.

## 8. Verification is layered

No single check proves that a backup is recoverable.

YaCompress separates three different questions:

1. **Structural verification:** can the archive backend read its structure?
2. **Checksum verification:** does the retained file still match its recorded SHA-256 manifest?
3. **Restore validation:** can the archive be extracted and can the application use the restored data?

The first two are automated by the collection. The third remains an operational responsibility because application consistency and restore acceptance criteria are application-specific.

A checksum manifest is also not a digital signature. If an attacker can modify both the archive and its manifest, SHA-256 alone does not establish authenticity. Store the manifest separately, protect it with access controls, or sign it when malicious modification is part of the threat model.

## 9. Explicit operations over hidden orchestration

The collection does not currently provide a monolithic `backup_policy` module that silently creates, verifies, signs, rotates, and restores data.

Explicit tasks are preferred because they provide:

- visible ordering;
- distinct registered results;
- precise Ansible `block`/`rescue` handling;
- independent permissions;
- independent scheduling;
- easier troubleshooting and retry.

Reusable roles or higher-level policy modules may be considered later only if real usage shows repeated orchestration that cannot be expressed clearly with existing Ansible constructs.

## 10. Compatibility is tested, not assumed

Compatibility claims are limited to environments represented by continuous tests or explicit host validation.

The project currently tests modern and enterprise variants from the Debian, Ubuntu, Fedora, Rocky, AlmaLinux, Oracle Linux, Arch, and openSUSE families. It also validates older GNU tar behavior, `ansible-core 2.15`, sparse files larger than 5 GiB, and separate-filesystem destination handling.

Container coverage is a strong signal, not a guarantee for every production configuration. Exact SLES/RHEL service packs, NFS mounts, clustered filesystems, SELinux enforcing, FIPS, quotas, and identity mapping must be validated on the real target host.

## 11. Performance claims require reproducible evidence

YaCompress supports native parallel backends, but the project does not claim that one format or module is always faster.

Performance depends on:

- CPU model and core count;
- compression level;
- file count and average file size;
- source and destination storage;
- cache state;
- already-compressed content;
- network filesystem behavior;
- competing workload.

The included benchmark framework records raw data and validates the produced archives. Published claims should include the hardware, software versions, dataset, parameters, iterations, and raw CSV.

## 12. Documentation is part of the interface

For infrastructure tools, unclear behavior is an operational defect.

Every non-trivial feature should document:

- what it does;
- what it intentionally does not do;
- the destructive boundary;
- Check Mode behavior;
- return values;
- failure semantics;
- a runnable example;
- relevant compatibility limits.

Architecture Decision Records preserve the reasons behind decisions so future contributors can distinguish deliberate constraints from accidental implementation details.

## 13. Future changes must preserve the project boundary

A proposed feature belongs in YaCompress when it materially improves the safe lifecycle of standard Linux archives under Ansible.

Good candidates:

- manifest signing;
- reusable restore-test workflows;
- retention policies built on proven operational demand;
- clearer reporting and audit output.

Poor candidates:

- proprietary archive formats;
- a general-purpose synchronization engine;
- an object-storage client unrelated to archive lifecycle;
- an embedded scheduler that duplicates Ansible or systemd;
- abstractions added only for stylistic uniformity.

The target is not the largest collection. The target is the smallest trustworthy collection that covers the complete lifecycle of standard Linux archives.
