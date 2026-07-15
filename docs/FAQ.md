# Frequently asked questions

## Project scope

### What is YaCompress?

YaCompress is an Ansible Collection for creating, extracting, verifying, checksumming, and rotating standard Linux archive files through explicit modules.

### What problem does it solve?

It covers the archive lifecycle around retained backup files: create, verify, record a SHA-256 manifest, verify later, and apply retention.

### Is YaCompress a complete backup system?

No. It does not provide a remote repository, encryption, deduplication, incremental snapshots, authentication, ransomware-resistant immutability, or application-consistent snapshots.

### Does it use a proprietary archive format?

No. It creates ordinary TAR-family and ZIP archives that can be read with standard system tools.

### Is it Linux-only?

The Collection is Linux-first because it intentionally uses native Linux archive utilities. The produced ZIP and TAR-family archives remain portable, but module execution is tested on Linux.

### Does YaCompress replace Borg, Restic, or Kopia?

No. Those products manage repository-based backups with features such as deduplication, encryption, snapshots, and remote storage. YaCompress is for transparent standard archive files managed by Ansible.

### Does YaCompress replace enterprise backup software?

No. Use dedicated backup software when you need centralized policy, catalogues, tape, immutable storage, replication, encryption key management, or vendor support.

## Ansible alternatives

### Why not use `community.general.archive`?

Use `community.general.archive` for straightforward, portable archive creation with a Python-oriented implementation. Choose YaCompress when you need native pigz, zstd, sparse TAR handling, explicit worker limits, verification, manifests, or retention around existing archives.

### Is YaCompress always faster than `community.general.archive`?

No universal claim is made. The included benchmark showed substantial gains on one tested CachyOS host, but results depend on CPU, storage, files, compressor versions, levels, cache state, and concurrency.

### Why not use `ansible.builtin.unarchive`?

`ansible.builtin.unarchive` remains a good general extraction module. YaCompress provides a matching native archive creation/extraction path and lifecycle modules, but it is not a mandatory replacement for ordinary extraction.

### Why not call `tar` with `ansible.builtin.command`?

Direct commands are appropriate for simple local workflows. YaCompress adds argument validation, Check Mode behavior, format detection, structured results, guarded source deletion, tests, and a stable Ansible interface.

### Why not use `ansible.builtin.shell`?

Shell tasks increase quoting and injection risk and usually return less structured information. YaCompress invokes native tools with argument lists rather than shell command strings.

## Formats and compressors

### Which formats are supported?

`tar`, `tar.gz`, `tar.bz2`, `tar.xz`, `tar.zst`, and ZIP.

### Which format should I choose by default?

For Linux backup workflows, start by testing `tar.zst` with a moderate level such as `3`. Use `tar.gz` for maximum compatibility, plain `tar` for already-compressed data, and `tar.xz` when archive size matters more than backup speed.

### When should I use `tar` without compression?

Use plain TAR for media, encrypted files, compressed database dumps, or other data that gains little from recompression. It can also be useful when storage or network throughput is not the bottleneck.

### What is the difference between gzip and pigz?

Both produce gzip-compatible streams. gzip is normally single-threaded; pigz parallelizes compression across CPU cores.

### How do I enable pigz?

Set `compression: pigz` to require it, or `compression: auto` to prefer pigz and fall back to gzip.

### Why is `compression` not automatically pigz for `tar.gz`?

The current default preserves existing behavior and broad compatibility. A future default change would require an explicit compatibility decision rather than a silent patch release change.

### What does `threads: auto` mean?

It allows supported compressors to use their native automatic worker selection. On shared production hosts, a fixed positive integer may be safer.

### Does increasing compression level always help?

No. Higher levels usually cost more CPU and time, and gains may be small or nonexistent for already-compressed data. Measure with representative data.

### Why can zstd create a smaller archive than xz in some tests?

Compression results depend on the dataset and compressor settings. xz does not guarantee the smallest result for every input.

### Is ZIP recommended for Linux backups?

ZIP is useful for exchange and desktop compatibility. TAR-family formats usually preserve Linux-oriented structure and sparse-file behavior more naturally.

### Does ZIP support multiple source paths?

The current `multi_archive` interface supports multiple sources for TAR-family creation, not ZIP.

## Archive creation

### Can I archive multiple source paths?

Yes, for TAR-family formats. Sources must have unique base names and must not overlap.

