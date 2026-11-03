# Minimal thermal feedback experiment

This experiment is incomplete. Do not treat the current image as an accepted thermal-control deployment.

The optional LAB_THERMAL=1 integration feeds a simple thermal model into the QEMU TMP105 temperature property. MAX31785 external feedback separates guest-commanded target RPM from externally calculated actual RPM. OpenBMC still reads the normal Linux hardware-monitoring path and retains fan protection. No sensor D-Bus property is overwritten.

## Current evidence

The third QEMU patch compiled on 2026-11-02. The resulting binary SHA256 is d9933c50969cbb300abdb30c100f5b9f0ab7416a25ff83be5f721db239236a97. A separate thermal image and independent state were created. Initial host-off samples show temperature 25 degrees C and actual RPM gradually following zero targets, demonstrating that the optional QOM interfaces and model update path execute. This does not prove temperature-triggered native fan regulation.

The stock Witherspoon fan policy includes PCIe-temperature speed increases above 55 degrees C and decreases below 52 degrees C. A real manual-load test reached 55.562 degrees C through Linux hwmon while fan targets remained 10500 RPM. Both OCC objects exist but report OccActive=false; the compiled policy gates its temperature-control events on both being active. Thus service absence is not the observed cause: the POWER-specific activation prerequisite is incompatible with the x86 host. No OCC property was falsified. Load was restored to zero and the host completed ACPI shutdown with exit 0 and chassis Off. Native temperature-dependent fan regulation remains unproven. The installed controller exposes no configuration directory at the usual /etc or /usr/share phosphor-fan-control paths; a deliberate x86 policy adaptation is still needed.

## Model and input

src/thermal_model.py uses first-order fan inertia and heating minus airflow-dependent cooling. Constants describe a demonstration model, not calibrated physical hardware. src/thermal_bridge.py discovers MAX31785 and TMP105 and runs inside the existing manager, avoiding a second client on its BMC QMP socket.

While powered, the current input is a private state/thermal-load.json object with numeric load between 0 and 1. This is explicitly manual synthetic input, not measured Debian CPU utilization. Host-off input is zero. Actual guest-load measurement remains unimplemented.

Errors are logged as thermal_error. There is not yet a proven safe recovery policy for stale input or BMC reset; do not inject failures or leave an unverified running host unattended. Snapshot/live migration of the new feedback state has not been implemented or accepted.

## Remaining acceptance

Confirm native BMC readiness, actual host startup, matching virtual-device/hwmon readings, and native target changes as temperature rises and falls. Then add real Debian-load measurement. Keep the experiment on independent disks and loopback-only management ports. Do not disable fan protection to force a passing result.
