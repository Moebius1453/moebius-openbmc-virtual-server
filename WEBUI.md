# Web UI 构建与重新装载

bmcweb 提供 HTTPS 和 Redfish，webui-vue 提供浏览器界面。Witherspoon 配置通过 phosphor-no-webui 禁用了前端包依赖，因此 HTTPS 可达不代表固件带有登录页。

## 构建前端

在已有构建容器中运行 scripts/build-webui.sh，要求 OpenBMC 源码位于 /work/openbmc，版本与脚本固定提交一致。脚本直接构建 webui-vue，不更换运行 flash；首次会构建 Node.js 等宿主工具，可能耗时数小时。后续复用下载和构建缓存，不要清空缓存来重复尝试。

产物位于 /work/artifacts/webui/build-XXXXXXXX/webui-www.tar.gz，校验记录为同目录 SHA256SUMS。把归档取回操作端，保留在仓库外。首页可以是 index.<hash>.html.gz；bmcweb 支持将它映射为目录首页。

## 装载到运行 BMC

操作端需要 Python 和 paramiko，以及已记录于 known_hosts 的宿主 SSH 密钥。本机私钥不复制到 BMC。以下 PowerShell 命令从仓库根目录运行；LAB_SERVER、LAB_USER、LAB_BMC_PIN、LAB_WEBUI_ARCHIVE、LAB_WEBUI_SHA256 由使用者设置。BMC 指纹采用不带冒号的 MD5 十六进制格式，与既有装载脚本一致。

```powershell
python scripts/stage-webui.py --server $env:LAB_SERVER --user $env:LAB_USER --port 2280 --fingerprint $env:LAB_BMC_PIN --archive $env:LAB_WEBUI_ARCHIVE --sha256 $env:LAB_WEBUI_SHA256
```

脚本交互询问 BMC 密码，也可通过 --password-file 读取受保护的本地文件。不要把密码文件放入仓库。

首次装载会：

1. 校验归档 SHA256，拒绝路径穿越、链接、重复文件及超大解包内容。
2. 在 /tmp 新建目录，复制原网页资源并添加前端，不覆盖 /usr/share/www。
3. 在 /run/systemd/system/bmcweb.service.d/virtual-webui.conf 写入服务级 BindReadOnlyPaths 映射。
4. 重载 systemd 配置，仅重启 bmcweb。HTTPS / Redfish 短暂断开，BMC 和 Debian 不重启。

相同前端已装载时，检查配置、文件、服务状态以及服务进程实际看到的文件，返回 Frontend already active; no restart。发现不同版本或未知覆盖配置时停止，不自动替换。程序超时不表示重启没执行；先查服务与 HTTPS，不立即重复执行。

## BMC 重启后

/tmp 与 /run 中的部署会消失。BMC 恢复 SSH 后重新运行相同装载命令即可；此步骤与风扇控制器 stage 独立。没有开机自动装载服务，不需要为装载网页启动 CPU 负载实验。

## 访问和验收

在操作端建立 SSH 隧道，宿主 BMC HTTPS 端口按实际部署替换：

```powershell
ssh -N -o ExitOnForwardFailure=yes -L 8443:127.0.0.1:2480 "$env:LAB_USER@$env:LAB_SERVER"
```

浏览器访问 https://127.0.0.1:8443，使用 BMC 账户。先确认实验地址，再处理自签证书提示。

在 Linux 宿主可检查 HTML 响应：

```bash
curl -ksS --compressed -H 'Accept: text/html' -D - https://127.0.0.1:2480/
```

验收包括首页 HTTP 200、引用的 JS/CSS HTTP 200，以及浏览器实际登录。当前部署已通过这三项，统一装载脚本的已装载无重启分支已实际执行；该脚本的首次装载及重启后分支仍需单独执行验收，首次现场部署采用同样目录映射方法。

## 回退

先检查覆盖文件是否为本脚本创建，并保存内容和部署目录。确认后移走这一份 virtual-webui.conf，再 daemon-reload 并重启 bmcweb，即恢复原网页目录。不要删除整个服务覆盖目录或其他服务文件。回退会撤下图形前端，不改变 Redfish 固件功能。
