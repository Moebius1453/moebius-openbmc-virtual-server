#!/bin/bash
set -euo pipefail
work=/work/openbmc/build/witherspoon/tmp/work/x86_64-linux/qemu-system-native/9.2.0
source_dir=$work/qemu-9.2.0
patch_file=/work/max31785-rpm-mode.patch
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
