FROM debian:13

RUN printf '%s\n' \
        'Types: deb' \
        'URIs: http://mirrors.tuna.tsinghua.edu.cn/debian' \
        'Suites: trixie trixie-updates' \
        'Components: main' \
        'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
        '' \
        'Types: deb' \
        'URIs: http://mirrors.tuna.tsinghua.edu.cn/debian-security' \
        'Suites: trixie-security' \
        'Components: main' \
        'Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg' \
        > /etc/apt/sources.list.d/debian.sources \
    && printf '%s\n' \
        'Acquire::http::Timeout "30";' \
        'Acquire::https::Timeout "30";' \
        'Acquire::Retries "2";' \
        > /etc/apt/apt.conf.d/80-download-timeout \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        python3 \
        qemu-system-arm \
        qemu-system-x86 \
        qemu-utils \
        tini \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /lab
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["qemu-system-arm", "--version"]
