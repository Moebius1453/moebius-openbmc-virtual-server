#!/bin/sh
set -eu
reconcile() {
    pgood=$(busctl --timeout=5 get-property org.openbmc.control.Power /org/openbmc/control/power0 org.openbmc.control.Power pgood)
    [ "$pgood" = 'i 0' ] || return 0
    state=$(busctl --timeout=5 get-property org.openbmc.control.Power /org/openbmc/control/power0 org.openbmc.control.Power state)
    [ "$state" = 'i 1' ] || return 0
    chassis=$(busctl --timeout=5 get-property xyz.openbmc_project.State.Chassis /xyz/openbmc_project/state/chassis0 xyz.openbmc_project.State.Chassis CurrentPowerState)
    [ "$chassis" = 's "xyz.openbmc_project.State.Chassis.PowerState.On"' ] || return 0
    printf '%s\n' 'Actual PowerGood lost; requesting native chassis Off.'
    busctl --timeout=5 set-property xyz.openbmc_project.State.Chassis /xyz/openbmc_project/state/chassis0 xyz.openbmc_project.State.Chassis RequestedPowerTransition s xyz.openbmc_project.State.Chassis.Transition.Off
}
reconcile
dbus-monitor --system "type='signal',sender='org.openbmc.control.Power',path='/org/openbmc/control/power0',interface='org.openbmc.control.Power',member='PowerLost'" |
while IFS= read -r line; do
    case "$line" in
        *member=PowerLost*) reconcile ;;
    esac
done
