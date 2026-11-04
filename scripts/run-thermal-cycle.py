#!/usr/bin/env python3
"""Run one isolated thermal experiment with native power control and cleanup."""
import argparse
import getpass
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time

import paramiko


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--server', required=True)
    p.add_argument('--user', required=True)
    p.add_argument('--bmc-port', type=int, default=2280)
    p.add_argument('--bmc-fingerprint', required=True)
    p.add_argument('--guest-port', type=int, default=2281)
    p.add_argument('--guest-fingerprint', required=True)
    p.add_argument('--key', required=True)
    p.add_argument('--state', required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--controller', type=Path,
                   help='Optional local controller binary to stage before powering on')
    p.add_argument('--controller-sha256',
                   help='Required checksum when --controller is supplied')
    a = p.parse_args()
    controller_data = None
    if a.controller:
        import hashlib
        controller_data = a.controller.read_bytes()
        if not a.controller_sha256 or hashlib.sha256(controller_data).hexdigest() != a.controller_sha256:
            p.error('Controller SHA256 is required and must match the local binary')
    elif a.controller_sha256:
        p.error('--controller-sha256 requires --controller')
    # Refuse overwriting an earlier experiment before any remote action.
    evidence = a.output.open('x', encoding='utf-8')
    server = paramiko.SSHClient()
    server.load_system_host_keys()
    server.set_missing_host_key_policy(paramiko.RejectPolicy())
    bmc = paramiko.SSHClient()

    class Pin(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            if key.get_fingerprint().hex() != a.bmc_fingerprint:
                raise paramiko.SSHException('BMC identity changed')

    bmc.set_missing_host_key_policy(Pin())
    requested = False
    child = None

    def command(text):
        _, out, err = bmc.exec_command(text, timeout=20)
        result = out.read().decode().strip()
        error = err.read().decode()
        if out.channel.recv_exit_status():
            raise RuntimeError(error or text)
        return result

    def event(name, **fields):
        line = json.dumps({'event': name, 'time': time.time(), **fields})
        print(line, flush=True)
        evidence.write(line + '\n')
        evidence.flush()

    try:
        password = getpass.getpass('Isolated BMC password: ')
        server.connect(a.server, username=a.user, timeout=10)
        channel = server.get_transport().open_channel(
            'direct-tcpip', ('127.0.0.1', a.bmc_port), ('127.0.0.1', 0))
        bmc.connect('bmc', username='root', password=password, sock=channel,
                    look_for_keys=False, allow_agent=False, timeout=15)
        ready = command('busctl get-property xyz.openbmc_project.State.BMC '
                        '/xyz/openbmc_project/state/bmc0 xyz.openbmc_project.State.BMC CurrentBMCState')
        if not ready.endswith('.Ready"'):
            raise RuntimeError('BMC is not Ready')
        pgood_cmd = ('busctl get-property org.openbmc.control.Power '
                     '/org/openbmc/control/power0 org.openbmc.control.Power pgood')
        if command(pgood_cmd) != 'i 0':
            raise RuntimeError('Host must initially be powered off')
        if controller_data is not None:
            binary = '/tmp/fan-x86-' + a.controller_sha256
            with bmc.open_sftp() as sftp:
                try:
                    with sftp.open(binary) as stream:
                        if hashlib.sha256(stream.read()).hexdigest() != a.controller_sha256:
                            raise RuntimeError('Conflicting staged controller')
                except FileNotFoundError:
                    with sftp.open(binary, 'wx') as stream:
                        stream.write(controller_data)
                with sftp.open(binary) as stream:
                    if hashlib.sha256(stream.read()).hexdigest() != a.controller_sha256:
                        raise RuntimeError('Uploaded controller checksum mismatch')
            installer = Path(__file__).with_name('load-x86-fan-controller.sh').read_text()
            _, out, err = bmc.exec_command(
                'sh -s -- ' + shlex.quote(binary) + ' ' + shlex.quote(a.controller_sha256),
                timeout=60)
            # exec_command stdin is needed for the installer, not credentials.
            out.channel.sendall(installer.encode())
            out.channel.shutdown_write()
            message = out.read().decode()
            error = err.read().decode()
            if out.channel.recv_exit_status():
                raise RuntimeError(error or 'Controller installation failed')
            event('controller_ready', result=message.strip())
        controller = command('systemctl show phosphor-fan-control@0.service -p ExecStart --value')
        if '/tmp/fan-x86-' not in controller:
            raise RuntimeError('Load the explicit x86 controller before this experiment')
        command('systemctl is-active phosphor-fan-control@0.service')
        # Set before sending: an interrupted request may already have taken effect.
        requested = True
        command('busctl set-property xyz.openbmc_project.State.Host '
                '/xyz/openbmc_project/state/host0 xyz.openbmc_project.State.Host '
                'RequestedHostTransition s xyz.openbmc_project.State.Host.Transition.On')
        event('host_start_requested')
        forward = Path(__file__).with_name('forward-guest-load.py')
        # A trusted key pin is checked by the actual guest SSH handshake.
        from importlib.util import spec_from_file_location, module_from_spec
        spec = spec_from_file_location('forward_load', forward)
        helpers = module_from_spec(spec)
        spec.loader.exec_module(helpers)
        for attempt in range(60):
            guest = paramiko.SSHClient()

            class GuestPin(paramiko.MissingHostKeyPolicy):
                def missing_host_key(self, client, hostname, key):
                    if helpers.fingerprint(key) != a.guest_fingerprint:
                        raise paramiko.BadHostKeyException(hostname, key, key)

            guest.set_missing_host_key_policy(GuestPin())
            try:
                ch = server.get_transport().open_channel(
                    'direct-tcpip', ('127.0.0.1', a.guest_port), ('127.0.0.1', 0))
                guest.connect('guest', username=a.user, key_filename=a.key, sock=ch,
                              look_for_keys=False, allow_agent=False,
                              timeout=5, banner_timeout=5)
                _, out, _ = guest.exec_command('systemctl is-system-running', timeout=5)
                if out.read().decode().strip() == 'running':
                    break
            except paramiko.BadHostKeyException:
                raise
            except (OSError, paramiko.SSHException):
                pass
            finally:
                guest.close()
            if attempt == 59:
                raise RuntimeError('Guest did not reach running within bounded attempts')
            time.sleep(2)
        event('guest_running')
        args = [sys.executable, str(forward), '--server', a.server, '--user', a.user,
                '--guest-port', str(a.guest_port), '--guest-fingerprint', a.guest_fingerprint,
                '--key', a.key, '--state', a.state, '--cpu-cycle']
        child = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, encoding='utf-8')
        for line in child.stdout:
            print(line, end='', flush=True)
            evidence.write(line)
            evidence.flush()
        if child.wait() != 0:
            raise RuntimeError('Sampling experiment failed; inspect evidence')
        event('sampling_completed')
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        if requested:
            try:
                command('systemctl start --no-block obmc-host-shutdown@0.target')
                for _ in range(45):
                    if command(pgood_cmd) == 'i 0':
                        chassis = command('busctl get-property xyz.openbmc_project.State.Chassis '
                                          '/xyz/openbmc_project/state/chassis0 '
                                          'xyz.openbmc_project.State.Chassis CurrentPowerState')
                        if chassis.endswith('.Off"'):
                            event('host_off_confirmed')
                            break
                    time.sleep(2)
                else:
                    event('shutdown_not_confirmed', action='Inspect before any further experiment')
            except Exception as error:
                event('shutdown_error', error=str(error))
        bmc.close()
        server.close()
        evidence.close()
