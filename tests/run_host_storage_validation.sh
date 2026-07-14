#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 DESTINATION_DIRECTORY" >&2
    echo "Point DESTINATION_DIRECTORY at the exact local, NFS, clustered, or enterprise filesystem to validate." >&2
    exit 2
fi

dest_root=$1
require_fips=${REQUIRE_FIPS:-0}
require_selinux=${REQUIRE_SELINUX_ENFORCING:-0}
require_fs_type=${REQUIRE_FS_TYPE:-}

mkdir -p "$dest_root"

fs_type=unknown
if command -v findmnt >/dev/null 2>&1; then
    fs_type=$(findmnt -n -o FSTYPE -T "$dest_root" 2>/dev/null || echo unknown)
fi

selinux=unavailable
if command -v getenforce >/dev/null 2>&1; then
    selinux=$(getenforce)
fi

fips=unknown
if [ -r /proc/sys/crypto/fips_enabled ]; then
    fips=$(cat /proc/sys/crypto/fips_enabled)
fi

printf '%s\n' "Destination: $dest_root" "Filesystem: $fs_type" "SELinux: $selinux" "Kernel FIPS flag: $fips"

if [ -n "$require_fs_type" ] && [ "$fs_type" != "$require_fs_type" ]; then
    echo "Expected filesystem type $require_fs_type, found $fs_type" >&2
    exit 1
fi
if [ "$require_fips" = 1 ] && [ "$fips" != 1 ]; then
    echo "FIPS mode was required but /proc/sys/crypto/fips_enabled is not 1" >&2
    exit 1
fi
if [ "$require_selinux" = 1 ] && [ "$selinux" != Enforcing ]; then
    echo "SELinux enforcing mode was required but detected: $selinux" >&2
    exit 1
fi

venv=${YACOMPRESS_VALIDATION_VENV:-/tmp/yacompress-host-validation-venv}
build_dir=${YACOMPRESS_VALIDATION_BUILD:-/tmp/yacompress-host-validation-build}
collections_dir=${YACOMPRESS_VALIDATION_COLLECTIONS:-/tmp/yacompress-host-validation-collections}

rm -rf "$venv" "$build_dir" "$collections_dir"
python3 -m venv "$venv"
"$venv/bin/pip" install --disable-pip-version-check 'ansible-core>=2.15'
mkdir -p "$build_dir" "$collections_dir"
"$venv/bin/ansible-galaxy" collection build --output-path "$build_dir"
archive=$(find "$build_dir" -maxdepth 1 -name 'mraibo-yacompress-*.tar.gz' -print -quit)
[ -n "$archive" ]
"$venv/bin/ansible-galaxy" collection install "$archive" -p "$collections_dir"

ANSIBLE_COLLECTIONS_PATH="$collections_dir" \
ANSIBLE_NOCOLOR=1 \
"$venv/bin/ansible-playbook" -i localhost, -c local tests/storage_smoke.yml \
    -e "dest_root=$dest_root"

printf '%s\n' "Host storage validation passed." "Filesystem: $fs_type" "SELinux: $selinux" "Kernel FIPS flag: $fips"
