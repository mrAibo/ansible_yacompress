# ADR 0002: Produce standard archive formats

- Status: Accepted
- Date: 2026-07-15

## Context

Backup systems often gain advanced capabilities by introducing a private repository format, chunk store, metadata database, or content-addressed pack files. Those designs can provide deduplication, incremental snapshots, encryption, and efficient remote transfer.

YaCompress addresses a different problem: reliable lifecycle management for conventional archives created and operated through Ansible.

## Decision

YaCompress will produce and consume standard TAR-family and ZIP archives:

- `tar`;
- `tar.gz`;
- `tar.bz2`;
- `tar.xz`;
- `tar.zst`;
- ZIP.

The collection will not require a YaCompress-specific repository, catalog, daemon, database, or restore client.

Manifests are separate deterministic JSON files and do not alter the archive format.

## Consequences

### Positive

- Archives remain readable with common tools when Ansible and YaCompress are unavailable.
- Recovery procedures are simple to inspect, rehearse, and document.
- Existing storage, replication, and transport systems can handle the files.
- There is no collection-specific repository migration or lock-in.
- Individual archives can be moved, copied, or retained independently.

### Negative

- No native cross-archive deduplication.
- No incremental snapshot graph.
- No built-in encrypted repository or key management.
- No content-addressed corruption repair.
- Full archives may consume more storage and transfer bandwidth than repository-based backup systems.

## Rejected alternatives

### Create a proprietary YaCompress repository format

Rejected because it would change the project from archive lifecycle automation into a complete backup storage system and would make recovery depend on project-specific code.

### Embed archives inside a custom container with metadata

Rejected because separate manifests and ordinary filesystem metadata already cover the current requirements without reducing interoperability.

### Reimplement Borg, Restic, or Kopia capabilities

Rejected because those mature tools already solve repository-based backup problems. YaCompress should complement them rather than reproduce them poorly.

## Reconsider when

This decision should be reconsidered only if the project's purpose explicitly changes. Features such as deduplication or encrypted repositories should normally be implemented through integration with an existing backup system, not by changing YaCompress archive formats.
