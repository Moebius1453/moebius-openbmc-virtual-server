#!/bin/bash
set -euo pipefail
flash=$(realpath "${1:?Supply a powered-off adapted flash or pristine firmware}")
base=$(realpath "${2:?Supply an immutable Debian cloud base image}")
seed=$(realpath "${3:?Supply a cloud-init seed ISO}")
destination=${4:?Supply a new independent state directory}
test -f "$flash"
test -f "$base"
test -f "$seed"
test ! -e "$destination"
command -v qemu-img >/dev/null
umask 077
mkdir "$destination"
destination=$(realpath "$destination")
mkdir "$destination/debian"
# Copy the base so the overlay never depends on a live deployment directory.
cp --reflink=auto "$base" "$destination/debian/base.qcow2"
qemu-img create -f qcow2 -F qcow2 -b "$destination/debian/base.qcow2" "$destination/debian/host.qcow2"
cp "$seed" "$destination/debian/seed.iso"
cp --reflink=auto "$flash" "$destination/bmc-2.18-rw3-test.mtd"
printf 'Prepared independent state: %s\n' "$destination"
printf '%s\n' 'Pristine firmware still needs BMC adaptation before host power testing.'
