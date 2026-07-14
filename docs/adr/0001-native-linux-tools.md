# ADR 0001: Use native Linux archive tools

- Status: Accepted
- Date: 2026-07-15

## Context

An Ansible archive module can either implement compression through Python libraries or invoke archive tools installed on the managed Linux host.

A Python implementation can improve portability and reduce host command requirements. Native tools provide established Linux behavior, native multithreading for selected codecs, and direct compatibility with existing administrative workflows.

YaCompress is intended for managed Linux systems where GNU tar and format-specific tools can be installed and validated.

## Decision

YaCompress will use native Linux tools for archive creation, extraction, and structural verification.

The supported backends include:

- GNU tar;
- gzip and pigz;
- bzip2;
- xz;
- zstd;
- zip and unzip.

Python remains responsible for Ansible integration, validation, orchestration, metrics, manifests, and safe filesystem transitions. It does not reimplement compression codecs.

## Consequences

### Positive

- Native pigz, zstd, and xz threading can be used directly.
- Administrators can reproduce archive operations outside Ansible.
- The project avoids new Python compression dependencies.
- Standard Linux tools remain available during disaster recovery.
- Backend versions and behavior can be tested on representative distributions.

### Negative

- Required commands must be installed on the managed host.
- Managed Windows hosts are not supported.
- BSD and non-GNU tar implementations are not part of the current compatibility claim.
- Backend behavior may vary across distribution versions and must be tested.

## Rejected alternatives

### Implement all formats with Python standard-library modules

Rejected because it would not provide the intended native Linux execution model or direct pigz/zstd command integration.

### Add a third-party Python archive framework

Rejected because existing native tools already solve the compression problem and a new dependency would increase packaging and compatibility risk.

### Support both native and Python backends immediately

Rejected as unnecessary complexity. A second backend would duplicate behavior, test matrices, error handling, and documentation before demonstrated user demand.

## Reconsider when

Revisit this decision if a supported Linux environment cannot install the required native tools, or if a portable backend can be added without duplicating the module contract and safety logic.