### Can the destination be inside the source directory?

No. The module rejects that relationship to prevent the archive from consuming itself during creation.

### Are nested or overlapping source paths allowed?

No. Overlapping sources are rejected because they create duplicate, ambiguous archive content.

### Can I select only part of a directory?

Yes. Use relative `include` patterns with a single directory source.

### Can I exclude files?

Yes. `exclude` accepts relative archive-member patterns.

### Which exclude patterns are rejected?

Absolute paths and patterns that normalize outside the source with leading parent traversal are rejected.

### Are ordinary glob patterns allowed?

Yes. Examples include `*.log`, `cache/**`, and `temporary-*`.

### Does YaCompress follow symbolic links?

Behavior depends on the operation and native backend. Manifest enumeration and rotation do not follow symlinks. Archive creation preserves native tool semantics and should be tested for the chosen format and options.

### Does it support sparse files?

Yes, for TAR-family archive creation with `sparse: true` and GNU tar. A real-host test validated a logical file larger than 5 GiB while preserving sparse allocation after restore.

### Can I delete source data after archiving?

Yes, with `delete_source: true`. The module forces archive verification before deletion and reports partial deletion failures.

### Is source deletion transactional?

No. Verification reduces accidental loss, but deletion remains a filesystem operation and does not provide application-level transactions.

### Does YaCompress freeze active applications?

No. Use an application dump, quiescing procedure, filesystem snapshot, or storage snapshot before archiving mutable databases, virtual machines, and similar workloads.

## Verification and manifests

### What does archive verification prove?

It proves that the selected native backend could read the archive structure at that time.

### What does archive verification not prove?

It does not prove that the source was complete, the application was consistent, extraction is safe, content is semantically correct, or the archive came from a trusted party.

### What is the difference between `verify_archive` and `archive_verify`?

`verify_archive` checks a newly created archive before replacement or source deletion. `archive_verify` performs a standalone read-only check of an existing retained archive.

### Why use a SHA-256 manifest?

A manifest detects changed, missing, or unexpected files covered by its stored selection policy.

### Is a manifest a digital signature?

No. An attacker who can replace both archive and manifest can make them agree. Protect manifests separately or use a future signing mechanism.

### Does a manifest encrypt the backup?

No. Checksums provide integrity detection, not confidentiality.

### Should I verify archives periodically?

Yes. Retained archives can be damaged after creation. Scheduled structural verification and manifest verification help detect storage corruption before recovery is needed.

### Do verification and manifests replace restore tests?

No. A real restore test is the strongest operational proof that the recovery path works.

### Can verification continue without failing the playbook?

Yes. `archive_verify` supports `fail_on_error: false`, and `archive_manifest` supports `fail_on_mismatch: false` for reporting workflows.

## Rotation

### How does rotation work?

`archive_rotate` selects regular files by patterns and removes files that exceed count and/or age limits while protecting the newest `min_keep` files.

### Can I preview rotation?

Yes. Run the task in Ansible Check Mode and inspect `planned_removals`.

### Does rotation follow symbolic links?

No. It skips symbolic links and avoids traversing symbolic-link directories.

### Can I rotate archive and manifest files together?

Use separate rotation tasks with matching naming conventions. This keeps each policy explicit and independently reviewable.

### Is deleted backup data recoverable?

Not by YaCompress. Keep independent copies when your recovery requirements demand them.

## Performance

### Which backend was fastest in the reference benchmark?

On the tested CachyOS host, zstd and pigz were the fastest large-data cases. This is a reference measurement, not a guarantee for other systems.

### Why are many small files slow?

Directory walking, metadata operations, path handling, and archive headers can dominate when payload files are tiny.

### Can more threads make backups slower?

Yes. Storage contention, memory pressure, scheduling overhead, and multiple concurrent jobs can outweigh compressor parallelism.

### Should production jobs use all CPU cores?

Not automatically. Use a fixed worker count on shared systems and measure backup-window impact.

### Does verification add overhead?

Yes. Structural verification reads the completed archive again. Manifest verification also hashes data. That cost buys earlier failure detection.

### How do I run the benchmark?

Build and install the Collection locally, install `community.general`, then run `benchmarks/run.py` with representative size, file count, and multiple iterations. See `docs/BENCHMARKING.md`.

### Can benchmark results from CI be used for marketing?

No. Small CI runs validate the framework, not production performance.

