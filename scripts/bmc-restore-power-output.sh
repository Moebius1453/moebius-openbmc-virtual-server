#!/bin/sh
set -eu
pgood=$(busctl get-property org.openbmc.control.Power /org/openbmc/control/power0 org.openbmc.control.Power pgood)
[ "$pgood" = 'i 1' ] || exit 0
base=
for chip in /sys/class/gpio/gpiochip*; do
    if [ "$(cat "$chip/label")" = 1e780000.gpio ]; then
        base=$(cat "$chip/base")
        break
    fi
done
test -n "$base"
number=$((base + 25))
line=/sys/class/gpio/gpio$number
owned=false
if [ ! -d "$line" ]; then
    printf '%s\n' "$number" > /sys/class/gpio/export
    owned=true
fi
printf 'out\n' > "$line/direction"
printf '1\n' > "$line/value"
if [ "$owned" = true ]; then
    printf '%s\n' "$number" > /sys/class/gpio/unexport
fi
