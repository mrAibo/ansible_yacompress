# Contributing to YaCompress

Thank you for helping improve YaCompress.

This project prefers small, evidence-based changes over broad rewrites. A contribution should solve a demonstrated problem, preserve the archive lifecycle model, and remain understandable to an administrator reading the code later.

## Before opening a change

1. Search existing issues and pull requests.
2. Confirm that the change is necessary.
3. Read the affected module, its callers, tests, examples, and documentation.
4. Reuse existing helpers and native platform capabilities where possible.
5. Avoid new dependencies unless the problem cannot be solved cleanly without them.

YaCompress follows the Ponytail engineering style described in the upstream project:

- fix the root cause rather than the visible symptom;
- make the smallest complete change;
- prefer standard libraries and native Linux tools;
- avoid unnecessary wrappers, abstractions, frameworks, and boilerplate;
- change as few files as practical;
- keep behavior explicit and testable;
- do not add features only to increase surface area.

Reference: <https://github.com/DietrichGebert/ponytail>

## Project boundaries

A proposed feature should improve at least one of these areas:

- recoverability;
- archive integrity;
- operational safety;
- performance transparency;
- standard-format lifecycle management;
- compatibility with supported Linux environments.

YaCompress is not intended to become:

- a proprietary backup repository;
- an encryption or key-management system;
- a deduplicating snapshot engine;
- an extraction sandbox for hostile archives;
- a replacement for Borg, Restic, Kopia, or enterprise backup software.

Large changes that cross these boundaries should begin as a design discussion or issue.

## Development environment

### Requirements

Use:

- Python 3;
- Ansible Core 2.15 or newer;
- Git;
- native archive tools required by the test scope.

For the complete local test set, install:

- `tar`;
- `gzip`;
- `pigz`;
- `bzip2`;
- `xz`;
- `zstd`;
- `zip`;
- `unzip`.

Package names differ between distributions.

### Clone and create a virtual environment

```bash
git clone https://github.com/mrAibo/ansible_yacompress.git
cd ansible_yacompress

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install "ansible-core>=2.15"
```

Do not commit the virtual environment, build artifacts, installed collections, benchmark output, or temporary archives.

## Repository layout

Important paths include:

```text
plugins/modules/                  Collection modules
tests/                            Python behavior and failure-path tests
tests/integration/targets/        ansible-test integration targets
examples/                         Runnable playbook examples
docs/                             User and operator documentation
docs/adr/                         Accepted architecture decisions
benchmarks/                       Reproducible benchmark framework
.github/workflows/                CI matrices
```

Keep module behavior, tests, and documentation aligned.

## Making a change

Create a focused branch:

```bash
git switch main
git pull --ff-only
git switch -c fix/descriptive-name
```

Prefer one concern per pull request. Examples:

- one validation fix plus its regression tests;
- one documentation improvement;
- one module feature with the smallest required documentation and tests;
- one CI improvement that reproduces a real failure mode.

Avoid combining unrelated cleanup, formatting, refactoring, and feature work.

## Coding rules

### Preserve current interfaces

Do not silently change defaults, return values, accepted formats, path semantics, or destructive behavior.

A compatibility-affecting change requires:

- an explicit rationale;
- tests for old and new behavior;
- migration documentation;
- an appropriate version decision.

### Native command execution

Pass commands as argument lists through Ansible module APIs. Do not introduce shell parsing when direct execution is possible.

Validate user-controlled values before passing them to native tools. In particular, review:

- absolute and relative path handling;
- parent traversal;
- symbolic links;
- source/destination overlap;
- archive-member patterns;
- temporary-file placement;
- destructive operations.

### Destructive operations

Deletion must remain explicit, conservative, and observable.

When adding or modifying deletion behavior:

- support Check Mode where meaningful;
- verify required preconditions first;
- report partial completion honestly;
- return deleted and remaining paths when partial failure is possible;
- never hide a destructive side effect behind a read-only option.

### Error handling

Error messages should identify:

- the failed operation;
- the relevant path, format, or option;
- the native tool error when useful;
- whether any state change already occurred.

Do not claim rollback or transactionality when the filesystem cannot provide it.

### Dependencies

New Python dependencies are strongly discouraged. Prefer:

1. Python standard library;
2. Ansible module utilities;
3. existing native Linux tools already within project scope.

A dependency proposal must explain why these options are insufficient and how packaging, security, and compatibility will be maintained.

## Documentation rules

Update documentation when a change affects:

- user-visible behavior;
- defaults;
- supported values;
- requirements;
- return data;
- security boundaries;
- performance guidance;
- release or migration steps.

