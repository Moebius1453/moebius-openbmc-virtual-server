# 临时部署虚拟x86风扇策略

仅用于隔离热测试BMC。不是物理服务器风扇控制方案。原程序保留不覆盖；服务切换和回退均会短暂中断控制，必须在主机关机时经授权执行。

## 统一实验入口

完整步骤见[REAL-LOAD.md](REAL-LOAD.md)。run-thermal-cycle.py支持--controller及--controller-sha256，在真实PowerGood为0时将已校验程序放入BMC内存，调用装载入口后再启动主机。原有供应商程序与watchdog配置保留。load-x86-fan-controller.sh已在实际BMC验证重复调用不重启相同运行程序。

2026-11-04真实CPU三阶段实验通过升温提速、撤载减速和正常关机。下方2026-11-02记录保留为早期开发过程。

## 构建与变更范围

scripts/prepare-x86-fan-policy.py仅将occ_active_speed_changes中的两个OccActive=true前提改为真实PowerGood=1，其余事件保留。scripts/build-x86-fan-control.sh备份策略输入、使用既有recipe构建环境增量编译，退出时恢复输入文件。不会写OCC属性。

## 临时部署

产物可能含调试信息，必须先核大小及目标可用空间，不可直接塞入小容量BMC持久分区。当前实验使用/tmp内存盘；重启后程序及/run覆盖均消失。传输后必须比对SHA256。

在隔离BMC内，经授权创建/run/systemd/system/phosphor-fan-control@0.service.d/virtual-x86-test.conf，内容为：

```ini
[Service]
ExecStart=
ExecStart=/tmp/phosphor-fan-control-x86-c3087235 --control
```

随后daemon-reload并restart该服务。保留供应商unit及watchdog相关drop-in，不启停监测服务。程序路径中的哈希对应本次已验构建，其他构建需使用各自产物及准确路径。

回退时先正常关闭测试主机，确认PowerGood=0；单独授权后移除且仅移除此实验覆盖，daemon-reload并restart原服务。不要删除整个unit目录或供应商覆盖。

## 2026-11-02进度

临时控制器SHA256 c30872354c5162468436c3a08535588d97130a00f526dcc183b1d128229ae1f7，服务active/running。开机后低温目标转速从10500降至6360 RPM，实际转速有惯性地趋于6360，证明原生控制程序已实际降速。手动高负载升温提速及撤载回落验收仍在进行，完整闭环尚未宣布通过。

一次误将24 MiB未strip程序写入约1.8 MiB持久区失败，留下1.5 MiB残缺文件；用户授权精确删除后可写区恢复54%使用率。完整程序暂存于/tmp并校验成功。此事故说明部署入口必须先核空间；正式打包尚未实现。
