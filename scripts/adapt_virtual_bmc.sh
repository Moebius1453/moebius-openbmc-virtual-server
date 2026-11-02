#!/bin/sh
set -eu
fan_config=${1:?Supply the single-tach fan monitor JSON already copied into the BMC}
soft_poweroff=${2:?Supply the guest ACPI shutdown script already copied into the BMC}
bundle=${3:?Supply the copied bundle directory containing scripts/ and config/systemd/}
backup=/var/lib/virtual-server-adaptation
systemd=/etc/systemd/system
soft_override=$systemd/xyz.openbmc_project.Ipmi.Internal.SoftPowerOff.service.d/virtual-x86.conf
units='avsbus-enable@0.service avsbus-disable@0.service vrm-control@0.service fsi-scan@0.service power-workarounds@0.service pseq-monitor.service pseq-monitor-pgood.service ir35221-on-bind@0.service'
services='virtual-server-restore-power-output.service virtual-server-power-loss.service'
for source in "$fan_config" "$soft_poweroff" \
    "$bundle/scripts/bmc-restore-power-output.sh" \
    "$bundle/scripts/bmc-reconcile-power-loss.sh" \
    "$bundle/config/systemd/virtual-server-soft-poweroff.conf" \
    "$bundle/config/systemd/virtual-server-restore-power-output.service" \
    "$bundle/config/systemd/virtual-server-power-loss.service"; do
    test -f "$source"
done
mkdir -p "$backup"
stage=$(mktemp -d "$backup/install-XXXXXXXX")
printf '%s\n' '[Unit]' 'ConditionPathExists=/run/virtual-server-power-hardware-present' > "$stage/power.conf"
cat > "$stage/legacy-soft.conf" <<'UNIT'
[Unit]
Before=obmc-power-stop@0.service obmc-chassis-poweroff@0.target obmc-host-stop@0.target obmc-host-stop-pre@0.target
ConditionPathExists=

[Service]
ExecStart=
ExecStart=/bin/sh /usr/local/libexec/virtual-server-soft-poweroff
TimeoutStartSec=70
UNIT
check_file() {
    if [ -L "$2" ] || { [ -e "$2" ] && [ ! -f "$2" ]; }; then
        printf '%s\n' "Not a regular destination file: $2" >&2
        exit 1
    fi
    if [ -e "$2" ] && ! cmp -s "$1" "$2"; then
        printf '%s\n' "Existing file differs; leaving it unchanged: $2" >&2
        exit 1
    fi
}
for unit in $units; do
    check_file "$stage/power.conf" "$systemd/$unit.d/virtual-x86.conf"
done
check_file "$fan_config" /etc/phosphor-fan-presence/monitor/config.json
check_file "$soft_poweroff" "$backup/soft-poweroff.sh"
check_file "$bundle/scripts/bmc-restore-power-output.sh" "$backup/restore-power-output.sh"
check_file "$bundle/scripts/bmc-reconcile-power-loss.sh" "$backup/reconcile-power-loss.sh"
for service in $services; do
    check_file "$bundle/config/systemd/$service" "$systemd/$service"
done
if [ ! -L "$soft_override" ] && [ -f "$soft_override" ] && cmp -s "$stage/legacy-soft.conf" "$soft_override"; then
    cp -p "$soft_override" "$stage/soft-poweroff-before-persistent.conf"
else
    check_file "$bundle/config/systemd/virtual-server-soft-poweroff.conf" "$soft_override"
fi
install_file() {
    if [ ! -e "$2" ]; then
        mkdir -p "$(dirname "$2")"
        cp "$1" "$2"
    fi
}
for unit in $units; do
    if [ ! -e "$systemd/$unit.d/virtual-x86.conf" ]; then
        systemctl cat "$unit" > "$stage/$unit.original"
    fi
    install_file "$stage/power.conf" "$systemd/$unit.d/virtual-x86.conf"
done
if [ ! -e /etc/phosphor-fan-presence/monitor/config.json ]; then
    cp -p /usr/share/phosphor-fan-presence/monitor/config.json "$stage/fan-monitor-vendor.json"
fi
install_file "$fan_config" /etc/phosphor-fan-presence/monitor/config.json
install_file "$soft_poweroff" "$backup/soft-poweroff.sh"
install_file "$bundle/scripts/bmc-restore-power-output.sh" "$backup/restore-power-output.sh"
install_file "$bundle/scripts/bmc-reconcile-power-loss.sh" "$backup/reconcile-power-loss.sh"
for service in $services; do
    install_file "$bundle/config/systemd/$service" "$systemd/$service"
done
if [ -e "$stage/soft-poweroff-before-persistent.conf" ]; then
    cp "$bundle/config/systemd/virtual-server-soft-poweroff.conf" "$soft_override"
else
    if [ ! -e "$soft_override" ]; then
        systemctl cat xyz.openbmc_project.Ipmi.Internal.SoftPowerOff.service > "$stage/soft-poweroff.original"
    fi
    install_file "$bundle/config/systemd/virtual-server-soft-poweroff.conf" "$soft_override"
fi
systemctl daemon-reload
systemctl enable $services
printf '%s\n' 'Adaptation installed; lifecycle services are enabled for the next BMC boot. No running service was restarted.'