## Storage and operating systems

### Which Linux families are tested?

CI covers Debian, Ubuntu, Fedora, Rocky Linux, AlmaLinux, Oracle Linux, Arch Linux, and openSUSE families.

### Does container CI guarantee support on my server?

No. Test the exact OS release, native tool versions, filesystem, security policy, mount options, and recovery host.

### Can I use NFS?

Yes, but NFS behavior depends on server configuration, mount options, UID mapping, caching, locking, quotas, and rename semantics. Run the host-storage validation script against the real mount.

### Can I use Btrfs, XFS, or ext4?

They are reasonable targets, but production validation should use the actual destination filesystem and workload.

### Does atomic replacement work everywhere?

YaCompress writes beside the destination and uses replacement semantics supported by Ansible and the filesystem. Network and clustered filesystems may expose different visibility and cache behavior.

### How much temporary space is required?

Archive creation may temporarily require space for both the old destination and the new archive. Monitor quotas and free space.

### Does YaCompress support SELinux or AppArmor?

It does not disable or bypass them. Validate the exact policy on the target host and manage labels with dedicated Ansible modules where necessary.

### Is YaCompress FIPS-compliant?

The Collection does not make a blanket FIPS certification claim. Behavior depends on the host policy and installed native tools.

## Security

### How do I report a vulnerability?

Use GitHub Private Vulnerability Reporting from the repository Security tab. Do not open a public issue for a suspected vulnerability.

### Does YaCompress safely extract hostile archives?

No. YaCompress is not an extraction sandbox. Treat external archives as hostile and extract them only in an isolated, unprivileged directory after inspecting members.

### Does compression provide encryption?

No. Use encrypted transport, encrypted storage, encrypted filesystems, or a repository backup product with key management.

### Does YaCompress need root?

No by design. Run it with the least privileges required to read sources and write destinations.

### Can an untrusted playbook operator misuse the modules?

Yes. Anyone who can change trusted Ansible inputs and run with sufficient privileges can direct filesystem operations. YaCompress validates mistakes and unsafe relationships; it cannot override the operator's authority.

## Installation and releases

### How do I install the Collection?

Use `ansible-galaxy collection install mraibo.yacompress` after the release is published, or build and install the local Galaxy archive from source.

### How do I see module documentation?

Run `ansible-doc mraibo.yacompress.multi_archive` and the corresponding command for `archive_verify`, `archive_manifest`, or `archive_rotate`.

### Which Ansible version is required?

Use the supported range documented in `galaxy.yml`, CI, and release notes. Real-host acceptance testing passed with `ansible-core 2.19.11`.

### Are releases backward compatible?

Patch and minor releases should avoid unexpected breaking changes. Any incompatible change must be documented and versioned deliberately.

### Why is the project version still 1.6.0 after documentation changes?

Documentation-only changes do not necessarily require a new Collection version before the first 1.6.0 publication. The final release audit will ensure that the packaged contents and release notes match the tag.

### Where are release instructions documented?

See `docs/RELEASING.md` and the upcoming Galaxy release checklist.

## Troubleshooting

### The module cannot find zstd, pigz, or xz. What should I do?

Install the selected native backend from the managed host's trusted package repositories, or choose a format available on that host.

### Why did explicit threads fail for `tar.gz`?

Explicit gzip worker counts require pigz. Ordinary gzip does not provide the same worker option.

### Why did my include pattern fail?

`include` patterns must be relative, remain within the source, and match at least one path.

### Why did my exclude pattern fail?

Exclude patterns must be relative and must not normalize outside the source archive tree.

### Why was Check Mode reported as changed?

Check Mode reports whether the real operation would change the filesystem while avoiding the actual mutation.

### Why does an archive task run again?

Archive creation is not content-addressed idempotency. Use `creates`, timestamped workflows, external scheduling logic, or explicit conditions according to the backup policy.

### Why is my compressed archive larger than expected?

The input may already be compressed or encrypted, the level may be low, or archive metadata may dominate a very small dataset. Compare against plain TAR and representative levels.

### Why is my backup slow despite many threads?

The bottleneck may be storage, metadata, network latency, CPU throttling, memory pressure, or concurrent workloads rather than compression.

### Where should I ask ordinary questions or report bugs?

Use public GitHub issues for non-sensitive bugs, compatibility reports, documentation problems, and feature requests.
