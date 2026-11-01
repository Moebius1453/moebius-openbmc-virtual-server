PREMIRRORS:prepend = "\
https?://ftp.gnu.org/gnu/ https://mirrors.tuna.tsinghua.edu.cn/gnu/ \n \
https?://ftpmirror.gnu.org/ https://mirrors.tuna.tsinghua.edu.cn/gnu/ \n \
"
FETCHCMD_wget = "/usr/bin/env wget -t 2 -T 30 --passive-ftp --prefer-family=IPv4"
