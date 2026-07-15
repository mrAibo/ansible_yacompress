# Security policy

## Supported versions

Security fixes are prepared for the latest released YaCompress version and the current `main` branch. Older versions may receive fixes when the change can be backported safely, but users should normally upgrade to the latest release.

| Version | Security support |
|---|---|
| Latest release | Supported |
| Current `main` | Supported for development and pre-release testing |
| Older releases | Best effort |

## Reporting a vulnerability

Do not open a public issue for a suspected vulnerability.

Use GitHub Private Vulnerability Reporting for this repository:

1. Open the repository **Security** tab.
2. Select **Report a vulnerability**.
3. Include the affected module and version, required privileges, reproduction steps, impact, and any proposed mitigation.

Reports should contain enough information to reproduce the problem without using production secrets or personal data. A maintainer will acknowledge the report through the private advisory and coordinate investigation, remediation, release, and disclosure there.

Use public GitHub issues for ordinary bugs, compatibility problems, feature requests, documentation errors, and performance regressions that do not expose data, cross a privilege boundary, or permit unintended destructive actions.

## Security scope

YaCompress is an Ansible Collection that invokes native archive tools on managed Linux hosts. It does not provide a sandbox, encryption layer, remote repository, authentication service, or application-consistent snapshot mechanism.

The Collection aims to:

- avoid shell-string command construction;
- validate module arguments before invoking native tools;
- keep temporary archive files beside the final destination;
- replace completed destinations atomically where the filesystem supports it;
- avoid following symbolic links during rotation and manifest enumeration;
- reject unsafe manifest paths;
- expose destructive operations explicitly;
- preserve Check Mode as a non-mutating preview;
- verify archives before optional source deletion.

These controls reduce risk, but they do not make untrusted archives or untrusted playbook input safe in every environment.

## Trust boundaries

### Ansible controller

The controller, playbooks, inventory, variables, vault data, Collection package, and configured credentials are trusted. Anyone who can change these inputs can direct Ansible to read, create, extract, or remove files with the privileges granted to the remote user.

### Managed host

The operating system, Python runtime, filesystem, and native utilities such as `tar`, `gzip`, `pigz`, `zstd`, `xz`, `zip`, and `unzip` are part of the trusted computing base. Their package provenance and security updates remain the operator's responsibility.

### Source and destination data

Source trees may contain hostile filenames, symbolic links, device nodes, sockets, sparse files, or files that change during processing. Destination directories may be writable by other users. Operators should restrict permissions and avoid sharing working directories with untrusted processes.

### Archives from untrusted sources

Treat externally supplied archives as hostile. Structural verification confirms that a backend can read an archive; it does not prove that extraction is safe. Extract untrusted archives only in an isolated directory with minimal privileges and inspect their member names and types first.

## Privileges and least privilege

Modules run with the privileges of the Ansible remote user, including privileges obtained through `become`. YaCompress does not need root by design.

Use the least privilege required to read the source and write the destination. Avoid running backup tasks as root when a dedicated service account is sufficient. Separate backup ownership from application ownership where practical.

A module cannot protect files from a playbook operator who deliberately supplies destructive paths while running with sufficient privileges.

## Native command execution

YaCompress passes argument lists to `AnsibleModule.run_command`; it does not build commands through a shell. This prevents normal filename content from becoming shell syntax.

Native tools still interpret their own options, archive member names, patterns, environment, configuration files, and platform-specific behavior. Keep packages current and test the exact distributions and versions used in production.

## Paths, patterns, and traversal

Module path arguments should resolve to the intended source, destination, manifest, or retention directory. The Collection validates important path relationships and rejects unsafe paths stored in manifests.

`include` and `exclude` values are archive selection patterns, not shell expressions. They should remain relative to the selected source. Absolute and parent-traversal patterns are not meaningful safe input and are being tightened consistently across the interface.

Do not generate path arguments directly from untrusted network input without validation in the calling role or playbook.

## Symbolic links

Symbolic-link behavior differs by operation and backend:

- rotation skips symbolic links and avoids traversing symbolic-link directories;
- manifest enumeration does not follow symbolic links;
- archive creation follows the semantics of the selected native archive tool and module options;
- extraction may create links described by a trusted archive.

A safe destination directory must not be writable by an attacker who can replace path components during execution.

## Temporary files and atomic replacement

TAR-family archive creation uses a temporary path in the destination directory and replaces the final destination only after successful creation and optional verification. Keeping both paths on the same filesystem avoids cross-filesystem rename failures and supports atomic replacement where the filesystem implements it.

Consequences:

- enough free space is required for the temporary and existing archive at the same time;
- filesystem quotas and file-size limits still apply;
- network and clustered filesystems may have different visibility and cache semantics;
- atomic rename does not prevent another privileged process from changing source data while it is read.

Interrupted processes may leave temporary files. Operational monitoring should detect and remove stale `.multi_archive-*` paths after confirming that no job is active.

## Time-of-check/time-of-use limitations

