# Releasing YaCompress

Releases are built from the collection metadata and published as immutable versioned artifacts. Do not create a tag until the release pull request is merged and every required workflow on `main` is green.

## Required repository configuration

For GitHub Releases, no additional secret is required. The workflow uses the repository-scoped `GITHUB_TOKEN` with `contents: write`.

For Ansible Galaxy publication:

1. Create a GitHub environment named `galaxy`.
2. Add the environment secret `ANSIBLE_GALAXY_TOKEN`.
3. Optionally require a reviewer for that environment.
4. Never store the token in the repository, workflow YAML, shell history, or release artifact.

The Galaxy publication job is manual. Pushing a tag creates the GitHub Release but does not automatically publish to Galaxy.

## Prepare a release

1. Update `galaxy.yml` to the new semantic version.
2. Add the matching section to `CHANGELOG.md`.
3. Update versioned installation examples when needed.
4. Run the complete CI and compatibility matrix.
5. Validate the metadata locally:

```bash
python3 tests/test_release.py
python3 scripts/release.py v1.6.0 --notes-output /tmp/release-notes.md
```

The validator rejects:

- malformed tags;
- a tag that differs from `galaxy.yml`;
- a missing or empty changelog section.

## Local release build

```bash
rm -rf build collections
mkdir -p build collections
ansible-galaxy collection build --output-path build
sha256sum build/mraibo-yacompress-1.6.0.tar.gz
ansible-galaxy collection install \
  build/mraibo-yacompress-1.6.0.tar.gz \
  -p collections

ANSIBLE_COLLECTIONS_PATH="$PWD/collections" \
ansible-doc mraibo.yacompress.multi_archive

ANSIBLE_COLLECTIONS_PATH="$PWD/collections" \
ansible-playbook -i localhost, -c local tests/collection_smoke.yml

ANSIBLE_COLLECTIONS_PATH="$PWD/collections" \
ansible-playbook --syntax-check -i localhost, examples/complete_backup.yml
```

## Create the tag and GitHub Release

Create an annotated tag from the tested `main` commit:

```bash
git switch main
git pull --ff-only
git tag -a v1.6.0 -m "mraibo.yacompress 1.6.0"
git push origin v1.6.0
```

The `Release` workflow then:

1. checks that `v1.6.0`, `galaxy.yml`, and `CHANGELOG.md` agree;
2. builds the collection;
3. installs and smoke-tests the exact built archive;
4. produces `SHA256SUMS`;
5. creates a GitHub Release using the matching changelog section;
6. attaches the collection archive and checksum file.

The workflow uses `--verify-tag`; it will not silently create a missing tag.

## Publish to Ansible Galaxy

After reviewing the GitHub Release and downloaded checksum:

1. Open **Actions → Release → Run workflow**.
2. Select the tag, such as `v1.6.0`.
3. Leave `create_release` disabled when the release already exists.
4. Enable `publish_galaxy`.
5. Approve the `galaxy` environment deployment when protection rules require it.

Galaxy versions are immutable. If publication succeeds with incorrect content, increment the version and publish a corrective release; do not attempt to replace the existing Galaxy artifact.

## Verify the public release

From a clean environment:

```bash
ansible-galaxy collection install mraibo.yacompress:1.6.0
ansible-doc mraibo.yacompress.multi_archive
ansible-doc mraibo.yacompress.archive_verify
ansible-doc mraibo.yacompress.archive_rotate
ansible-doc mraibo.yacompress.archive_manifest
```

Run at least one archive round-trip on a disposable path. For enterprise storage, use `tests/run_host_storage_validation.sh` on the exact target filesystem and security mode.

## Failure handling

- **Metadata validation fails:** correct the tag, `galaxy.yml`, or changelog; do not bypass the validator.
- **GitHub Release fails after build:** rerun the workflow. Existing release assets are uploaded with `--clobber`.
- **Galaxy secret is missing:** configure `ANSIBLE_GALAXY_TOKEN` in the `galaxy` environment and rerun only the manual publication.
- **Galaxy reports that the version exists:** verify the existing public artifact and prepare a new version if correction is required.
