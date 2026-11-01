#!/bin/sh
set -eu
base=
for chip in /sys/class/gpio/gpiochip*; do
    if [ "$(cat "$chip/label")" = 1e780000.gpio ]; then
        base=$(cat "$chip/base")
        break
    fi
done
test -n "$base"
request=$((base + 27))
line=/sys/class/gpio/gpio$request
owned=false
if [ ! -d "$line" ]; then
    printf '%s\n' "$request" > /sys/class/gpio/export
    owned=true
fi
cleanup() {
    printf '0\n' > "$line/value"
    if [ "$owned" = true ]; then
        printf '%s\n' "$request" > /sys/class/gpio/unexport
    fi
}
trap cleanup EXIT
trap 'exit 1' HUP INT TERM
# QEMU drops the initial value when direction and value change together.
printf 'out\n' > "$line/direction"
printf '1\n' > "$line/value"
remaining=60
while [ "$remaining" -gt 0 ]; do
    if [ "$(gpioget gpiochip0 28)" = 1 ]; then
        exit 0
    fi
    sleep 1
    remaining=$((remaining - 1))
done
printf '%s\n' 'Guest shutdown was not acknowledged within 60 seconds.' >&2
exit 1
