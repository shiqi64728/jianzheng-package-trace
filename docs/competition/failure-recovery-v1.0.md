# Competition RC v1.0 故障恢复

## 原则

- 不删除未知文件，不写入 `runtime/mvp-v0.1` 或 `runtime/mvp-v0.2`。
- 先保留日志与失败响应，再执行可逆恢复。
- 不在比赛现场升级驱动、CUDA、PyTorch、Ultralytics、OpenCV 或 NumPy。

## 自检失败

| 现象 | 检查 | 恢复 |
|---|---|---|
| Python 不存在 | `Test-Path D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe` | 修复路径；不要切换到未知 Python |
| active model SHA 不符 | 对照注册表和 `2dd857...a97` | 停止演示，恢复已审计权重；不得忽略 |
| E 盘缺失 | `Test-Path E:\JianZhengData` | 接回 E 盘后重跑自检 |
| frontend/dist 缺失 | 本地 `node_modules` 是否存在 | `npm run build`，不执行联网安装 |
| 端口占用 | `Get-NetTCPConnection -LocalPort 8000` | 若不是 RC，改用 `-Port 8001`；不要强杀未知进程 |

## 服务启动失败

查看：

`E:\JianZhengData\runtime\competition-rc-v1.0\logs\uvicorn.stderr.log`

确认无残留 RC PID 后重新启动。若 PID 指向非 Uvicorn，停止脚本会拒绝操作，应人工核实进程，而不是删除 PID 后强杀。

## SQLite

数据库：`E:\JianZhengData\runtime\competition-rc-v1.0\jianzheng.db`，schema v3。迁移是 additive-only，v0.2 数据库只作为 SQLite backup API 的只读 bootstrap 来源。

出现 `database is locked` 时：先停止 RC，确认没有 Uvicorn/python 占用，再启动。禁止直接删除 `.db`、`.db-wal` 或 `.db-shm`。需要恢复时先复制整个 RC runtime 到新的时间戳目录，再在副本上诊断。

## 模型或 GPU

模型缺失/SHA 异常是停止条件。GPU 暂不可用但模型仍可 CPU 运行时，health/warmup 必须如实显示 runtime 与 fallback；性能指标不再沿用本次 GPU 报告。

## 报告或图像

- 报告 404：先确认案例已分析，再检查 `reports/<case_id>/report-rNNN.html`。
- 图片引用失效：检查报告 JSON 的 `image_path` 与 SHA；不要把图片复制进 Git。
- 工单/复核变更后报告使用同一 revision 路径刷新当前业务快照；append-only 真相仍在 SQLite 事件表。

## 视频

只接受 MP4，MIME 为 `video/mp4` 或 `application/octet-stream`。解码失败时保留源 SHA 和错误，不转述为“无异常”。视频支线失败不影响图像主线。

## 最后 fallback

若现场 UI 故障但 API 正常，可在浏览器打开 `/docs` 或直接展示已生成 Evidence Report；若 API 也不可恢复，展示已验证证据 JSON，明确它是赛前验证记录而非当前实时运行。
