#!/bin/sh
set -eu
backup=/var/lib/virtual-server-adaptation
mkdir -p "$backup"
for unit in avsbus-enable@0.service avsbus-disable@0.service vrm-control@0.service fsi-scan@0.service power-workarounds@0.service pseq-monitor.service pseq-monitor-pgood.service ir35221-on-bind@0.service; do
    dir=/etc/systemd/system/$unit.d
    mkdir -p "$dir"
    file=$dir/virtual-x86.conf
    if [ -e "$file" ]; then
        printf '%s\n' "Already configured: $unit"
        continue
    fi
    systemctl cat "$unit" > "$backup/$unit.original"
    printf '%s\n' '[Unit]' 'ConditionPathExists=/run/virtual-server-power-hardware-present' > "$file"
done
systemctl daemon-reload
