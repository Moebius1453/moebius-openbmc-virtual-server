#!/bin/sh
set -eu
binary=${1:?Supply the controller binary already copied into BMC memory}
expected=${2:?Supply its SHA256}
unit=phosphor-fan-control@0.service
actual=$(sha256sum "$binary")
[ "${actual%% *}" = "$expected" ]
pgood=$(busctl get-property org.openbmc.control.Power /org/openbmc/control/power0 org.openbmc.control.Power pgood) || exit 75
[ "$pgood" = 'i 0' ] || { printf '%s\n' 'Host is powered; controller left unchanged' >&2; exit 1; }
ready=$(busctl get-property xyz.openbmc_project.State.BMC /xyz/openbmc_project/state/bmc0 xyz.openbmc_project.State.BMC CurrentBMCState) || exit 75
[ "$ready" = 's "xyz.openbmc_project.State.BMC.BMCState.Ready"' ] || exit 75
case "$binary" in /tmp/*) ;; *) printf '%s\n' 'Controller must be staged in BMC memory' >&2; exit 1 ;; esac
case "$binary" in *[!a-zA-Z0-9_./-]*) exit 1 ;; esac
file=/run/systemd/system/$unit.d/virtual-x86-managed.conf
if [ -e /run/systemd/system/$unit.d/virtual-x86-test.conf ]; then
    printf '%s\n' 'Existing experimental override needs explicit migration first' >&2
    exit 1
fi
stage=$(mktemp /tmp/fan-unit-XXXXXXXX)
printf '[Service]\nExecStart=\nExecStart=%s --control\n' "$binary" > "$stage"
if [ -L "$file" ] || { [ -e "$file" ] && ! cmp -s "$stage" "$file"; }; then
    printf '%s\n' 'Conflicting override; unchanged' >&2
    exit 1
fi
if [ -f "$file" ] && cmp -s "$stage" "$file" && systemctl is-active --quiet "$unit"; then
    pid=$(systemctl show "$unit" -p MainPID --value)
    if [ "$pid" -gt 0 ] && [ "$(readlink "/proc/$pid/exe")" = "$binary" ]; then
        printf '%s\n' 'Controller already active; no restart'
        exit 0
    fi
fi
chmod 755 "$binary"
mkdir -p "/run/systemd/system/$unit.d"
if [ ! -e "$file" ]; then
    cp "$stage" "$file"
fi
systemctl daemon-reload
systemctl restart "$unit"
systemctl is-active "$unit"