Use precise claims. Do not write that YaCompress is always faster, safer, portable, atomic, FIPS-compliant, or enterprise-ready without defining the tested scope.

Benchmark results must include the host, software versions, dataset, settings, iterations, and limitations.

## Testing

Run the narrowest relevant tests while developing, then the full local test set before requesting review.

### Python tests

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
```

Tests may skip when an optional native tool is unavailable. Install the tool when it is required for the changed behavior.

### Build the Collection

```bash
rm -rf build collections
mkdir -p build collections

ansible-galaxy collection build --output-path build
archive=$(find build -maxdepth 1 -name 'mraibo-yacompress-*.tar.gz' -print -quit)
ansible-galaxy collection install "$archive" -p collections --force
```

### Check packaged module documentation

```bash
export ANSIBLE_COLLECTIONS_PATH="$PWD/collections"

ansible-doc mraibo.yacompress.multi_archive >/dev/null
ansible-doc mraibo.yacompress.archive_verify >/dev/null
ansible-doc mraibo.yacompress.archive_manifest >/dev/null
ansible-doc mraibo.yacompress.archive_rotate >/dev/null
```

### Syntax-check the complete example

```bash
ANSIBLE_COLLECTIONS_PATH="$PWD/collections" \
ansible-playbook -i localhost, -c local \
    examples/complete_backup.yml \
    --syntax-check
```

### ansible-test

Run from the installed Collection source location expected by `ansible-test`:

```bash
ansible-test sanity --docker default
ansible-test integration --docker default
```

The repository CI remains the authoritative full matrix. Do not add ignore files or suppressions merely to make sanity pass.

### Real-host storage validation

For changes affecting filesystems, atomic replacement, sparse files, large files, NFS, permissions, SELinux, or FIPS-sensitive environments, run:

```bash
./tests/run_host_storage_validation.sh /tmp/yacompress-validation
```

For a specific filesystem:

```bash
REQUIRE_FS_TYPE=xfs \
./tests/run_host_storage_validation.sh /path/on/xfs/yacompress-validation
```

Use an isolated test path. Do not point validation or rotation tests at production backups.

### Performance changes

Run benchmarks only when behavior could materially affect performance:

```bash
ANSIBLE_COLLECTIONS_PATH="$PWD/collections" \
python3 benchmarks/run.py \
    --size-mib 512 \
    --small-files 10000 \
    --iterations 3
```

Do not optimize from a single synthetic dataset. Preserve raw CSV output and describe the test host.

## Writing tests

A regression test should fail before the fix and pass after it.

Cover the relevant contract:

- successful operation;
- rejected invalid input;
- Check Mode;
- idempotent or repeat behavior where applicable;
- partial failure for destructive operations;
- archive contents or restored data, not only return codes;
- packaged Collection behavior through integration tests.

Prefer small deterministic fixtures. Avoid sleeps unless time ordering is the behavior under test.

## Commit messages

Use concise imperative messages describing the outcome, for example:

```text
fix: isolate host validation collection path
test: reject unsafe exclude traversal
docs: explain pre-Galaxy installation
```

Do not use vague messages such as `update`, `changes`, or `fix stuff`.

## Pull requests

A good pull request contains:

- a clear problem statement;
- the smallest complete solution;
- changed behavior and compatibility impact;
- tests executed;
- documentation impact;
- security and destructive-operation considerations;
- benchmark evidence only when relevant.

Before requesting review, confirm:

- the branch is based on current `main`;
- unrelated changes are absent;
- generated and temporary files are absent;
- tests pass locally where available;
- documentation matches actual behavior;
- CI is green on the exact head commit.

Draft pull requests are encouraged for work that is not ready to merge.

## Security reports

Do not report suspected vulnerabilities in a public issue.

Use GitHub Private Vulnerability Reporting from the repository Security tab. See `SECURITY.md` for the disclosure policy and threat model.

## Reviews and merge policy

Review focuses on correctness, safety, compatibility, clarity, and test evidence.

A pull request may be declined when it:

- expands scope without a demonstrated user need;
- duplicates existing functionality without a clear benefit;
- adds avoidable dependencies;
- weakens validation or destructive-operation safeguards;
- changes defaults without a compatibility plan;
- makes unsupported security or performance claims;
- introduces abstraction larger than the problem it solves.

Accepted pull requests are normally squash-merged after required checks pass.

## Licensing

By submitting a contribution, you agree that it may be distributed under the project license, GPL-3.0-or-later. Do not submit code, documentation, fixtures, or data that you do not have the right to contribute.
