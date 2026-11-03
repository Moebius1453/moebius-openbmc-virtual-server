#!/bin/bash
set -euo pipefail
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
work=${FAN_WORK_DIR:-/work/openbmc/build/witherspoon/tmp/work/witherspoon-openbmc-linux-gnueabi/phosphor-fan/1.0+git}
events=$work/recipe-sysroot/usr/share/phosphor-fan-control/events.yaml
output=${FAN_OUTPUT_DIR:-/work/artifacts/fan-x86}
mkdir -p "$output"
release=$(mktemp -d "$output/build-XXXXXXXX")
test -f "$events"
test ! -L "$events"
cp -p "$events" "$release/events-original.yaml"
python3 "$project_dir/scripts/prepare-x86-fan-policy.py" "$events" "$release/events-x86.yaml"
# The recipe sysroot may share hardlinks: replace its entry, never edit in place.
cp "$release/events-x86.yaml" "$events.x86-new"
mv "$events.x86-new" "$events"
restore() {
    cp "$release/events-original.yaml" "$events.restore"
    mv "$events.restore" "$events"
}
trap restore EXIT
bash "$work/temp/run.do_compile"
install -m 0755 "$work/build/control/phosphor-fan-control" "$release/phosphor-fan-control"
(cd "$release" && sha256sum phosphor-fan-control events-*.yaml > SHA256SUMS)
printf 'Virtual x86 fan controller: %s\n' "$release"
printf '%s\n' 'Recipe policy input restored. Built output contains the explicit x86 policy.'
