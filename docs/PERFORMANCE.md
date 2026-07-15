# Performance guide

YaCompress delegates archive work to native Linux tools. Performance therefore depends on the selected format, compression level, worker count, CPU, storage, filesystem, source layout, cache state, and data entropy.

There is no universal fastest or smallest format. Benchmark the actual host and workload before setting production defaults.

## Practical starting point

For frequent Linux backups, start with:

```yaml
- name: Create a fast balanced backup
  mraibo.yacompress.multi_archive:
    source: /srv/application
    dest: /srv/backups/application.tar.zst
    state: archived
    compression_level: 3
    threads: auto
    verify_archive: true
```

`tar.zst` is usually the first candidate because zstd offers high throughput, parallel compression, fast extraction, and competitive archive size.

Use a fixed worker count instead of `threads: auto` on shared production systems:

```yaml
threads: 4
```

## Format selection

| Requirement | Suggested format | Reason |
|---|---|---|
| Fast recurring Linux backups | `tar.zst` | Strong speed/ratio balance and parallelism |
| Maximum gzip compatibility | `tar.gz` with `compression: pigz` or `auto` | Standard gzip stream with optional parallel creation |
| Compact long-term archive | `tar.xz` | Often useful when archive size matters more than creation time |
| Already-compressed data | plain `tar` | Avoid spending CPU on data that will not compress meaningfully |
| Legacy bzip2 workflow | `tar.bz2` | Compatibility rather than peak performance |
| Cross-platform desktop exchange | ZIP | Broad tooling support, but not the primary Linux backup choice |

## gzip and pigz

A `.tar.gz` destination remains a gzip-compatible archive whether the compressor is gzip or pigz.

The current backward-compatible default is:

```yaml
compression: none
```

For `tar.gz`, this selects ordinary gzip. It does not mean an uncompressed archive.

To prefer parallel gzip and fall back when pigz is unavailable:

```yaml
compression: auto
threads: auto
```

To require pigz explicitly:

```yaml
compression: pigz
threads: 4
```

Choose pigz when gzip compatibility is required and the host has spare CPU cores. On slow storage, additional workers may stop helping once storage becomes the bottleneck.

## zstd

zstd is the recommended first benchmark candidate for recurring backups.

Advantages:

- parallel compression;
- high throughput at moderate levels;
- fast decompression;
- standard `.tar.zst` output;
- strong results for both large files and trees containing many files.

Start near level 3. Increase levels only after measuring whether the smaller archive justifies the additional CPU time.

```yaml
compression_level: 3
threads: auto
```

For shared systems, cap workers:

```yaml
compression_level: 3
threads: 2
```

## xz

xz is appropriate when compact output is more important than backup-window duration.

It can consume substantially more CPU time and memory than zstd. A higher level is not automatically better operationally if it delays backups, increases contention, or reduces the time available for verification and replication.

Use xz for measured archival cases, not as an automatic default.

## Plain TAR

Use plain TAR when sources are already compressed or encrypted, for example:

- JPEG, PNG, MP4, and many media formats;
- existing ZIP, gzip, zstd, or xz files;
- encrypted database exports;
- VM images that are internally compressed;
- application bundles that already contain compressed assets.

Compression may add CPU cost while producing little or no space saving.

## Many small files

Workloads containing many small files are often dominated by:

- filesystem metadata access;
- directory traversal;
- process and Ansible overhead;
- inode and cache behavior;
- archive header creation.

Compression throughput in MiB/s can look low because the dataset itself is small. Wall-clock time and file count are more meaningful than throughput alone.

The CachyOS reference run showed approximately 0.8 seconds for the tested YaCompress cases versus 7.5 seconds for the compared `community.general.archive` gzip case on 10,000 generated small files. This is a host-specific observation, not a universal guarantee.

## Large files

For large sequential files, CPU and storage throughput dominate.

Measure:

- source read speed;
- destination write speed;
- one-core compressor speed;
- scaling as workers increase;
- temporary-space requirements;
- verification time.

If performance stops improving after increasing workers, storage bandwidth or memory pressure is probably limiting the job.

## Sparse files

Use sparse support for VM disks, database files, and other files with large holes:

```yaml
sparse: true
```

Without sparse-aware handling, logical holes can become real zero-filled data in an archive or restored file, increasing storage and runtime dramatically.

Always validate sparse preservation on the target filesystem and restore host.

## CPU versus I/O bottlenecks

