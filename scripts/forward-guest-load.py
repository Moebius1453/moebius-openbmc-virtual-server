#!/usr/bin/env python3
"""Forward a bounded guest CPU sample stream through authenticated SSH."""
import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import posixpath
import shlex
import time

import paramiko


def fingerprint(key):
    return 'SHA256:' + base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--server', required=True)
    p.add_argument('--user', required=True)
    p.add_argument('--guest-port', type=int, required=True)
    p.add_argument('--guest-fingerprint', required=True)
    p.add_argument('--key', required=True)
    p.add_argument('--state', required=True)
    p.add_argument('--samples', type=int, default=120)
    p.add_argument('--cpu-cycle', action='store_true',
                   help='Explicitly run a bounded 360-second idle/load/cooldown guest experiment')
    a = p.parse_args()
    if not 1 <= a.samples <= 600:
        p.error('samples must be between 1 and 600')
    server = paramiko.SSHClient()
    server.load_system_host_keys()
    server.set_missing_host_key_policy(paramiko.RejectPolicy())
    guest = paramiko.SSHClient()

    class PinnedKey(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            if fingerprint(key) != a.guest_fingerprint:
                raise paramiko.SSHException('Guest host key does not match pin')

    guest.set_missing_host_key_policy(PinnedKey())
    try:
        server.connect(a.server, username=a.user, timeout=10)
        channel = server.get_transport().open_channel(
            'direct-tcpip', ('127.0.0.1', a.guest_port), ('127.0.0.1', 0))
        guest.connect('guest', username=a.user, sock=channel,
                      key_filename=a.key, look_for_keys=False, allow_agent=False,
                      timeout=15, banner_timeout=20)
        filename = 'guest-cpu-cycle.py' if a.cpu_cycle else 'sample-guest-load.py'
        sampler = Path(__file__).with_name(filename).read_text()
        command = 'python3 -' if a.cpu_cycle else f'python3 - --samples {a.samples}'
        stdin, stdout, stderr = guest.exec_command(command, timeout=15)
        stdin.write(sampler)
        stdin.flush()
        stdin.channel.shutdown_write()
        with server.open_sftp() as sftp:
            destination = posixpath.join(a.state, 'thermal-load.json')
            # Explicit switch from manual input, preserving the previous document.
            with sftp.open(destination) as stream:
                original = stream.read()
            if not isinstance(json.loads(original), dict):
                raise ValueError('Existing load input is not an object')
            backup = destination + '.before-guest-' + str(time.time_ns())
            with sftp.open(backup, 'wx') as stream:
                stream.write(original)
            for line in stdout:
                record = json.loads(line)
                value = record.get('load')
                if (record.get('source') != 'guest-proc-stat'
                        or isinstance(value, bool)
                        or not isinstance(value, (float, int))
                        or not math.isfinite(value) or not 0 <= value <= 1):
                    raise ValueError('Invalid guest CPU sample')
                # Timestamp in the consumer's host clock domain, not Windows.
                temporary = destination + '.sample-' + str(time.time_ns())
                with sftp.open(temporary, 'wx') as stream:
                    stream.write(json.dumps(record))
                publish = (
                    'import json,os,sys,time; '
                    'p=sys.argv[1]; d=json.load(open(p)); '
                    'd["received_at"]=time.time(); '
                    'f=open(p,"w"); json.dump(d,f); f.close(); '
                    'os.replace(p,sys.argv[2])')
                _, published, errors = server.exec_command(
                    'python3 -c ' + shlex.quote(publish) + ' '
                    + shlex.quote(temporary) + ' ' + shlex.quote(destination),
                    timeout=10)
                if published.channel.recv_exit_status():
                    raise RuntimeError(errors.read().decode())
                print(json.dumps(record), flush=True)
        status = stdout.channel.recv_exit_status()
        if status:
            raise RuntimeError(stderr.read().decode())
    finally:
        guest.close()
        server.close()
