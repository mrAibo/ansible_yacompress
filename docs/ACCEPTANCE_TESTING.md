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

The host-validation script now sets `ANSIBLE_COLLECTIONS_PATH` explicitly for both Collection installation and playbook execution. CI also runs the validator with an intentionally inherited external Collection path so the regression remains covered.

## Complete benchmark table

The reference run used 512 MiB datasets, 10,000 small files, and three measured iterations.

| Dataset | Variant | Mean seconds | Mean MiB/s | Compression ratio | Archive MiB |
|---|---|---:|---:|---:|---:|
| large-compressible | community-gzip | 2.374 | 215.9 | 0.0024 | 1.24 |
| large-compressible | yacompress-pigz | 1.033 | 495.4 | 0.0060 | 3.08 |
| large-compressible | yacompress-xz | 2.344 | 218.4 | 0.0002 | 0.08 |
| large-compressible | yacompress-zstd | 1.053 | 486.4 | 0.0001 | 0.05 |
| many-small-files | community-gzip | 7.479 | 0.2 | 0.1668 | 0.23 |
| many-small-files | yacompress-pigz | 0.821 | 1.7 | 0.0989 | 0.14 |
| many-small-files | yacompress-xz | 0.866 | 1.6 | 0.0198 | 0.03 |
| many-small-files | yacompress-zstd | 0.818 | 1.7 | 0.0451 | 0.06 |
| mixed-data | community-gzip | 2.446 | 209.9 | 0.0024 | 1.25 |
| mixed-data | yacompress-pigz | 1.040 | 493.4 | 0.0060 | 3.09 |
| mixed-data | yacompress-xz | 2.350 | 218.4 | 0.0002 | 0.08 |
| mixed-data | yacompress-zstd | 1.033 | 496.9 | 0.0001 | 0.05 |

## Interpretation of this run

On this host:

- YaCompress pigz was about 2.30× faster than community gzip on `large-compressible` and about 2.35× faster on `mixed-data`.
- YaCompress zstd was about 2.25× faster than community gzip on `large-compressible` and about 2.41× faster on `mixed-data`.
- On `many-small-files`, community gzip took 7.479 seconds, while the YaCompress cases completed in 0.818–0.866 seconds. The wall-clock difference was approximately 8.6–9.1×.
- zstd produced the smallest archive in the `large-compressible` and `mixed-data` cases: approximately 0.05 MiB versus 0.08 MiB for xz.
- xz produced the smallest archive in the `many-small-files` case: approximately 0.03 MiB versus 0.06 MiB for zstd.
- xz was not consistently slower than community gzip in this run, but it was about 2.2–2.3× slower than zstd on the two 512 MiB data-heavy cases.
- pigz maximized gzip-compatible throughput but produced larger archives than the other tested compressors on these highly compressible generated datasets.

The generated datasets are deliberately synthetic. Extremely small output archives indicate highly repetitive input and must not be treated as representative of databases, media, encrypted data, or already-compressed production content.

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
