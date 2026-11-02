#!/bin/bash
set -euo pipefail
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work=${QEMU_WORK_DIR:-/work/openbmc/build/witherspoon/tmp/work/x86_64-linux/qemu-system-native/9.2.0}
source_dir=$work/qemu-9.2.0
feedback_patch=$project_dir/patches/qemu/0003-max31785-external-fan-feedback.patch
# Apply the optional interface first so the existing exporter builds all changes.
if patch --dry-run --batch --forward -p1 -d "$source_dir" -i "$feedback_patch" >/dev/null 2>&1; then
    backup=$(mktemp "$source_dir/hw/sensor/max31785.c.bak-XXXXXXXX")
    cp -p "$source_dir/hw/sensor/max31785.c" "$backup"
    patch --batch --forward -p1 -d "$source_dir" -i "$feedback_patch"
elif patch --dry-run --batch --forward -R -p1 -d "$source_dir" -i "$feedback_patch" >/dev/null 2>&1; then
    printf '%s\n' 'External feedback patch already applied'
else
    printf '%s\n' 'External feedback patch does not match source' >&2
    exit 1
fi
export PATH="$work/recipe-sysroot-native/usr/bin/python3-native:$work/recipe-sysroot-native/usr/bin:$work/recipe-sysroot-native/usr/sbin:$PATH"
cd "$work/build"
"$work/recipe-sysroot-native/usr/bin/ninja" -j4 qemu-system-arm
output_dir=${QEMU_OUTPUT_DIR:-/work/artifacts/qemu-thermal}
mkdir -p "$output_dir"
release_dir=$(mktemp -d "$output_dir/build-XXXXXXXX")
install -m 0755 qemu-system-arm "$release_dir/qemu-system-arm"
cp "$project_dir/patches/qemu/0001-max31785-honor-rpm-mode.patch" "$release_dir/max31785-rpm-mode.patch"
cp "$project_dir/patches/qemu/0002-max31785-status-fans-byte.patch" "$release_dir/max31785-status-byte.patch"
cp "$feedback_patch" "$release_dir/max31785-external-feedback.patch"
(cd "$release_dir" && sha256sum qemu-system-arm *.patch > SHA256SUMS)
printf 'Thermal QEMU artifacts: %s\n' "$release_dir"
printf '%s\n' 'External feedback is opt-in; existing machines retain legacy fan behavior.'
