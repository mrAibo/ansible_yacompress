# Benchmarking YaCompress

The benchmark suite compares native YaCompress backends with `community.general.archive` under the same Ansible controller process and filesystem.

It is designed to make performance claims reproducible, not to publish one universal winner. Compression results depend on CPU architecture, storage, cache state, file count, data entropy, compressor versions, and the selected levels and thread limits.

## Compared cases

The default matrix includes:

- YaCompress `tar.gz` with `pigz`, level 3, automatic worker selection
- YaCompress `tar.zst` with zstd, level 3, automatic workers
- YaCompress `tar.xz` with xz, level 3, two workers
- `community.general.archive` with gzip

Every produced archive is opened with `tar -tf` before its result is recorded.

The benchmark selects pigz explicitly. The `multi_archive` module keeps `compression: none` as its backward-compatible default for `tar.gz`, which uses gzip. Set `compression: auto` to prefer pigz and fall back to gzip, or set `compression: pigz` to require pigz.

## Datasets

The runner generates three temporary datasets:

1. **large-compressible** — one large repetitive log-like file; useful for measuring compressor throughput.
2. **many-small-files** — files distributed across many directories; useful for measuring metadata and archive-creation overhead.
3. **mixed-data** — a large text file, an already compressed file, and configuration files.

The generated source data and archives are removed after the run. Only CSV and Markdown results are retained.

## Run locally

Install the collections and native tools first:

```bash
ansible-galaxy collection build --output-path build
archive=$(find build -maxdepth 1 -name 'mraibo-yacompress-*.tar.gz' -print -quit)
test -n "$archive"
ansible-galaxy collection install "$archive" -p collections --force
ansible-galaxy collection install community.general -p collections
```

Run a representative benchmark:

```bash
ANSIBLE_COLLECTIONS_PATH="$PWD/collections" \
ANSIBLE_NOCOLOR=1 \
python3 benchmarks/run.py \
  --size-mib 512 \
  --small-files 10000 \
  --iterations 3
```

Results are written to:

```text
benchmark-results/results.csv
benchmark-results/results.md
```

To benchmark only YaCompress backends:

```bash
python3 benchmarks/run.py --skip-community
```

## Run from GitHub Actions

Open **Actions → Archive benchmark → Run workflow** and choose:

- dataset size;
- small-file count;
- iteration count.

The workflow uploads the raw CSV, Markdown summary, and diagnostic log as an artifact.

Pull requests use a deliberately tiny dataset only to validate that the benchmark machinery works. Those smoke-test numbers must not be presented as performance evidence because Ansible startup overhead dominates such small runs.

## Recommended measurement practice

For credible published results:

- use at least 128 MiB; 512 MiB or 1 GiB is preferable;
- use at least three measured iterations;
- record CPU model, logical CPU count, RAM, filesystem, storage type, OS, Ansible version, and compressor versions;
- run on an otherwise idle host;
- use the same source data for every backend;
- report both wall-clock time and archive size;
- keep raw CSV results available;
- distinguish warm-cache and cold-cache tests;
- do not compare different compression levels without saying so.

## CachyOS reference run

A real-host acceptance run used:

- CachyOS with Linux 7.1.3;
- `ansible-core` 2.19.11;
- GNU tar 1.35;
- zstd 1.5.7;
- xz 5.8.3;
- pigz 2.8;
- 512 MiB generated datasets;
- 10,000 files in the small-file dataset;
- three measured iterations.

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

Observed on that host:

- pigz was approximately 2.30× faster than community gzip on `large-compressible` and 2.35× faster on `mixed-data`;
- zstd was approximately 2.25× faster than community gzip on `large-compressible` and 2.41× faster on `mixed-data`;
- the small-file community case took 7.479 seconds, versus 0.818–0.866 seconds for the YaCompress cases, a wall-clock difference of approximately 8.6–9.1×;
- zstd produced the smallest archive for the two data-heavy generated datasets;
- xz produced the smallest archive for the many-small-files dataset;
- xz was approximately 2.2–2.3× slower than zstd on the two 512 MiB data-heavy datasets;
- pigz provided the fastest gzip-compatible result, but its output was larger on these highly compressible generated datasets.

These generated inputs are intentionally synthetic and extremely compressible. The tiny output sizes must not be generalized to databases, media, encrypted data, or already-compressed production content. This table documents one reproducible host run, not a universal guarantee.

The full acceptance record is available in [`ACCEPTANCE_TESTING.md`](ACCEPTANCE_TESTING.md).

## Interpreting results

A faster compressor is not automatically the best choice:

- `tar.zst` is generally the first candidate for frequent Linux backups because it balances speed, parallelism, and extraction performance.
- `tar.gz` with pigz is useful when gzip compatibility is required.
- `tar.xz` targets compact long-term archives where creation speed matters less, but it does not guarantee the smallest output for every dataset.
- plain `tar` is appropriate when the source is already compressed.
- ZIP is mainly a compatibility format and is not part of the comparative benchmark matrix.

Treat these as selection guidelines. Use measured results from the actual target hardware for operational decisions.
