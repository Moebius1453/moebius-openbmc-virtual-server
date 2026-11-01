#!/bin/bash
set -euo pipefail
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
artifact_dir=$(realpath "${1:?Supply the exported QEMU artifact directory}")
image=${2:-moebius-openbmc-virtual-server:integration-rpm}
test -f "$artifact_dir/qemu-system-arm"
test -f "$artifact_dir/max31785-rpm-mode.patch"
test -f "$artifact_dir/SHA256SUMS"
(
    cd "$artifact_dir"
    sha256sum -c SHA256SUMS
)
docker buildx build --load \
    --build-context "qemu-rpm=$artifact_dir" \
    --file "$project_dir/Dockerfile.integration" \
    --tag "$image" "$project_dir"
printf 'Built %s; no running container was replaced.\n' "$image"
