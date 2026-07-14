# Linux compatibility

YaCompress uses native archive tools on the managed host. Compatibility therefore depends on both Ansible/Python support and the behavior of the installed `tar`, `pigz`, `zstd`, `xz`, `zip`, and related commands.

## Continuously tested distributions

The following images build and install the collection from source and run an end-to-end smoke scenario on every pull request and push to `main`:

| Distribution | Family | Package manager | Ansible line | Tested operations |
|---|---|---|---|---|
| Ubuntu 24.04 | Debian | APT | current | zstd, pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| Ubuntu 22.04 | Debian | APT | 2.15 | zstd, automatic gzip/pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| Debian 12 | Debian | APT | current | zstd, pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| Debian 11 | Debian | APT | 2.15 | zstd, automatic gzip/pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| Fedora 42 | Red Hat | DNF | current | zstd, pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| Rocky Linux 9 | Enterprise Linux | DNF | current | zstd, pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| AlmaLinux 8 | Enterprise Linux | DNF | 2.15 | zstd, automatic gzip/pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| AlmaLinux 9 | Enterprise Linux | DNF | 2.15 | zstd, automatic gzip/pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| Oracle Linux 8 | Enterprise Linux | DNF | 2.15 | zstd, automatic gzip/pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| Oracle Linux 9 | Enterprise Linux | DNF | 2.15 | zstd, automatic gzip/pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| Arch Linux | Arch | pacman | current | zstd, pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| openSUSE Leap 15.6 | SUSE | zypper | current | zstd, pigz, multiple sources, extraction, verification, explicit thread limits |

The normal CI additionally runs the Python regression suite, legacy module tests, collection build/install tests, `ansible-test sanity`, and `ansible-test integration` on Ubuntu 24.04.

## Minimum Ansible baseline

`meta/runtime.yml` declares `requires_ansible: ">=2.15.0"`. The enterprise matrix installs the latest available `ansible-core` release in the `2.15` line and executes the complete collection build/install and archive round-trip on each listed legacy distribution.

This proves compatibility with the declared minimum Ansible line for the tested images. It does not imply that every older Python/Ansible combination outside the matrix is supported.

## Native tar portability

Older GNU tar releases do not always auto-detect zstd-compressed archives while listing or extracting them. YaCompress explicitly supplies the matching decompressor for gzip, bzip2, xz, and zstd reads. This behavior is covered by a regression test and by the AlmaLinux 8 and Oracle Linux 8 end-to-end jobs.

## Expected compatibility

Other glibc-based Linux distributions should work when they provide:

- a Python version supported by the installed Ansible release;
- GNU tar or a tar implementation compatible with the selected compressor invocation;
- the native compressor required by the selected format;
- sufficient permissions and free space for a temporary archive beside `dest`.

Expected compatibility is not the same as continuous validation. A distribution should only be listed as tested after its complete build/install and archive round-trip succeeds in CI or on a documented real host.

## Enterprise systems

Container validation catches package naming, command-line compatibility, archive creation, verification, extraction, and result-shape problems. It does not fully reproduce:

- corporate repositories and package pinning;
- FIPS mode;
- SELinux/AppArmor policy customizations;
- NFS and clustered filesystems;
- cgroup or systemd CPU restrictions;
- multi-gigabyte production data;
- the exact SLES, RHEL, Oracle Linux, AlmaLinux, or Ubuntu LTS minor release used by an organization.

Before production rollout, run `tests/run_distribution_smoke.sh`, `tests/run_enterprise_smoke.sh`, or an equivalent playbook on the exact target image or host.

## Not currently claimed

The collection does not currently claim support for:

- Alpine Linux or other musl-based systems;
- BSD, macOS, or Windows managed hosts;
- non-GNU archive tools with incompatible command-line behavior;
- formats whose required executable is not installed.

Unsupported platforms may work, but they are not advertised until they receive a reproducible compatibility test.
