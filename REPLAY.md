# Independent integration replay

This entry keeps an integration replay separate from an existing deployment. It does not replace the existing integration Compose file or update running containers.

## Requirements and data protection

Use Linux with Docker, Compose v2, KVM and qemu-img. Build the integration image with scripts/build-integration.sh and the exported two-patch QEMU artifact first. Set an explicit new image tag; do not move a live deployment tag during replay.

The input flash must be a pristine firmware artifact or a powered-off adapted test flash. Never copy a flash while its QEMU process is writing it. Use the original immutable Debian cloud image, not a live host.qcow2. The seed contains login configuration and belongs outside Git.

Prepare a previously nonexistent state directory:

```bash
bash scripts/prepare-replay-state.sh "$FIRMWARE" "$DEBIAN_BASE" "$SEED_ISO" "$REPLAY_STATE"
```

The script copies the base and creates a new writable overlay. A failure leaves the new partial directory intact for inspection; it does not delete or overwrite existing data. The base copy must remain immutable while its overlay exists.

## Adapt a pristine BMC

A pristine flash must first boot in an isolated BMC instance using the same patched integration image. Copy scripts/, config/systemd/ and config/fan-monitor-single-tach.json into a temporary bundle inside that BMC. In the BMC, run:

```bash
sh /tmp/replay-bundle/scripts/adapt_virtual_bmc.sh \
  /tmp/replay-bundle/config/fan-monitor-single-tach.json \
  /tmp/replay-bundle/scripts/bmc-soft-poweroff.sh \
  /tmp/replay-bundle
```

The installer checks conflicts before installing its managed files, saves installation evidence under /var/lib/virtual-server-adaptation, and enables lifecycle services without restarting them. It is not a fully transactional installer. Unknown conflicting content is an error, not permission to overwrite it.

Stop that isolated BMC before using its adapted flash for full integration. Never start two QEMU processes on the same writable flash or host disk.

## Start the independent full integration

Set LAB_IMAGE to the image tag you built and LAB_STATE to the absolute independent state directory. Confirm the default loopback ports 2270, 2470 and 2271 are unused, or set BMC_SSH_PORT, BMC_HTTPS_PORT and HOST_SSH_PORT explicitly.

```bash
export KVM_GID=$(stat -c %g /dev/kvm)
export LAB_IMAGE LAB_STATE
sudo --preserve-env=KVM_GID,LAB_IMAGE,LAB_STATE docker compose -f compose.replay.yaml up -d
```

If you override ports, preserve those variables through sudo as well. Do not use this command to adopt a container created with docker run; inspect and stop the test instance first. No Docker socket, privileged mode or public QMP endpoint is needed.

Check BMC SSH, the persistent script hashes, both lifecycle services, native PowerGood and chassis state. Then request a native power transition and check actual Debian startup and shutdown. An HTTP success response is not proof that the host reached its final state.

## Evidence and current limits

On 2026-11-02, a newly built integration image booted an independent copy of the original firmware. The three-argument installer completed twice with exit 0. Both services were enabled; explicitly starting them produced a successful oneshot and an active PowerLost listener. This proves first installation and repeat installation on real firmware, not only mocked tests.

The subsequent full integration replay uses an independent Debian base copy, new overlay and adapted flash. The subsequent acceptance confirmed a changed BMC boot ID with all three script hashes preserved and both lifecycle services automatically active. The independent Debian guest reached systemd running through SSH. Native BMC shutdown produced an ACPI request, guest exit code 0, complete filesystem unmounting and Power down in the serial console, followed by PowerGood 0, chassis Off and a successful soft-poweroff service. First startup and graceful shutdown on the full replay passed; repeated cycling and broader failure recovery were not covered. The preparation script and Compose entry added alongside this work have not themselves been executed end to end; the accepted instance was launched with equivalent explicit docker run commands. The existing deployment had previously passed limited lifecycle and Redfish graceful-shutdown tests; those results must not be substituted for this new replay's results.

Next: finish this replay's actual host power test, then implement the minimal load/temperature/fan feedback loop. Host boot-complete reporting, SOL, host IPMI and comprehensive disconnect recovery remain separate gaps.
