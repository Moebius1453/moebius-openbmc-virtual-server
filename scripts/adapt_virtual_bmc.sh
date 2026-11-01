#!/bin/sh
set -eu
fan_config=${1:?Supply the single-tach fan monitor JSON already copied into the BMC}
test -f "$fan_config"
soft_poweroff=${2:?Supply the guest ACPI shutdown script already copied into the BMC}
test -f "$soft_poweroff"
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
soft_dest=/usr/local/libexec/virtual-server-soft-poweroff
soft_override=/etc/systemd/system/xyz.openbmc_project.Ipmi.Internal.SoftPowerOff.service.d/virtual-x86.conf
if [ -e "$soft_dest" ] && ! cmp -s "$soft_poweroff" "$soft_dest"; then
    printf '%s\n' 'Existing soft poweroff script differs; leaving it unchanged.' >&2
    exit 1
fi
mkdir -p /usr/local/libexec
if [ ! -e "$soft_dest" ]; then
    cp "$soft_poweroff" "$soft_dest"
    chmod 0755 "$soft_dest"
fi
mkdir -p "$(dirname "$soft_override")"
if [ ! -e "$soft_override" ]; then
    systemctl cat xyz.openbmc_project.Ipmi.Internal.SoftPowerOff.service > "$backup/soft-poweroff.original"
    cat > "$soft_override" <<'UNIT'
[Unit]
Before=obmc-power-stop@0.service obmc-chassis-poweroff@0.target obmc-host-stop@0.target obmc-host-stop-pre@0.target
ConditionPathExists=

[Service]
ExecStart=
ExecStart=/bin/sh /usr/local/libexec/virtual-server-soft-poweroff
TimeoutStartSec=70
UNIT
fi
systemctl daemon-reload
printf '%s\n' 'Adaptation installed; no running service was restarted.'
