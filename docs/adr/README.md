# Architecture Decision Records

Architecture Decision Records document significant choices that shape YaCompress. They preserve the context, accepted trade-offs, rejected alternatives, and conditions under which a decision should be revisited.

ADRs describe the current architecture; they are not immutable. A future decision that supersedes an existing ADR should add a new record and update the old record's status rather than silently rewriting history.

## Accepted decisions

| ADR | Decision |
|---|---|
| [0001](0001-native-linux-tools.md) | Use native Linux archive tools |
| [0002](0002-standard-archive-formats.md) | Produce standard archive formats |
| [0003](0003-atomic-destination-replacement.md) | Replace destination files atomically |

## Format

Each ADR includes:

- status and date;
- context;
- decision;
- positive and negative consequences;
- rejected alternatives;
- conditions for reconsideration.

New ADRs should be short enough to review independently and should record a real architectural choice, not routine implementation detail.

See [YaCompress Design Philosophy](../DESIGN_PHILOSOPHY.md) for the broader principles connecting these decisions.
