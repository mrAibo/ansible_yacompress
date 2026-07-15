# Real-host acceptance testing

Container and CI coverage are necessary but do not replace a run on a real host with its actual kernel, filesystem, native tools, environment variables, and security policy.

## CachyOS acceptance run

YaCompress 1.6.0 completed the full 14-step acceptance plan on CachyOS with:

- Linux 7.1.3
- `ansible-core` 2.19.11
- GNU tar 1.35
- zstd 1.5.7
- xz 5.8.3
- pigz 2.8

The following checks passed:

| Area | Result |
|---|---|
| Collection build and installation | Collection 1.6.0 built and installed; all four `ansible-doc` pages rendered |
| Full lifecycle | Create → structural verify → manifest → extract completed with `failed=0` |
| Restore integrity | Three restored files matched their sources byte-for-byte and by SHA-256 |
| Check Mode | No destination archive was created |
| Corrupted archive | `archive_verify` returned `valid: false`, `changed: false` in soft-failure mode |
| Manifest mismatch | A modified archive produced `valid: false` and non-empty mismatches |
| Rotation | Check Mode preserved six files; the real run retained exactly the three newest files |
| Host storage validation | Completed successfully on tmpfs |
| Sparse file | A logical file larger than 5 GiB remained sparse after round-trip and matched with `cmp` |
| Comparative benchmark | Completed successfully and produced CSV and Markdown output |

## Defect found by the run

The acceptance run exposed an environment-isolation bug in `tests/run_host_storage_validation.sh`.

When the caller already exported `ANSIBLE_COLLECTIONS_PATH`, `ansible-galaxy collection install` could resolve an existing Collection outside the script's private validation directory and skip the intended installation. The subsequent playbook used the private directory and could not find the module.

The host-validation script must therefore set `ANSIBLE_COLLECTIONS_PATH` explicitly for both Collection installation and playbook execution. Validation scripts should not depend on the caller having a clean shell environment.

## Benchmark summary

The reference run used 512 MiB datasets, 10,000 small files, and three iterations. On that specific host:

- YaCompress zstd measured approximately 490 MiB/s;
- `community.general.archive` gzip measured approximately 210 MiB/s at a similar compression ratio;
- the 10,000-small-file community gzip case took about 7.5 seconds, versus about 0.8 seconds for the compared YaCompress case;
- xz produced a better ratio at a substantial throughput cost.

These are host-specific observations, not universal guarantees. Preserve raw CSV, exact commands, system metadata, cache conditions, and compressor versions whenever publishing results.

## Required evidence for future reference runs

Record:

- distribution and kernel;
- CPU model and logical CPU count;
- RAM;
- filesystem and storage type;
- Python and `ansible-core` versions;
- tar, gzip, pigz, zstd, xz, bzip2, zip, and unzip versions;
- exact Collection commit or release;
- raw benchmark CSV and Markdown;
- full host-validation output;
- any inherited `ANSIBLE_*` environment variables.

A new platform should be described as validated only after the lifecycle, corruption, manifest, rotation, storage, sparse-file, and restore-integrity tests pass.
