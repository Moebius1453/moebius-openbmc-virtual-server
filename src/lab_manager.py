import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

RUNTIME = Path('/run/lab')
STATE = Path('/lab/state')
GPIO_PATH = '/machine/soc/gpio'
stopping = False


class QMP:
    def __init__(self, path):
        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.settimeout(3)
        try:
            self.sock.connect(str(path))
            self.file = self.sock.makefile('rwb', buffering=0)
            self.read()
            self.call('qmp_capabilities')
        except Exception:
            self.sock.close()
            raise

    def read(self):
        line = self.file.readline()
        if not line:
            raise ConnectionError('QMP disconnected')
        return json.loads(line)

    def call(self, command, **arguments):
        message = {'execute': command}
        if arguments:
            message['arguments'] = arguments
        self.file.write((json.dumps(message) + '\n').encode())
        while True:
            response = self.read()
            if 'error' in response:
                raise RuntimeError(str(response['error']))
            if 'return' in response:
                return response['return']

    def close(self):
        self.file.close()
        self.sock.close()


def log(event, **fields):
    print(json.dumps({'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                      'event': event, **fields}), flush=True)


def handle_signal(signum, frame):
    global stopping
    stopping = True


def start_bmc():
    path = RUNTIME / 'bmc.qmp'
    path.unlink(missing_ok=True)
    command = [
        'qemu-system-arm', '-M', 'witherspoon-bmc',
        '-drive', 'file=/lab/state/bmc-2.18-rw3-test.mtd,if=mtd,format=raw',
        '-nic', 'user,hostfwd=tcp:0.0.0.0:2222-:22,hostfwd=tcp:0.0.0.0:2443-:443',
        '-qmp', f'unix:{path},server=on,wait=off',
        '-display', 'none', '-monitor', 'none',
        '-serial', 'file:/lab/state/bmc-integration-console.log',
    ]
    process = subprocess.Popen(command)
    log('bmc_started', pid=process.pid)
    return process


def start_host():
    path = RUNTIME / 'host.qmp'
    path.unlink(missing_ok=True)
    command = [
        'qemu-system-x86_64', '-name', 'virtual-host',
        '-machine', 'q35,accel=kvm', '-cpu', 'host', '-smp', '2', '-m', '2048',
        '-drive', 'file=/lab/state/debian/host.qcow2,if=virtio,format=qcow2',
        '-drive', 'file=/lab/state/debian/seed.iso,media=cdrom,readonly=on',
        '-nic', 'user,model=virtio-net-pci,hostfwd=tcp:0.0.0.0:2223-:22',
        '-qmp', f'unix:{path},server=on,wait=off',
        '-display', 'none', '-monitor', 'none',
        '-serial', 'file:/lab/state/debian/console.log',
    ]
    process = subprocess.Popen(command)
    log('host_started', pid=process.pid)
    return process


def end_process(process, qmp_path):
    if process is None or process.poll() is not None:
        return
    try:
        client = QMP(qmp_path)
        try:
            client.call('quit')
        finally:
            client.close()
    except (OSError, ValueError, RuntimeError):
        pass
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main():
    RUNTIME.mkdir(exist_ok=True)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, handle_signal)
    bmc = start_bmc()
    host = None
    client = None
    last_request = False
    last_good = None
    previous_reset = None
    error_since = None
    try:
        while not stopping:
            if host is not None and host.poll() is not None:
                log('host_exited', code=host.returncode)
                host = None
            if bmc.poll() is not None:
                log('bmc_exited', code=bmc.returncode, host_running=host is not None)
                if client is not None:
                    client.close()
                    client = None
                time.sleep(1)
                bmc = start_bmc()
                last_good = None
            try:
                if client is None:
                    client = QMP(RUNTIME / 'bmc.qmp')
                    last_good = None
                request = client.call('qom-get', path=GPIO_PATH, property='gpioD1')
                reset = client.call('qom-get', path=GPIO_PATH, property='gpioA1')
                if request and not last_request and host is None:
                    host = start_host()
                if not request and host is not None:
                    log('host_power_removed')
                    end_process(host, RUNTIME / 'host.qmp')
                    host = None
                if host is not None and previous_reset is True and reset is False:
                    host_qmp = QMP(RUNTIME / 'host.qmp')
                    try:
                        host_qmp.call('system_reset')
                    finally:
                        host_qmp.close()
                    log('host_reset')
                good = False
                if host is not None and host.poll() is None:
                    host_qmp = QMP(RUNTIME / 'host.qmp')
                    try:
                        good = host_qmp.call('query-status')['running']
                    finally:
                        host_qmp.close()
                if good != last_good:
                    client.call('qom-set', path=GPIO_PATH, property='gpioD2', value=good)
                    log('power_good', value=good)
                    last_good = good
                last_request = request
                previous_reset = reset
                error_since = None
            except (OSError, ValueError, RuntimeError) as exc:
                if error_since is None:
                    log('bridge_connection_error', error=str(exc))
                    error_since = time.monotonic()
                if client is not None:
                    client.close()
                    client = None
            time.sleep(0.25)
    finally:
        if host is not None and host.poll() is None:
            try:
                host_qmp = QMP(RUNTIME / 'host.qmp')
                try:
                    host_qmp.call('system_powerdown')
                finally:
                    host_qmp.close()
                host.wait(timeout=60)
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
                log('host_shutdown_timeout')
            end_process(host, RUNTIME / 'host.qmp')
        if client is not None:
            client.close()
        end_process(bmc, RUNTIME / 'bmc.qmp')
        log('lab_stopped')


if __name__ == '__main__':
    main()
