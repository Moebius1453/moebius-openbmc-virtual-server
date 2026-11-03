# 实际负载与控制器镜像载荷

当前是待验实现，不是已部署成果。手动负载热闭环已通过；真实CPU仅完成单独五次采样。完整真实负载升降温测试未完成。

## 仓库入口

- scripts/sample-guest-load.py：客体读取/proc/stat，1秒一个样本，最多600次。
- scripts/forward-guest-load.py：在本机运行，依赖paramiko。宿主使用已有known_hosts，客体使用明确SHA256密钥指纹，私钥只留本机。连接后先备份原负载文档，再以临时文件加原子替换发布样本；默认120秒，最长600秒，退出关闭连接。
- src/thermal_bridge.py：区分manual与guest-proc-stat；真实样本超过5秒按保守满负载发热，不把断连解释为空闲。缺失或无效JSON文档同样保守处理。其他字段验证仍可能报告thermal_error，全面失效处理尚未验。
- scripts/load-x86-fan-controller.sh：在BMC内执行，检查SHA256、BMC Ready及pgood0，拒绝已知临时覆盖冲突；新建/run覆盖并重启原生控制服务。只有获得服务中断授权后才运行。
- Dockerfile.thermal-runtime：从既有thermal镜像继承，外部fan-x86构建上下文携带strip程序及校验清单。不会将程序写入BMC rwfs。

## 实际负载转发

在本机项目根使用下列命令，必须先确认客体SSH指纹来自可信串口或既有记录。示例指纹为本次隔离测试客体首次采样观察值，尚需独立串口核对，不作为可信首次配对依据。

```powershell
python scripts/forward-guest-load.py --server 10.107.230.205 --user moebius --guest-port 2281 --guest-fingerprint SHA256:yRynyK8UxhDUvwy6IGfn/VWsBJ2shyAU5B2NyJd/sB0 --key C:/Users/Moebius/.ssh/id_ed25519 --state /data/openbmc-virtual-server/thermal-state-20261102 --samples 120
```

该命令会将手动输入切换为真实采样；原文档保留时间戳备份。结束后真实输入会过期，运行新版热桥的主机将按保守满负载处理。不要在旧镜像上将其当成已经实现的超时策略。

## 控制器装载和恢复边界

镜像携带只保证产物来源可重复，不等于BMC重启后自动装载。当前尚无通过验收的自动SSH装载编排。BMC内/tmp程序及/run覆盖会丢失，需重新传输校验并在主机关机时调用装载脚本。发现virtual-x86-test.conf时必须先经授权迁移，不自动删覆盖。

管理器对BMC RESET标记清除热设备路径，下次重发现重新启用external-fan-feedback；QEMU进程异常退出重建路径尚需补充同样恢复。目标初始值及新字段迁移仍未验。

## 后续验收

先构建runtime镜像，不替换在线实例。获得独立测试实例切换授权后部署；核串口指纹，做真实空闲、有限两vCPU负载、撤载、超时和恢复测试。结束正常关机并核真实退出。新增脚本及Dockerfile未运行测试，不宣称通过。不得关闭测速保护或伪造OCC。
