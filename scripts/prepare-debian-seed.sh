#!/bin/bash
set -euo pipefail
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "${LAB_DIR:-$project_dir}/state/debian"
keyfile=${1:?Supply a public SSH key file as the first argument}
key=$(cat "$keyfile")
case "$key" in
    ssh-ed25519\ *|ssh-rsa\ *|ecdsa-sha2-*\ *) ;;
    *) printf '%s\n' 'Unsupported public key format' >&2; exit 1 ;;
esac
test ! -e seed.iso
test ! -e user-data
test ! -e meta-data
umask 077
python3 - "$key" <<'PY'
import json
import sys
from pathlib import Path
config = {
    "hostname": "virtual-host",
    "manage_etc_hosts": True,
    "users": [{
        "name": "moebius",
        "groups": ["sudo"],
        "shell": "/bin/bash",
        "lock_passwd": True,
        "sudo": ["ALL=(ALL) NOPASSWD:ALL"],
        "ssh_authorized_keys": [sys.argv[1]],
    }],
    "disable_root": True,
    "ssh_pwauth": False,
}
Path("user-data").write_text("#cloud-config\n" + json.dumps(config, indent=2) + "\n")
Path("meta-data").write_text("instance-id: moebius-virtual-host-01\nlocal-hostname: virtual-host\n")
PY
xorriso -as mkisofs -quiet -output seed.iso -volid cidata -joliet -rock user-data meta-data
printf '%s\n' 'Seed created with SSH-key-only login; guest moebius has passwordless sudo.'
