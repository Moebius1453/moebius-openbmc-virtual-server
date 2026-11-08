#!/usr/bin/env python3
"""校验并在 BMC 内存中装载网页，不改写原始网页目录。"""
import argparse
import getpass
import hashlib
import io
from pathlib import Path, PurePosixPath
import re
import shlex
import tarfile

import paramiko


def archive_files(data):
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or not (member.isfile() or member.isdir()):
                raise ValueError('Unsafe archive member')
            if member.isfile():
                if member.size > 16 * 1024 * 1024:
                    raise ValueError('Archive member too large')
                name = str(path)
                if name in files:
                    raise ValueError('Duplicate archive member')
                files[name] = archive.extractfile(member).read()
                if sum(map(len, files.values())) > 32 * 1024 * 1024:
                    raise ValueError('Frontend too large')
    if not any(re.fullmatch(r'index(?:\.[a-fA-F0-9]+)?\.html(?:\.gz)?', n) for n in files):
        raise ValueError('No frontend index')
    return files


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--server', required=True)
    p.add_argument('--user', required=True)
    p.add_argument('--port', type=int, default=2280)
    p.add_argument('--fingerprint', required=True, help='BMC SSH MD5 fingerprint, without colons')
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--password-file', type=Path)
    a = p.parse_args()
    data = a.archive.read_bytes()
    if hashlib.sha256(data).hexdigest() != a.sha256:
        raise ValueError('Archive checksum mismatch')
    files = archive_files(data)
    password = a.password_file.read_text().strip() if a.password_file else getpass.getpass('BMC password: ')
    server = paramiko.SSHClient()
    server.load_system_host_keys()
    server.set_missing_host_key_policy(paramiko.RejectPolicy())
    bmc = paramiko.SSHClient()

    class Pin(paramiko.MissingHostKeyPolicy):
        def missing_host_key(self, client, hostname, key):
            if key.get_fingerprint().hex() != a.fingerprint:
                raise paramiko.SSHException('BMC key mismatch')

    bmc.set_missing_host_key_policy(Pin())

    def run(command):
        stdin, stdout, stderr = bmc.exec_command(command, timeout=120)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        if stdout.channel.recv_exit_status():
            raise RuntimeError(error or output or command)
        return output

    try:
        server.connect(a.server, username=a.user, timeout=10)
        channel = server.get_transport().open_channel('direct-tcpip', ('127.0.0.1', a.port), ('127.0.0.1', 0))
        bmc.connect('bmc', username='root', password=password, sock=channel,
                    look_for_keys=False, allow_agent=False, timeout=15)
        with bmc.open_sftp() as sftp:
            override = '/run/systemd/system/bmcweb.service.d/virtual-webui.conf'
            try:
                with sftp.open(override) as f:
                    config = f.read().decode()
            except FileNotFoundError:
                config = None
            if config is not None:
                match = re.fullmatch(r'\[Service\]\nBindReadOnlyPaths=(/tmp/virtual-webui-[A-Za-z0-9_-]+/www):/usr/share/www\n', config)
                if not match:
                    raise RuntimeError('Unknown existing override; left unchanged')
                root = match[1]
                for name, content in files.items():
                    with sftp.open(root + '/' + name) as f:
                        if f.read() != content:
                            raise RuntimeError('Different deployed frontend; left unchanged')
                pid = run('systemctl show bmcweb.service -p MainPID --value')
                active = run('systemctl is-active bmcweb.service')
                if active == 'active' and pid.isdigit() and pid != '0':
                    # 检查进程实际看到的目录，而不只检查尚未生效的配置。
                    for name, content in files.items():
                        with sftp.open('/proc/' + pid + '/root/usr/share/www/' + name) as f:
                            if f.read() != content:
                                raise RuntimeError('Service view differs; inspect before restarting')
                    print('Frontend already active; no restart')
                    return
                raise RuntimeError('Existing deployment is not active; inspect service before restarting')
            root = run('mktemp -d /tmp/virtual-webui-XXXXXXXX')
            if not re.fullmatch(r'/tmp/virtual-webui-[A-Za-z0-9_-]+', root):
                raise RuntimeError('Unexpected temporary directory')
            run('mkdir ' + shlex.quote(root + '/www') + ' && cp -a /usr/share/www/. ' + shlex.quote(root + '/www/') + ' && chmod 755 ' + shlex.quote(root))
            for name, content in files.items():
                destination = root + '/www/' + name
                run('mkdir -p ' + shlex.quote(str(PurePosixPath(destination).parent)))
                with sftp.open(destination, 'wx') as f:
                    f.write(content)
                sftp.chmod(destination, 0o644)
            run('mkdir -p /run/systemd/system/bmcweb.service.d')
            with sftp.open(override, 'wx') as f:
                f.write('[Service]\nBindReadOnlyPaths=' + root + '/www:/usr/share/www\n')
            print('Staged frontend: ' + root, flush=True)
            run('systemctl daemon-reload && systemctl restart bmcweb.service && systemctl is-active bmcweb.service')
            print('Frontend staged; verify HTTPS and browser login')
    finally:
        bmc.close()
        server.close()


if __name__ == '__main__':
    main()
