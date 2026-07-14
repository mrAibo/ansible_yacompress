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
ansible-galaxy collection install build/mraibo-yacompress-1.4.0.tar.gz -p collections
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

## Interpreting results

A faster compressor is not automatically the best choice:

- `tar.zst` is generally the first candidate for frequent Linux backups because it balances speed, parallelism, and extraction performance.
- `tar.gz` with pigz is useful when gzip compatibility is required.
- `tar.xz` targets compact long-term archives where creation speed matters less.
- plain `tar` is appropriate when the source is already compressed.
- ZIP is mainly a compatibility format and is not part of the comparative benchmark matrix.

Treat these as selection guidelines. Use measured results from the actual target hardware for operational decisions.
