# Ansible Galaxy release checklist

Use this checklist for every public YaCompress release. Galaxy versions are immutable, so publish only the exact artifact already reviewed and released on GitHub.

## 1. Repository readiness

- [ ] The release changes are merged into `main`.
- [ ] The working tree is clean and `main` is up to date.
- [ ] No release-blocking issue or pull request remains open.
- [ ] Private Vulnerability Reporting is enabled.
- [ ] All required GitHub Actions checks on the release commit are green.
- [ ] Real-host acceptance results are reviewed for the release when behavior changed.

## 2. Version and release notes

- [ ] `galaxy.yml` contains the intended semantic version.
- [ ] `CHANGELOG.md` contains a matching, complete section.
- [ ] README and documentation installation examples use the intended version or an intentional unpinned command.
- [ ] Breaking changes, deprecations, security fixes, and migration steps are explicit.
- [ ] The release contains no claim that is broader than the available CI, acceptance, or benchmark evidence.

Validate the metadata:

```bash
python3 tests/test_release.py
python3 scripts/release.py v1.6.0 --notes-output /tmp/release-notes.md
```

Review `/tmp/release-notes.md` before tagging.

## 3. Build the exact artifact

```bash
rm -rf build collections
mkdir -p build collections

ansible-galaxy collection build --output-path build
archive="$(find build -maxdepth 1 -name 'mraibo-yacompress-*.tar.gz' -print -quit)"
test -n "$archive"
sha256sum "$archive"

ansible-galaxy collection install "$archive" -p collections --force
```

- [ ] The archive name matches `galaxy.yml`.
- [ ] The archive contains README, license, module documentation, examples, and intended operational documents.
- [ ] The archive does not contain Git metadata, workflow files, test markers, local environments, or benchmark output directories.

## 4. Test the built artifact

```bash
export ANSIBLE_COLLECTIONS_PATH="$PWD/collections"

ansible-doc mraibo.yacompress.multi_archive >/dev/null
ansible-doc mraibo.yacompress.archive_verify >/dev/null
ansible-doc mraibo.yacompress.archive_manifest >/dev/null
ansible-doc mraibo.yacompress.archive_rotate >/dev/null

ansible-playbook -i localhost, -c local tests/collection_smoke.yml
ansible-playbook --syntax-check -i localhost, examples/complete_backup.yml
```

- [ ] All four module documentation pages render.
- [ ] The installed collection smoke test passes.
- [ ] The published end-to-end example passes syntax validation.
- [ ] A disposable archive round trip succeeds on a real Linux host.
- [ ] Check Mode creates no archive or manifest and deletes nothing.

## 5. Tag and GitHub Release

Create the annotated tag from the exact tested `main` commit:

```bash
git switch main
git pull --ff-only
git status --short
git tag -a v1.6.0 -m "mraibo.yacompress 1.6.0"
git push origin v1.6.0
```

- [ ] The tag points to the reviewed release commit.
- [ ] The Release workflow succeeds.
- [ ] The GitHub Release title and notes are correct.
- [ ] The attached collection archive downloads successfully.
- [ ] `SHA256SUMS` matches the downloaded archive.

Do not publish to Galaxy until the GitHub artifact has been downloaded and verified.

## 6. Publish to Ansible Galaxy

Repository prerequisites:

- a GitHub environment named `galaxy`;
- environment secret `ANSIBLE_GALAXY_TOKEN`;
- optional required reviewer protection.

Then:

1. Open **Actions → Release → Run workflow**.
2. Select the exact release tag.
3. Leave `create_release` disabled when the GitHub Release already exists.
4. Enable `publish_galaxy`.
5. Approve the protected `galaxy` environment when required.

- [ ] The workflow publishes the same archive produced from the release tag.
- [ ] No local rebuild or manually modified artifact is uploaded.
- [ ] The Galaxy import finishes successfully.

## 7. Verify from a clean environment

Use a clean virtual environment, container, or disposable Linux host without a source checkout in `ANSIBLE_COLLECTIONS_PATH`:

```bash
python3 -m venv /tmp/yacompress-release-test
source /tmp/yacompress-release-test/bin/activate
python -m pip install --upgrade pip 'ansible-core>=2.15'

ansible-galaxy collection install mraibo.yacompress:1.6.0
ansible-galaxy collection list mraibo.yacompress

ansible-doc mraibo.yacompress.multi_archive >/dev/null
ansible-doc mraibo.yacompress.archive_verify >/dev/null
ansible-doc mraibo.yacompress.archive_manifest >/dev/null
ansible-doc mraibo.yacompress.archive_rotate >/dev/null
```

- [ ] Galaxy installs the expected version.
- [ ] All four modules are discoverable without the repository checkout.
- [ ] A disposable create → verify → manifest → extract workflow succeeds.
- [ ] The Galaxy README and metadata render correctly.
- [ ] Repository, issue tracker, license, tags, and documentation links are correct.

## 8. After publication

- [ ] Announce the release only after clean-install verification.
- [ ] Record the public Galaxy version and GitHub Release in the tracking issue.
- [ ] Monitor Galaxy import logs, GitHub issues, and security reports.
- [ ] Do not replace or overwrite an incorrect Galaxy version.
- [ ] Publish a corrected incremented version when an immutable release needs a fix.

## Failure rules

- Metadata mismatch: correct the repository and create a new tested tag.
- Broken GitHub artifact: do not publish to Galaxy.
- Missing Galaxy token: configure the protected environment; never expose the token in logs or shell history.
- Version already exists in Galaxy: verify the existing artifact and prepare a new version for any correction.
- Clean-install failure: treat it as release-blocking even when source-checkout tests pass.
