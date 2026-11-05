# Minimal thermal feedback experiment

## Current result: real CPU cycle

On 2026-11-04 the real Debian CPU experiment completed 120 seconds each of idle, load and cooldown, with mean CPU utilization of 0.17%, 99.99% and 0.18%. Native BMC targets rose from about 5000 to 7200 RPM as the model heated; actual tach feedback followed. Removing CPU load cooled the model to about 36.5 degrees C and reduced targets to 6600 RPM. The guest then completed ACPI shutdown with exit 0, PowerGood 0 and chassis Off.

The x86 policy generator replaces the POWER OCC activation prerequisite with actual PowerGood. Actual CPU samples are published by scripts/forward-guest-load.py. The complete workflow is documented in [REAL-LOAD.md](REAL-LOAD.md). Earlier investigation notes below describe the discovery sequence, not the current feature status.

## Earlier interface investigation

The optional LAB_THERMAL=1 integration feeds a simple thermal model into the QEMU TMP105 temperature property. MAX31785 external feedback separates guest-commanded target RPM from externally calculated actual RPM. OpenBMC still reads the normal Linux hardware-monitoring path and retains fan protection. No sensor D-Bus property is overwritten.

## Historical evidence: 2026-11-02

The third QEMU patch compiled on 2026-11-02. The resulting binary SHA256 is d9933c50969cbb300abdb30c100f5b9f0ab7416a25ff83be5f721db239236a97. A separate thermal image and independent state were created. Initial host-off samples show temperature 25 degrees C and actual RPM gradually following zero targets, demonstrating that the optional QOM interfaces and model update path execute. This does not prove temperature-triggered native fan regulation.

Historical status: the following paragraph describes the OCC-gated policy before the x86 adaptation described above.

The stock Witherspoon fan policy includes PCIe-temperature speed increases above 55 degrees C and decreases below 52 degrees C. A real manual-load test reached 55.562 degrees C through Linux hwmon while fan targets remained 10500 RPM. Both OCC objects exist but report OccActive=false; the compiled policy gates its temperature-control events on both being active. Thus service absence is not the observed cause: the POWER-specific activation prerequisite is incompatible with the x86 host. No OCC property was falsified. Load was restored to zero and the host completed ACPI shutdown with exit 0 and chassis Off. Native temperature-dependent fan regulation remains unproven. The installed controller exposes no configuration directory at the usual /etc or /usr/share phosphor-fan-control paths; a deliberate x86 policy adaptation is still needed.

## Model and input

src/thermal_model.py uses first-order fan inertia and heating minus airflow-dependent cooling. Constants describe a demonstration model, not calibrated physical hardware. src/thermal_bridge.py discovers MAX31785 and TMP105 and runs inside the existing manager, avoiding a second client on its BMC QMP socket.

While powered, state/thermal-load.json supplies numeric load between 0 and 1. The manual source supports controlled model experiments; guest-proc-stat supplies measured Debian CPU utilization. The host publishes received_at in its own clock domain. Guest samples older than five seconds use the explicitly labeled stale-guest-conservative source with load 1. Host-off input is zero.

Errors are logged as thermal_error. BMC RESET causes the manager to rediscover thermal devices and re-enable external fan feedback. After BMC startup, the stage mode reloads the x86 controller into memory; check validates readiness without powering on the host. These are explicit local operations, not a background recovery service.

## Operating workflow

Use [REAL-LOAD.md](REAL-LOAD.md) for check, stage and cycle commands. A BMC restart followed by fresh controller upload, activation and check completed successfully on 2026-11-04. Keep writable disks independent between instances and bind management ports to loopback. Fault injection and snapshot/live migration are separate engineering tasks.
