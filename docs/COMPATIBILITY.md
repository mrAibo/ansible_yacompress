# Linux compatibility

YaCompress uses native archive tools on the managed host. Compatibility therefore depends on both Ansible/Python support and the behavior of the installed `tar`, `pigz`, `zstd`, `xz`, `zip`, and related commands.

## Continuously tested distributions

The following images build and install the collection from source and run the same end-to-end smoke scenario on every pull request and push to `main`:

| Distribution | Family | Package manager | Tested operations |
|---|---|---|---|
| Ubuntu 24.04 | Debian | APT | zstd, pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| Debian 12 | Debian | APT | zstd, pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| Fedora 42 | Red Hat | DNF | zstd, pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| Rocky Linux 9 | Enterprise Linux | DNF | zstd, pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| Arch Linux | Arch | pacman | zstd, pigz, xz, ZIP, multiple sources, extraction, verification, check mode |
| openSUSE Leap 15.6 | SUSE | zypper | zstd, pigz, multiple sources, extraction, verification, explicit thread limits |

The normal CI additionally runs the Python regression suite, legacy module tests, collection build/install tests, `ansible-test sanity`, and `ansible-test integration` on Ubuntu 24.04.

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
- old Python or Ansible versions;
- FIPS mode;
- SELinux/AppArmor policy customizations;
- NFS and clustered filesystems;
- cgroup or systemd CPU restrictions;
- multi-gigabyte production data;
- the exact SLES, RHEL, Oracle Linux, AlmaLinux, or Ubuntu LTS minor release used by an organization.

Before production rollout, run `tests/run_distribution_smoke.sh` or an equivalent playbook on the exact target image or host.

## Not currently claimed

The collection does not currently claim support for:

- Alpine Linux or other musl-based systems;
- BSD, macOS, or Windows managed hosts;
- non-GNU archive tools with incompatible command-line behavior;
- formats whose required executable is not installed.

Unsupported platforms may work, but they are not advertised until they receive a reproducible compatibility test.
