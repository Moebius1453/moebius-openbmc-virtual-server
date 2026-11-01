#!/bin/bash
set -euo pipefail
work=${QEMU_WORK_DIR:-/work/openbmc/build/witherspoon/tmp/work/x86_64-linux/qemu-system-native/9.2.0}
source_dir=$work/qemu-9.2.0
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
patch_file=${QEMU_PATCH_FILE:-$project_dir/patches/qemu/0001-max31785-honor-rpm-mode.patch}
output_dir=${QEMU_OUTPUT_DIR:-/work/artifacts/qemu-rpm}
test -f "$patch_file"
if patch --dry-run --batch --forward -p1 -d "$source_dir" -i "$patch_file" >/dev/null 2>&1; then
    cp -p "$source_dir/hw/sensor/max31785.c" "$source_dir/hw/sensor/max31785.c.bak-$(date +%Y%m%d-%H%M%S)"
    patch --batch --forward -p1 -d "$source_dir" -i "$patch_file"
elif patch --dry-run --batch --forward -R -p1 -d "$source_dir" -i "$patch_file" >/dev/null 2>&1; then
    printf '%s\n' 'RPM patch already applied.'
else
    printf '%s\n' 'Patch does not match source; stopping.' >&2
    exit 1
fi
export PATH="$work/recipe-sysroot-native/usr/bin/python3-native:$work/recipe-sysroot-native/usr/bin:$work/recipe-sysroot-native/usr/sbin:$PATH"
cd "$work/build"
"$work/recipe-sysroot-native/usr/bin/ninja" -j4 qemu-system-arm
./qemu-system-arm --version
mkdir -p "$output_dir"
release_dir=$(mktemp -d "$output_dir/build-XXXXXXXX")
install -m 0755 qemu-system-arm "$release_dir/qemu-system-arm"
cp "$patch_file" "$release_dir/max31785-rpm-mode.patch"
{
    printf 'QEMU version: 9.2.0\nSource directory: %s\n' "$source_dir"
    ./qemu-system-arm --version
} > "$release_dir/build-info.txt"
(
    cd "$release_dir"
    sha256sum qemu-system-arm max31785-rpm-mode.patch > SHA256SUMS
)
printf 'QEMU artifacts exported to %s\n' "$release_dir"
