# YaCompress roadmap

This roadmap describes direction, not delivery dates. Items become commitments only after a focused issue or pull request defines the user need, compatibility impact, design, tests, and documentation.

## Project goal

YaCompress aims to be a dependable Ansible solution for managing the lifecycle of standard Linux archive files:

```text
create → verify → manifest → rotate → restore-test
```

The project prioritizes recoverability, operational safety, transparent formats, native Linux tooling, and evidence-based performance guidance.

## Completed foundation — 1.6

The current foundation includes:

- native TAR-family and ZIP creation and extraction;
- gzip, pigz, bzip2, xz, zstd, and uncompressed TAR workflows;
- multiple TAR source paths;
- sparse-file support;
- automatic or fixed compression workers;
- structural verification during and after archive creation;
- guarded source deletion after successful verification;
- deterministic SHA-256 manifests for files and directory selections;
- detection of changed, missing, and unexpected files;
- count- and age-based rotation with `min_keep` protection;
- Check Mode for planned destructive operations;
- atomic destination replacement where supported by the target filesystem;
- validation of source, destination, include, exclude, and manifest paths;
- unit, sanity, integration, distribution, storage, and real-host acceptance tests;
- reproducible benchmarks and operator documentation.

## Near-term 1.x priorities

The 1.x line should remain backward compatible. Priorities are driven by real user feedback rather than feature count.

### Release and adoption

- publish the Collection to Ansible Galaxy;
- validate installation from Galaxy on a clean Linux host;
- improve release automation and release verification;
- collect first-user installation and production feedback;
- fix documentation gaps discovered by new users.

### Restore confidence

Candidate work:

- a documented restore-test workflow using a temporary directory;
- optional comparison of restored files against a manifest;
- examples for database dumps, container volumes, and application directories;
- scheduled verification and reporting examples.

A restore-test feature must not claim application consistency when the source was archived without an application-aware dump, snapshot, lock, or quiesce step.

### Manifest authenticity

Candidate work:

- detached signing of manifest files;
- verification through established system tools such as GPG or another standard backend;
- clear key-management boundaries;
- no private-key storage inside YaCompress.

Checksums and signatures must remain separate concepts.

### Retention policies

Potential extensions:

- daily, weekly, monthly, and yearly retention groups;
- deterministic selection and Check Mode preview;
- explicit timezone and timestamp rules;
- no hidden deletion or implicit policy inference.

This work should extend `archive_rotate` only when the resulting interface remains understandable. A new policy module is preferable to overloading rotation with unrelated orchestration.

### Operational reporting

Possible additions:

- machine-readable summaries for archive, verification, manifest, and rotation results;
- example reporting to common Ansible callback or monitoring workflows;
- inventory of retained archives without modifying them.

Reporting should consume existing structured module results before new abstractions are introduced.

### Compatibility and performance

Ongoing work:

- additional real-host acceptance results;
- representative NFS and enterprise storage validation;
- benchmark datasets closer to real workloads;
- documented compressor-version differences;
- review of the `tar.gz` compression default only through an explicit compatibility proposal.

## Possible 2.0 directions

Version 2.0 is reserved for changes that cannot be delivered safely within the 1.x compatibility contract.

Possible topics include:

- redesigned defaults based on accumulated user evidence;
- a stable backup-policy interface coordinating existing lifecycle modules;
- signed manifest formats with an explicit versioning strategy;
- a restore-test module with clearly defined isolation and cleanup guarantees;
- formal support tiers for operating systems and filesystems;
- deprecation and migration of interfaces that proved confusing in real use.

None of these items is approved merely by appearing here. Each requires design review, migration planning, tests, and documented consequences.

## Explicit non-goals

YaCompress is not planned to become:

- a proprietary archive or repository format;
- a deduplicating or incremental snapshot engine;
- an encryption or key-management system;
- a remote object-storage client;
- a centralized backup catalogue or scheduler;
- a tape-management system;
- an immutable or ransomware-resistant storage platform;
- an extraction sandbox for hostile archives;
- a replacement for Borg, Restic, Kopia, or enterprise backup products;
- a universal cross-platform archive implementation independent of native Linux tools.

Standard archives must remain recoverable without YaCompress.

## Decision criteria

A roadmap proposal should normally satisfy all of the following:

1. It solves a demonstrated user or operator problem.
2. It improves recoverability, integrity, safety, transparency, or supported compatibility.
3. Existing modules and structured results cannot solve the problem cleanly.
4. The smallest complete design is understandable to an Ansible user.
5. It does not introduce a proprietary data format without an exceptional, documented reason.
6. Destructive behavior is explicit, previewable, and honestly reported.
7. Security and compatibility boundaries are documented.
8. Regression, integration, and relevant real-host tests are practical.
9. New dependencies are justified against the Python standard library, Ansible utilities, and existing native tools.
10. The maintenance cost is proportionate to the benefit.

## Compatibility policy

For the 1.x series:

- patch releases should contain compatible fixes and documentation improvements;
- minor releases may add compatible options, return fields, modules, and formats;
- defaults and destructive semantics should not change silently;
- deprecations require an announced migration path;
- unsupported security or performance claims are not accepted.

A breaking change belongs in a major release unless it corrects an immediate security vulnerability and no compatible mitigation is possible.

## How priorities are chosen

Priority is based on:

- severity of real failures;
- recoverability impact;
- number of affected users;
- security and data-loss risk;
- availability of a safe workaround;
- implementation and long-term maintenance cost;
- quality of reproducible evidence.

GitHub issues and pull requests are the source of truth for active work. This document records direction and boundaries rather than a fixed schedule.
