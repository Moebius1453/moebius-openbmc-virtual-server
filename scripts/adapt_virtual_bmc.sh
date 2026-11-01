#!/bin/sh
set -eu
fan_config=${1:?Supply the single-tach fan monitor JSON already copied into the BMC}
test -f "$fan_config"
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
monitor_dir=/etc/phosphor-fan-presence/monitor
mkdir -p "$monitor_dir"
if [ -e "$monitor_dir/config.json" ]; then
    if ! cmp -s "$fan_config" "$monitor_dir/config.json"; then
        printf '%s\n' 'Existing fan monitor override differs; leaving it unchanged.' >&2
        exit 1
    fi
else
    if [ ! -e "$backup/fan-monitor-vendor.json" ]; then
        cp -p /usr/share/phosphor-fan-presence/monitor/config.json "$backup/fan-monitor-vendor.json"
    fi
    cp "$fan_config" "$monitor_dir/config.json"
fi
systemctl daemon-reload
printf '%s\n' 'Adaptation installed; no running service was restarted.'
