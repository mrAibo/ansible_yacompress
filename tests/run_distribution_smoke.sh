#!/bin/sh
set -eu

install_packages() {
    if command -v apt-get >/dev/null 2>&1; then
        export DEBIAN_FRONTEND=noninteractive
        apt-get update
        apt-get install -y python3 python3-venv python3-pip tar gzip pigz bzip2 xz-utils zstd zip unzip
    elif command -v dnf >/dev/null 2>&1; then
        dnf install -y python3 python3-pip tar gzip pigz bzip2 xz zstd zip unzip
    elif command -v pacman >/dev/null 2>&1; then
        pacman -Syu --noconfirm python python-pip tar gzip pigz bzip2 xz zstd zip unzip
    else
        echo "Unsupported package manager" >&2
        exit 1
    fi
}

install_packages
python3 -m venv /tmp/yacompress-venv
. /tmp/yacompress-venv/bin/activate
python -m pip install --disable-pip-version-check --upgrade pip
python -m pip install --disable-pip-version-check ansible-core

rm -rf /tmp/yacompress-build /tmp/yacompress-collections
mkdir -p /tmp/yacompress-build /tmp/yacompress-collections
ansible-galaxy collection build --output-path /tmp/yacompress-build
archive=$(find /tmp/yacompress-build -maxdepth 1 -name 'mraibo-yacompress-*.tar.gz' -print -quit)
[ -n "$archive" ]
ansible-galaxy collection install "$archive" -p /tmp/yacompress-collections

ANSIBLE_COLLECTIONS_PATH=/tmp/yacompress-collections \
ANSIBLE_NOCOLOR=1 \
ansible-playbook -i localhost, -c local tests/distribution_smoke.yml
