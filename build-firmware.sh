#!/bin/bash
set -euo pipefail
cd /work
commit=05f7a3f2eddb94263a03c5e601452f0d4ec5c87b
if [ ! -e openbmc ]; then
    git clone --depth 1 --branch 2.18.0 https://github.com/openbmc/openbmc.git openbmc
fi
cd openbmc
test "$(git rev-parse HEAD)" = "$commit" || {
    printf '%s\n' 'Source revision differs; stopping without changing it.' >&2
    exit 1
}
set +u
source setup witherspoon build/witherspoon
set -u
if ! test -e conf/moebius-build-limits.inc; then
    printf '%s\n' \
        'BB_NUMBER_THREADS = "4"' \
        'PARALLEL_MAKE = "-j4"' \
        'DL_DIR = "/work/downloads"' \
        'SSTATE_DIR = "/work/sstate-cache"' \
        > conf/moebius-build-limits.inc
fi
if ! grep -q '^require conf/moebius-build-limits.inc$' conf/local.conf; then
    printf '\n%s\n' 'require conf/moebius-build-limits.inc' >> conf/local.conf
fi
if ! grep -q '^require /work/build-mirrors.inc$' conf/local.conf; then
    printf '\n%s\n' 'require /work/build-mirrors.inc' >> conf/local.conf
fi
bitbake obmc-phosphor-image
