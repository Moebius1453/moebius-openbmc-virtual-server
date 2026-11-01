#!/bin/bash
set -euo pipefail
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "${LAB_DIR:-$project_dir}"
mkdir -p state/debian
cd state/debian
if [ -e base.qcow2 ] || [ -e host.qcow2 ]; then
    printf '%s\n' 'Existing guest disk found; stopping without overwriting.' >&2
    exit 1
fi
url=https://cloud.debian.org/images/cloud/trixie/latest
curl -fL --connect-timeout 10 --max-time 60 "$url/SHA512SUMS" -o SHA512SUMS.download
curl -fL --connect-timeout 10 --speed-time 60 --speed-limit 1024 \
    --retry 2 "$url/debian-13-genericcloud-amd64.qcow2" -o base.download
sum=$(awk '$2 == "debian-13-genericcloud-amd64.qcow2" {print $1}' SHA512SUMS.download)
test "${#sum}" = 128
printf '%s  base.download\n' "$sum" | sha512sum -c -
mv -n base.download base.qcow2
qemu-img create -f qcow2 -F qcow2 -b base.qcow2 host.qcow2 20G
printf '%s\n' 'Debian base and writable overlay prepared. Guest has not been started.'
