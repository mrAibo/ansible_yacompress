# Why YaCompress Exists

YaCompress exists because creating an archive is only one step in a dependable backup workflow.

Linux already has excellent archive tools. Ansible already has mature modules for common archive tasks. YaCompress does not attempt to replace all of them. It provides a focused, Linux-first Ansible workflow for teams that want to manage the complete lifecycle of standard archives:

```text
create → structurally verify → record checksums → verify later → rotate → restore-test
```

The project deliberately keeps those operations separate. Each step can fail independently, can be inspected independently, and can be reused in an existing backup design.

## The problem it solves

A command such as `tar -cf`, `zip`, or `gzip` can create an archive. Production operations usually need additional guarantees:

- the completed archive can be read;
- the archive was not replaced with a partial file after a failed run;
- source deletion happens only after successful verification;
- retained backups can be checked again days or months later;
- checksum drift, missing files, and unexpected files can be reported;
- old backups can be removed using an explicit policy and Check Mode preview;
- the result remains a standard TAR-family or ZIP archive that can be recovered without YaCompress.

Shell scripts can assemble these steps, but each organisation then has to design and maintain its own validation, error handling, atomic replacement, retention logic, Check Mode equivalent, and Ansible reporting.

YaCompress packages those concerns as small Ansible modules with documented return values and a shared test matrix.

## What YaCompress is

YaCompress is a Linux-focused Ansible Collection for standard archive workflows.

It currently provides:

| Module | Responsibility |
|---|---|
| `mraibo.yacompress.multi_archive` | Create or extract TAR-family and ZIP archives using native tools |
| `mraibo.yacompress.archive_verify` | Perform read-only structural verification of an existing archive |
| `mraibo.yacompress.archive_manifest` | Create or verify deterministic SHA-256 manifests |
| `mraibo.yacompress.archive_rotate` | Apply count- and age-based retention with Check Mode preview |

The modules are separate by design. Creating, verifying, checksumming, and deleting are different responsibilities and should not be hidden behind one large action.

## Comparison with `community.general.archive`

`community.general.archive` is a mature, portable module and is the right default for many ordinary archive tasks. It supports multiple paths, exclusions, source removal, Check Mode, filesystem ownership and permission controls, and the common `bz2`, `gz`, `tar`, `xz`, and `zip` formats. It uses Python standard-library archive implementations on the managed host.

YaCompress has a narrower platform scope and a broader archive-lifecycle scope. It uses native Linux tools and adds operations that intentionally live outside archive creation.

| Capability | `community.general.archive` | YaCompress |
|---|---:|---:|
| Create standard TAR, gzip, bzip2, xz, or ZIP output | Yes | Yes |
| Pure Python implementation | Yes | No; native Linux tools |
| Native `pigz` support | No documented backend | Yes |
| Native `zstd` TAR archives | No documented format | Yes, `tar.zst` |
| Configurable native worker limits | No documented option | Yes, pigz/xz/zstd |
| Sparse-file-aware TAR creation | No documented option | Yes |
| Multiple explicit source paths | Yes | Yes, TAR-family creation |
| Source removal after archive creation | Yes | Yes, only after successful verification |
| Atomic destination replacement | Ansible atomic-write support | Explicit temporary archive beside `dest`, then replacement |
| Verify the newly created archive before source deletion | No dedicated option | Yes |
| Verify an existing retained archive | No separate module | Yes |
| Deterministic SHA-256 manifest creation and verification | No | Yes |
| Count- and age-based archive rotation | No | Yes |
| Check Mode retention preview | Not applicable | Yes |
| Compression and throughput metrics | No dedicated archive metrics | Yes |
| Broad non-Linux portability | Better fit | Not a goal |

This table is a capability comparison, not a performance claim. Performance depends on the dataset, CPU, storage, compression level, tool versions, and worker count. Use the repository benchmark suite on the target system before drawing conclusions.

Official reference: <https://docs.ansible.com/projects/ansible/latest/collections/community/general/archive_module.html>

### Choose `community.general.archive` when

- a simple archive-creation task is sufficient;
- portability and Python-only execution matter more than native Linux backends;
- you need its ownership, mode, attributes, or SELinux destination options;
- you already depend on `community.general` and do not need a lifecycle workflow.

### Choose YaCompress when

- managed hosts are Linux systems with native archive tools;
- `pigz`, `zstd`, worker limits, or sparse files matter;
- source deletion must be gated by successful archive verification;
- retained archives need scheduled structural checks;
- you need checksum manifests and explicit rotation policies;
- standard archive formats and transparent recovery are required.

The projects can also be used together. YaCompress is not intended to turn every archive task into a YaCompress task.

## Comparison with `ansible.builtin.unarchive`