A file can change between enumeration, hashing, archiving, verification, and deletion. YaCompress provides consistency for the bytes read by the selected tools; it does not freeze an active application.

For databases, virtual machines, mail stores, and other mutable workloads, use an application-native backup, quiescing procedure, filesystem snapshot, or storage snapshot before archiving.

When `delete_source` is enabled, source deletion occurs only after successful archive creation and requested verification. This reduces accidental loss but does not create transaction-level consistency with the application.

## Archive verification

`archive_verify` and `verify_archive` perform structural checks using the corresponding native backend. A successful result means the backend could read the archive structure at that time.

It does not guarantee:

- that the original source was complete or application-consistent;
- that every extracted file is semantically correct;
- that an archive is free of malicious members;
- that future storage corruption will not occur;
- that the archive was created by a trusted party.

Periodically combine structural verification with manifest verification and an actual restore test.

## SHA-256 manifests

`archive_manifest` records SHA-256 values, sizes, and relative paths. It detects accidental changes, missing files, and unexpected files covered by the stored selection policy.

A checksum manifest is not a digital signature. An attacker who can modify both the archive and its manifest can replace both consistently. Protect manifests with separate permissions, immutable storage, an independent system, or a future signing mechanism.

Do not treat SHA-256 manifests as encryption or proof of origin.

## Rotation and deletion

`archive_rotate` is deliberately separate from archive creation and verification because it deletes files. Use Check Mode before deploying or changing retention policies.

Recommended controls:

- dedicate one directory to one retention policy;
- use narrow filename patterns;
- retain at least one newest archive through `min_keep`;
- protect the directory from untrusted writers;
- review `planned_removals` in Check Mode;
- keep an independent copy when recovery requirements demand it.

Rotation cannot recover a file after the filesystem has deleted it.

## Extraction safety

Only extract archives from trusted sources into a controlled destination. Before extracting an external archive:

- verify its provenance and checksum;
- list members without extraction;
- reject absolute paths and parent traversal;
- inspect symbolic links, hard links, device nodes, and unusual ownership metadata;
- use a dedicated unprivileged account and empty destination;
- avoid extracting directly over a live application tree.

YaCompress is not an archive sandbox.

## Confidentiality and encryption

YaCompress produces standard archives and does not encrypt them. Compression does not provide confidentiality.

Protect backup data through filesystem permissions, encrypted filesystems, encrypted transport, encrypted storage, or a repository-based backup product when encryption and key management are required.

Archive filenames, manifests, logs, and Ansible output may reveal paths, sizes, timings, or error messages. Do not log secrets and use `no_log` in the calling task when variables contain sensitive information.

## Denial of service and resource use

Compression, hashing, verification, and extraction consume CPU, memory, storage bandwidth, temporary space, and inodes. Highly compressible or malicious archives may expand dramatically.

Control risk through:

- explicit compression levels;
- bounded `threads` values on shared hosts;
- filesystem quotas and free-space monitoring;
- isolated restore directories;
- Ansible timeouts and scheduling;
- testing with representative data.

`threads: auto` follows host capacity, not workload priority. A fixed worker count may be safer on shared production systems.

## NFS and clustered filesystems

Atomic rename, close-to-open consistency, UID mapping, root squashing, caching, locking, and quota behavior depend on the server and mount options. CI cannot prove compatibility with an organization's exact storage environment.

Run `tests/run_host_storage_validation.sh` against the real mounted destination and validate restore behavior on the intended recovery host.

## SELinux, AppArmor, and FIPS

Mandatory access-control and cryptographic-policy behavior is determined by the host policy and installed native tools.

YaCompress does not disable or bypass SELinux, AppArmor, or FIPS settings. Validate on the exact target host. The Collection does not promise preservation of arbitrary SELinux labels; manage labels with dedicated Ansible modules where required.

## Dependency and supply-chain security

YaCompress intentionally avoids third-party Python runtime dependencies, but it depends on:

- `ansible-core` on the controller/managed host execution path;
- the downloaded Collection artifact;
- the operating system and native archive packages;
- GitHub Actions used for CI and release automation.

Verify release checksums, install from trusted sources, pin automation where organizational policy requires it, and review dependency/security advisories from Ansible and the operating-system vendor.

## Security release process

For a confirmed vulnerability, maintainers will use a private GitHub Security Advisory to:

1. reproduce and assess impact;
2. prepare the smallest safe fix and regression test;
3. review affected versions and backport feasibility;
4. coordinate a patched release;
5. publish the advisory after users can upgrade.

Public disclosure timing depends on severity, exploitability, fix readiness, and coordination needs. No fixed response or release deadline is promised for this volunteer-maintained project.

## Known non-goals

YaCompress does not provide:

- encryption or key management;
- authentication or authorization;
- remote repository access;
- deduplication or incremental snapshots;
- ransomware-resistant immutability;
- application-consistent snapshots;
- malware scanning;
- sandboxed extraction;
- digital signatures for manifests;
- guaranteed secure erasure from SSDs, snapshots, copy-on-write filesystems, or remote storage.

Use dedicated systems when these properties are required.
