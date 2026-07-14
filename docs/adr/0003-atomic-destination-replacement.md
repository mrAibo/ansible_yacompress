# ADR 0003: Replace destination files atomically

- Status: Accepted
- Date: 2026-07-15

## Context

Archive creation and manifest generation can fail after the destination file has been opened. Writing directly to the production path risks leaving a truncated or partially updated file under the expected backup name.

A temporary file in a global temporary directory is also insufficient because the final rename may cross filesystem boundaries and fail with `EXDEV`.

## Decision

YaCompress will create replacement files in a temporary path beside the final destination, validate the completed result when applicable, and then replace the destination with an atomic same-filesystem rename.

The sequence is:

```text
create temporary path beside destination
        ↓
write complete archive or manifest
        ↓
perform requested validation
        ↓
atomically replace destination
        ↓
clean temporary state
```

The previous destination remains available until the replacement is ready.

## Consequences

### Positive

- A failed compressor does not leave a partial archive at the production path.
- Readers see either the previous complete file or the new complete file.
- Same-filesystem rename avoids normal cross-device replacement failures.
- Retry and cleanup behavior is easier to reason about.
- Archive verification can occur before the final path changes.

### Negative

- The destination filesystem must temporarily hold the new file while the previous file may still exist.
- Quotas and free-space checks remain operational responsibilities.
- Atomic rename does not make the underlying application data consistent while it is being archived.
- Network and clustered filesystems may have additional visibility, caching, or durability semantics that require host validation.

## Rejected alternatives

### Write directly to the destination

Rejected because command failure, interruption, or disk exhaustion could corrupt the file users expect to be the latest valid backup.

### Create the temporary file in `/tmp`

Rejected because `/tmp` is commonly a different filesystem from the destination, making atomic rename impossible.

### Delete the old destination before creation

Rejected because it creates a window with no valid destination and increases data-loss risk.

### Copy the completed temporary file into place

Rejected as the default because copying exposes partial destination content during the copy and requires another full data transfer.

## Reconsider when

Additional durability controls may be added if real environments require explicit `fsync` guarantees or filesystem-specific commit behavior. Such changes must preserve the same visible contract: an incomplete replacement must never be presented as the final archive or manifest.
