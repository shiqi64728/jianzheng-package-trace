# Competition RC v1.0 现场演示 Runbook

## 比赛前 10 分钟检查

1. 确认 E 盘已连接，电源处于高性能模式，关闭会占用 GPU 的无关程序。
2. 在 PowerShell 运行：

```powershell
Set-Location 'E:\Artificial-intelegence-training'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\demo\self-check-competition-mvp.ps1
```

3. 必须看到 Python、依赖、GPU、active model SHA、RC config、隔离数据库、frontend/dist 均 PASS。
4. 确认 `E:\JianZhengData\runtime\competition-rc-v1.0\demo\DEMO-D` 有 12 张图。
5. 禁止赛前临时执行 `pip install`、`npm install`、Git pull 或模型训练。

## 启动

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\demo\start-competition-mvp.ps1
```

打开 `http://127.0.0.1:8000`。看到 System Status 的 pipeline 为 `competition-rc-v1.0` 后开始。

## 建议演示顺序（主线）

1. **Dashboard**：强调所有指标来自 SQLite，不是 PPT 写死数字。
2. **New Case**：建立匿名案例，切换 Multi-Surface。
3. 上传 Demo D 的 N1/N2/N3 × front/left/right/top 12 张图。
4. 分析并进入 **Evidence**。
5. 展示首次异常区间 `N1_TO_N2` 与 trigger surface `left`。
6. 解释机器证据：此 Demo 为 `UNKNOWN_VISUAL_CHANGE`，不能伪称 D05 模型自动识别。
7. 进入 **Reviews**，由 `MEMBER-C` 人工确认 D05。
8. 回到 **Evidence**，展示 risk score 与九项可解释组成；强调不是法律责任结论。
9. 进入 **Work Orders**：创建 OPEN，变更 IN_REVIEW，最后 RESOLVE。
10. 打开 Evidence Report v1.0，展示时间线、风险分解、复核与工单历史。
11. 回到 **Dashboard**，展示计数变化。

自动化实测同一 HTTP 操作链耗时 1.943 秒；现场人工讲解可控制在 3 分钟内。

## Demo A/B/C/D 备用说明

- Demo A：合成单表面 N1→N2 变化。
- Demo B：公开 TAMPAR 对构造的模拟节点序列，不是真实物流轨迹。
- Demo C：公开 frozen val 的活动 D02/D03 检测演示。
- Demo D：合成四表面序列，left 在 N1→N2 变化，是主演示。

## 视频演示

进入 **Video Screening**，上传：

`E:\JianZhengData\runtime\competition-rc-v1.0\demo\SYNTHETIC-VIDEO-DEMO\damage-keyframe-screening.mp4`

展示采样帧、异常帧、D02/D03 检测和时间戳。固定表述是 `VIDEO_DAMAGE_KEYFRAME_SCREENING`；不得说成抛扔、违规动作或行为识别。

## 故障 fallback

1. 页面未开：先访问 `/api/health`；再按 failure-recovery 文档检查日志。
2. GPU warmup 失败：系统可惰性后备，但不要隐藏 warning；优先重启一次。
3. Demo D 上传错误：删除当前案例并新建，不覆盖已经存储的图片。
4. 视频编码异常：跳过视频支线，展示已经验证的外部 JSON 和关键帧；主 Demo 不受阻断。
5. 报告页面未开：使用返回的绝对 `report_path` 本地打开；不得现场修改数据库。

## 停止

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\demo\stop-competition-mvp.ps1
```

停止脚本只会终止 PID 文件指向且命令行匹配件证 Uvicorn 的进程。