A job is usually CPU-bound when:

- one or more compressor processes keep CPU cores saturated;
- storage throughput remains below device capability;
- adding workers improves elapsed time.

A job is usually I/O-bound when:

- storage stays near its throughput or latency limit;
- CPU usage remains moderate;
- adding workers provides little improvement;
- other workloads experience increased I/O wait.

A job can also be metadata-bound when archiving many small files.

## Worker selection

`threads: auto` uses host capacity. It does not understand workload priority, CPU quotas, cgroups, maintenance windows, or other services.

Use `auto` when the backup host is dedicated or the maximum throughput is desired. Use a fixed value when:

- applications share the host;
- Ansible runs multiple archive jobs concurrently;
- the host is CPU-constrained;
- predictable resource usage is more important than minimum elapsed time;
- containers or cgroups limit usable CPUs.

Avoid multiplying full-core worker counts across many hosts or tasks running at the same time.

## Compression levels

Higher levels normally trade more CPU time and sometimes more memory for a smaller archive. The gain often diminishes at higher levels.

Recommended process:

1. benchmark a moderate level;
2. record elapsed time and archive size;
3. test one lower and one higher level;
4. include verification and restore time in the decision;
5. choose the lowest operational cost that meets storage requirements.

Do not compare two tools at different levels without documenting those levels.

## Storage considerations

### SSD and NVMe

Fast storage can expose compressor limits. Parallel zstd or pigz may scale well until CPU or memory bandwidth becomes limiting.

### HDD

Seek-heavy small-file workloads can dominate elapsed time. More compressor workers may not help. Consider snapshotting or staging data before archiving when application design permits it.

### NFS and network storage

Network latency, server load, mount options, cache behavior, root squashing, and bandwidth can dominate results. Test the real mount and recovery host.

Atomic destination replacement requires the temporary archive and final destination to be on the same filesystem. Enough space must exist for the old and new archive during replacement.

### Copy-on-write filesystems

Btrfs, ZFS, and snapshot-based storage can change space accounting. Logical size, allocated size, compression, reflinks, quotas, and snapshots should be measured separately.

## Concurrency

Running many archive tasks concurrently can overwhelm:

- CPU cores;
- memory bandwidth;
- page cache;
- storage queues;
- NFS servers;
- temporary-space capacity.

Control concurrency through Ansible strategy, `serial`, host groups, scheduling, and fixed worker limits. Benchmark the complete concurrent production pattern, not only one isolated task.

## Verification cost

`verify_archive: true`, `archive_verify`, and `archive_manifest` add deliberate read and CPU work.

Do not remove verification merely to improve benchmark numbers. A fast archive that cannot be trusted or restored is not a successful backup.

Measure the full operational workflow:

```text
create → structural verify → manifest → replicate → periodic verify → restore test
```

## Interpreting the CachyOS reference run

The published reference used:

- CachyOS, Linux 7.1.3;
- `ansible-core` 2.19.11;
- GNU tar 1.35;
- zstd 1.5.7;
- xz 5.8.3;
- pigz 2.8;
- 512 MiB generated datasets;
- 10,000 generated small files;
- three measured iterations.

On that host, zstd and pigz were roughly 2.3 times faster than the compared community gzip case on the two large generated datasets. The small-file community gzip case took roughly nine times as long as the tested YaCompress cases.

The generated data was intentionally compressible. Archive sizes and ratios must not be generalized to production databases, media, encrypted files, or already-compressed content.

See [`BENCHMARKING.md`](BENCHMARKING.md) for the complete table and reproducible runner.

## Benchmark checklist

Record at minimum:

- exact Collection commit or version;
- CPU model and logical CPU count;
- RAM;
- OS and kernel;
- filesystem and storage type;
- local or network destination;
- Python and Ansible versions;
- native tool versions;
- source size and file count;
- data characteristics;
- compression format, level, and workers;
- cache state;
- elapsed time;
- archive size;
- verification result;
- raw CSV output.

## Operational recommendations

- Start with zstd level 3 for frequent Linux backups.
- Use pigz when gzip compatibility is mandatory.
- Use xz only after confirming that the size saving justifies the longer window.
- Use plain TAR for already-compressed data.
- Cap workers on shared hosts.
- Include verification in performance planning.
- Test real storage, especially NFS and clustered filesystems.
- Measure restore time, not only archive creation.
- Preserve raw benchmark data and avoid universal performance claims.
