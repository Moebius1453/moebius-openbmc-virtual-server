# 实际负载与统一实验入口

Debian 的真实 CPU 使用率通过 SSH 采样进入环境模型，OpenBMC 根据虚拟温度器件的读数调节风扇。完整实验由本机入口组织，使用私钥认证，密钥留在本机。

## 准备

本机使用 Python 3 和 Paramiko，宿主使用 Linux、Docker 与 KVM。先启动热模型运行容器，确认 BMC 的 SSH 指纹和客体指纹。运行配置包括宿主地址、用户名、BMC 与客体端口、宿主 state 绝对路径及本机私钥位置。

在本机设置以下环境变量用于示例：LAB_SERVER、LAB_USER、LAB_BMC_PIN、LAB_GUEST_PIN、LAB_KEY、LAB_STATE。地址与路径取当前部署的实际值。输出文件位于当前目录，已存在时入口拒绝覆盖。

## 三种操作模式

同一入口使用--mode选择操作，默认cycle：

| 模式 | 行为 |
|---|---|
| check | 检查BMC Ready、主机关机和x86控制器运行，不上传、不请求开机 |
| stage | 校验并按需装载--controller指定程序，完成后退出，不请求开机 |
| cycle | 按需装载后完成真实CPU三阶段实验与关机收尾 |

在下方完整命令中追加--mode check即可短检查；stage需同时传入--controller和--controller-sha256。各次使用不同--output文件。

2026-11-04隔离BMC实测stage两次及check一次成功，同哈希现有程序保持相同PID和启动时间，无服务重启。入口按实际运行路径核对哈希，兼容旧短文件名。不同内容的覆盖继续拒绝。

## 完整实验

在仓库根目录的 PowerShell 中执行：

```powershell
python scripts/run-thermal-cycle.py --server $env:LAB_SERVER --user $env:LAB_USER --bmc-fingerprint $env:LAB_BMC_PIN --guest-fingerprint $env:LAB_GUEST_PIN --key $env:LAB_KEY --state $env:LAB_STATE --output ./thermal-cycle.jsonl
```

入口询问 BMC 密码，核对 Ready、PowerGood 和控制器，启动主机并等待 Debian running，然后运行三阶段实验：

| 阶段 | 时间 | 行为 |
|---|---|---|
| idle | 120秒 | 采样空闲 CPU，让模型和风扇进入基线 |
| load | 120秒 | 客体内两个限时 CPU 工作进程 |
| cooldown | 120秒 | 退出工作进程，持续记录回落 |

每条 CPU 记录包含phase、elapsed_seconds和total_seconds。结束打印sampling_completed，正常关机并核对PowerGood与机箱Off后打印host_off_confirmed。异常时执行相同关机收尾；shutdown_error或shutdown_not_confirmed表示需要检查现场，不强制撤电。

本机证据包含CPU样本和生命周期事件；对应温度、目标转速与实际测速取运行容器的thermal_sample日志。

## 在同一入口装载控制器

将对应镜像的strip控制器导出到本机，并取得SHA256。在完整实验命令后添加：

```powershell
--controller ./phosphor-fan-control.stripped --controller-sha256 $env:LAB_CONTROLLER_SHA256
```

这两个参数启用开机前装载：校验本机程序，传入BMC /tmp，重新读取并核对上传哈希，调用仓库装载脚本，再启动实验。装载脚本要求Ready和pgood0，保留供应商程序及watchdog配置；遇到不同内容的覆盖拒绝继续。相同程序已经运行时不重启服务。

这一入口按需装载，不是宿主开机常驻服务。BMC重启会清除/tmp程序及/run覆盖，下一次实验重新传入。可选装载分支的本次代码检查包含参数解析；完整六分钟验收对应的是已有控制器分支。

## 只采样

```powershell
python scripts/forward-guest-load.py --server $env:LAB_SERVER --user $env:LAB_USER --guest-port 2281 --guest-fingerprint $env:LAB_GUEST_PIN --key $env:LAB_KEY --state $env:LAB_STATE --samples 120
```

发布前备份原输入文档，服务器生成received_at并原子替换thermal-load.json，避免Windows时钟参与过期判断。样本超过5秒，热桥标注stale-guest-conservative并按满负载计算发热；这不是客体真实CPU使用率，分析结果时要分开。

## 实验结果

2026-11-04完成三阶段各120条真实CPU样本：平均利用率0.17%、99.99%、0.18%。温度上升后BMC将目标从约5000提高到7200 RPM，实际测速逐渐跟随；撤载后温度回落至约36.5度，目标降至6600。最后ACPI关机、客体退出0、PowerGood归零，入口确认机箱Off。

采样回归覆盖CPU时间重复计数、计数回退、利用率计算和非法样本拒绝。故障保护、BMC重启恢复作为独立实验记录，不由负载试验代替。
