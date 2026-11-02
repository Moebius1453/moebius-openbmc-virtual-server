from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


PROJECT = Path(__file__).resolve().parents[1]
SH = shutil.which('sh')


@unittest.skipUnless(SH and os.name == 'posix', 'Requires a POSIX shell')
class AdaptationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.backup = self.root / 'var/lib/virtual-server-adaptation'
        self.systemd = self.root / 'etc/systemd/system'
        self.fan = self.root / 'etc/phosphor-fan-presence/monitor/config.json'
        self.override = self.systemd / 'xyz.openbmc_project.Ipmi.Internal.SoftPowerOff.service.d/virtual-x86.conf'
        vendor = self.root / 'usr/share/phosphor-fan-presence/monitor/config.json'
        vendor.parent.mkdir(parents=True)
        vendor.write_text('{"vendor": true}\n')
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.calls = self.root / 'systemctl.log'
        systemctl = self.bin / 'systemctl'
        systemctl.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\ncase "$1" in cat) printf "[Unit]\\nDescription=Vendor\\n" ;; esac\n')
        systemctl.chmod(0o755)
        self.env = {**os.environ, 'PATH': str(self.bin) + os.pathsep + os.environ['PATH'],
                    'CALLS': str(self.calls)}
        installer = (PROJECT / 'scripts/adapt_virtual_bmc.sh').read_text()
        for path in ('/var/lib/virtual-server-adaptation', '/etc/systemd/system',
                     '/etc/phosphor-fan-presence', '/usr/share/phosphor-fan-presence'):
            installer = installer.replace(path, str(self.root) + path)
        self.installer = self.root / 'install.sh'
        self.installer.write_text(installer)

    def install(self):
        return subprocess.run(
            [SH, str(self.installer), str(PROJECT / 'config/fan-monitor-single-tach.json'),
             str(PROJECT / 'scripts/bmc-soft-poweroff.sh'), str(PROJECT)],
            env=self.env, text=True, capture_output=True, timeout=10)

    def put(self, path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def test_install_is_persistent_enabled_and_idempotent(self):
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual((self.backup / 'soft-poweroff.sh').read_bytes(),
                         (PROJECT / 'scripts/bmc-soft-poweroff.sh').read_bytes())
        self.assertEqual(self.override.read_text(),
                         (PROJECT / 'config/systemd/virtual-server-soft-poweroff.conf').read_text())
        for name in ('virtual-server-power-loss.service',
                     'virtual-server-restore-power-output.service'):
            self.assertEqual((self.systemd / name).read_bytes(),
                             (PROJECT / 'config/systemd' / name).read_bytes())
        second = self.install()
        self.assertEqual(second.returncode, 0, second.stderr)
        calls = self.calls.read_text().splitlines()
        self.assertTrue(any(line.startswith('enable ') for line in calls))
        self.assertFalse(any('--now' in line or line.startswith(('start ', 'restart '))
                             for line in calls))
        self.assertFalse((self.root / 'usr/local/libexec').exists())

    def test_conflicting_script_is_not_overwritten_or_partially_installed(self):
        dest = self.backup / 'restore-power-output.sh'
        self.put(dest, 'custom\n')
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(dest.read_text(), 'custom\n')
        self.assertFalse(self.fan.exists())
        self.assertFalse(self.systemd.exists())
        self.assertFalse(self.calls.exists())

    def test_known_legacy_override_is_backed_up_and_migrated(self):
        target = (PROJECT / 'config/systemd/virtual-server-soft-poweroff.conf').read_text()
        legacy = target.replace('/var/lib/virtual-server-adaptation/soft-poweroff.sh',
                                '/usr/local/libexec/virtual-server-soft-poweroff')
        self.put(self.override, legacy)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.override.read_text(), target)
        backups = list(self.backup.glob('install-*/soft-poweroff-before-persistent.conf'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), legacy)

    def test_unknown_override_is_preserved(self):
        self.put(self.override, '[Service]\nExecStart=/custom\n')
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.override.read_text(), '[Service]\nExecStart=/custom\n')
        self.assertFalse((self.backup / 'soft-poweroff.sh').exists())
        self.assertFalse(self.fan.exists())

    def test_symlink_destination_is_rejected(self):
        target = self.root / 'user-data'
        target.write_text('preserve\n')
        self.backup.mkdir(parents=True)
        (self.backup / 'soft-poweroff.sh').symlink_to(target)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_text(), 'preserve\n')
        self.assertFalse(self.fan.exists())


@unittest.skipUnless(SH and os.name == 'posix', 'Requires a POSIX shell')
class PowerLossTests(unittest.TestCase):
    def run_listener(self, pgood, state, chassis, event):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            calls = root / 'calls'
            busctl = root / 'busctl'
            busctl.write_text('''#!/bin/sh
case "$2" in
    get-property)
        case "$6" in
            pgood) cat "$PGOOD_FILE" ;;
            state) printf '%s\\n' "$STATE" ;;
            CurrentPowerState) printf 's "xyz.openbmc_project.State.Chassis.PowerState.%s"\\n' "$CHASSIS" ;;
        esac ;;
    set-property)
        printf '%s\\n' "$*" >> "$CALLS"
        printf 'i 0\\n' > "$PGOOD_FILE" ;;
esac
''')
            monitor = root / 'dbus-monitor'
            monitor.write_text('''#!/bin/sh
printf 'i 0\\n' > "$PGOOD_FILE"
if [ "$EVENT" = yes ]; then
    printf '%s\\n' 'signal path=/org/openbmc/control/power0; interface=org.openbmc.control.Power; member=PowerLost'
fi
''')
            busctl.chmod(0o755)
            monitor.chmod(0o755)
            pgood_file = root / 'pgood'
            pgood_file.write_text(pgood + '\n')
            env = {**os.environ, 'PATH': str(root) + os.pathsep + os.environ['PATH'],
                   'PGOOD_FILE': str(pgood_file), 'STATE': state,
                   'CHASSIS': chassis, 'EVENT': event, 'CALLS': str(calls)}
            result = subprocess.run([SH, str(PROJECT / 'scripts/bmc-reconcile-power-loss.sh')],
                                    env=env, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            return calls.read_text().splitlines() if calls.exists() else []

    def test_real_power_lost_requests_only_native_off(self):
        calls = self.run_listener('i 1', 'i 1', 'On', 'yes')
        self.assertEqual(len(calls), 1)
        self.assertIn('RequestedPowerTransition s xyz.openbmc_project.State.Chassis.Transition.Off', calls[0])
        self.assertNotIn('CurrentPowerState', calls[0])

    def test_already_transitioning_does_not_repeat_off(self):
        self.assertEqual(self.run_listener('i 1', 'i 1', 'TransitioningToOff', 'yes'), [])

    def test_completed_off_does_not_repeat_off(self):
        self.assertEqual(self.run_listener('i 0', 'i 0', 'Off', 'yes'), [])


if __name__ == '__main__':
    unittest.main()
