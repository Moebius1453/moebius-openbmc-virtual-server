#!/bin/bash
set -euo pipefail
cd /work/openbmc
commit=05f7a3f2eddb94263a03c5e601452f0d4ec5c87b
test "$(git rev-parse HEAD)" = "$commit" || {
    printf '%s\n' 'Source revision differs; stopping without changing it.' >&2
    exit 1
}
set +u
source setup witherspoon build/witherspoon
set -u
# Build the frontend package directly without changing the running firmware.
bitbake webui-vue
shopt -s nullglob
paths=(tmp/work/*/webui-vue/*/packages-split/webui-vue/usr/share/www)
if [ "${#paths[@]}" -ne 1 ]; then
    printf '%s\n' 'Expected exactly one packaged web frontend; inspect build outputs.' >&2
    exit 1
fi
www="${paths[0]}"
indexes=("$www"/index.html "$www"/index.html.gz "$www"/index.*.html.gz)
found_index=false
for index in "${indexes[@]}"; do
    if [ -f "$index" ]; then
        found_index=true
    fi
done
if [ "$found_index" != true ]; then
    printf '%s\n' 'Packaged frontend has no index page.' >&2
    exit 1
fi
mkdir -p /work/artifacts/webui
out=$(mktemp -d /work/artifacts/webui/build-XXXXXXXX)
tar -czf "$out/webui-www.tar.gz" -C "$www" .
sha256sum "$out/webui-www.tar.gz" > "$out/SHA256SUMS"
printf 'Frontend artifact: %s\n' "$out"
printf '%s\n' 'Build only: no BMC files, flash, or running services were changed.'