`ansible.builtin.unarchive` is the standard choice for unpacking an existing archive, optionally after copying it from the controller. YaCompress does not try to replace it for ordinary extraction.

Use `ansible.builtin.unarchive` when its interface covers the task. Use `multi_archive` extraction when the same native format handling and lifecycle interface are useful for a YaCompress-managed workflow.

Official reference: <https://docs.ansible.com/projects/ansible/latest/collections/ansible/builtin/unarchive_module.html>

## Comparison with `tar` or shell scripts

Native commands remain the foundation of YaCompress. The Collection does not reimplement compression algorithms.

| Direct commands or scripts | YaCompress |
|---|---|
| Maximum freedom | Deliberately constrained interface |
| No Ansible Collection dependency | Native Ansible result and Check Mode behaviour |
| Operator designs validation and cleanup | Tested validation and cleanup paths |
| Error handling varies per script | Consistent module failures and return values |
| Retention commonly uses custom `find` commands | Explicit policy, path checks, `min_keep`, and preview |
| Metrics require extra scripting | Standard return values |

Use direct commands when a small local script is genuinely simpler. Use YaCompress when the same archive policy must be understandable and repeatable across managed hosts.

## Comparison with Borg, Restic, and Kopia

Borg, Restic, and Kopia are repository-based backup systems. They provide capabilities such as deduplication, snapshots, encryption, repository maintenance, and remote backends. YaCompress does not provide those features and should not be presented as their replacement.

YaCompress is a better fit when:

- the required artifact is a normal TAR-family or ZIP file;
- recovery must work with ordinary system tools;
- an existing NAS, filesystem, removable medium, or transfer process stores archives;
- Ansible should orchestrate the workflow without introducing a backup repository format.

Choose a repository-based backup system when deduplication, encryption, incremental snapshots, object storage, or repository-wide retention are primary requirements.

## Why standard archives

YaCompress deliberately produces standard archives instead of a proprietary container format.

Benefits:

- recovery does not require YaCompress;
- archives can be inspected with familiar operating-system tools;
- migration to another automation system remains possible;
- disaster recovery has fewer software dependencies;
- archives can be transferred, mounted, scanned, or stored using existing infrastructure.

The trade-off is equally explicit: standard archives do not automatically provide deduplication, incremental snapshots, encryption, or repository-level consistency.

## Restore-first philosophy

A backup is useful only when it can be restored.

YaCompress therefore treats archive creation as the beginning of the workflow, not the end:

1. Create the archive without replacing the previous destination until creation succeeds.
2. Read the completed archive before optional source deletion.
3. Perform an independent structural check when operational separation is useful.
4. Record SHA-256 checksums in a deterministic manifest.
5. Recheck retained files on a schedule.
6. Rotate only after the new backup has passed the required checks.
7. Periodically extract into a disposable location and test the recovered application or data.

Structural verification and SHA-256 checks do not prove application consistency. Active databases and mutable applications still require an application-aware dump, snapshot, lock, or quiesce procedure.

## Safety boundaries

YaCompress is designed to reduce common operational risks, not to eliminate every backup risk.

It provides:

- Check Mode without filesystem changes;
- atomic replacement for newly created archives and manifests;
- validation of source, destination, include, and manifest paths;
- no symlink following during manifest discovery, verification, or rotation;
- verification before `delete_source`;
- explicit reporting of partial deletion failures;
- `min_keep` protection during rotation;
- tested large sparse-file handling.

It does not provide:

- encryption;
- digital signatures;
- immutable storage;
- distributed locking;
- application-consistent database snapshots;
- protection from an attacker who can modify both an archive and its unsigned manifest.

Store manifests separately or sign them when malicious modification is part of the threat model.

## When YaCompress is a good fit

Typical uses include:

- application configuration and data directories;
- database dump files created by application-specific tools;
- VM exports and sparse raw images;
- CI/CD artifacts;
- air-gapped or removable-media archives;
- NAS or NFS archive workflows;
- environments that already standardise on Ansible and Linux native tools.

## When not to use it

Do not choose YaCompress merely because it has more options.

Prefer another solution when:

- `community.general.archive` already covers the task cleanly;
- `ansible.builtin.unarchive` is all that is needed;
- the managed host is not Linux;
- deduplication, encryption, incremental backups, or object-storage repositories are required;
- the data source cannot be made application-consistent;
- a direct one-line native command is genuinely the simplest maintainable solution.

## Evidence, not slogans

Project claims are intended to remain testable:

- official `ansible-test sanity` and integration tests;
- real archive round trips using native tools;
- distribution and enterprise Linux matrices;
- openSUSE validation;
- sparse-file testing above 5 GiB;
- a reproducible benchmark framework that records raw results.

YaCompress should earn trust through transparent formats, explicit limits, reproducible tests, and honest comparisons—not by claiming to be universally better.