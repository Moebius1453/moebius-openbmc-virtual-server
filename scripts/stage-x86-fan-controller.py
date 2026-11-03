#!/usr/bin/env python3
"""Stage an image-exported controller on an explicitly pinned isolated BMC."""
import argparse
import hashlib
from pathlib import Path
import shlex
import sys

import paramiko


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--server', required=True)
    p.add_argument('--user', required=True)
    p.add_argument('--port', type=int, required=True)
    p.add_argument('--fingerprint', required=True)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--password-file', type=Path, required=True)
    a = p.parse_args()
    data = a.binary.read_bytes()
    if hashlib.sha256(data).hexdigest() != a.sha256:
        raise SystemExit('Controller checksum mismatch')
    password = a.password_file.read_text().strip()
    server = paramiko.SSHClient()
    server.load_system_host_keys()
    server.set_missing_host_key_policy(paramiko.RejectPolicy())
    bmc = paramiko.SSHClient()

    class Pin(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            if key.get_fingerprint().hex() != a.fingerprint:
                raise paramiko.SSHException('BMC key mismatch')

    bmc.set_missing_host_key_policy(Pin())
    try:
        server.connect(a.server, username=a.user, timeout=10)
        ch = server.get_transport().open_channel(
            'direct-tcpip', ('127.0.0.1', a.port), ('127.0.0.1', 0))
        bmc.connect('bmc', username='root', password=password, sock=ch,
                    look_for_keys=False, allow_agent=False, timeout=15)
        # The shell installer refuses running hosts and conflicting overrides.
        with bmc.open_sftp() as sftp:
            binary = '/tmp/fan-x86-' + a.sha256
            try:
                with sftp.open(binary) as f:
                    if hashlib.sha256(f.read()).hexdigest() != a.sha256:
                        raise RuntimeError('Conflicting staged binary')
            except FileNotFoundError:
                with sftp.open(binary, 'wx') as f:
                    f.write(data)
            installer = Path(__file__).with_name('load-x86-fan-controller.sh').read_text()
        stdin, stdout, stderr = bmc.exec_command(
            'sh -s -- ' + shlex.quote(binary) + ' ' + shlex.quote(a.sha256), timeout=60)
        stdin.write(installer)
        stdin.flush()
        stdin.channel.shutdown_write()
        print(stdout.read().decode())
        error = stderr.read().decode()
        status = stdout.channel.recv_exit_status()
        if status:
            print(error, file=sys.stderr)
            raise SystemExit(status)
    finally:
        bmc.close()
        server.close()
