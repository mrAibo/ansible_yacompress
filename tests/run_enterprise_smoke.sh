#!/bin/sh
set -eu

ANSIBLE_CORE_SPEC=${ANSIBLE_CORE_SPEC:-ansible-core>=2.15,<2.16}
PYTHON_BIN=${PYTHON_BIN:-python3}

install_apt() {
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y python3 python3-venv python3-pip tar gzip bzip2 xz-utils zstd zip unzip
}

install_dnf() {
    major=$(rpm -E '%{rhel}' 2>/dev/null || true)
    if [ "$major" = "8" ]; then
        dnf install -y python39 python39-pip tar gzip bzip2 xz zstd zip unzip
        PYTHON_BIN=python3.9
    else
        dnf install -y python3 python3-pip tar gzip bzip2 xz zstd zip unzip
        PYTHON_BIN=python3
    fi
}

if command -v apt-get >/dev/null 2>&1; then
    install_apt
elif command -v dnf >/dev/null 2>&1; then
    install_dnf
else
    echo "Unsupported enterprise package manager" >&2
    exit 1
fi

"$PYTHON_BIN" -m venv /tmp/yacompress-enterprise-venv
. /tmp/yacompress-enterprise-venv/bin/activate
python -m pip install --disable-pip-version-check --upgrade 'pip<25'
python -m pip install --disable-pip-version-check "$ANSIBLE_CORE_SPEC"

python --version
ansible --version

rm -rf /tmp/yacompress-build /tmp/yacompress-collections
mkdir -p /tmp/yacompress-build /tmp/yacompress-collections
ansible-galaxy collection build --output-path /tmp/yacompress-build
archive=$(find /tmp/yacompress-build -maxdepth 1 -name 'mraibo-yacompress-*.tar.gz' -print -quit)
[ -n "$archive" ]
ansible-galaxy collection install "$archive" -p /tmp/yacompress-collections

ANSIBLE_COLLECTIONS_PATH=/tmp/yacompress-collections \
ANSIBLE_NOCOLOR=1 \
ansible-playbook -i localhost, -c local tests/enterprise_smoke.yml
