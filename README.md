# 件证

基于连续外观数字指纹的快递损伤异常节点定位与责任辅助认定系统。

## Competition MVP v0.1

- 环境：Windows、`jianzhen-training` Python 3.12、Node.js 24。
- 启动：`powershell -ExecutionPolicy Bypass -File scripts/demo/start-competition-mvp.ps1`
- 访问：[http://127.0.0.1:8000](http://127.0.0.1:8000)
- 历史 Demo：外部案例保留在 `E:\JianZhengData\runtime\mvp-v0.1\demo`。
- 主链路：Vue → FastAPI → D02/D03 Detector + ORB/RANSAC + absdiff →
  Sequence Locator → SQLite + HTML 报告。
- 代码目录：`ai/runtime`、`app/backend`、`frontend`、`scripts/demo`；模型、
  图片、数据库和运行报告均保存在 `E:\JianZhengData`，不提交 Git。

当前模型仅支持 D02 表面凹陷和 D03 纸箱破口；其他外观变化只输出
`UNKNOWN_VISUAL_CHANGE`。系统结果用于视觉异常定位与责任辅助判断，不直接构成
法律责任结论。

## Competition MVP v0.2

v0.2 在保留 v0.1 单图接口的同时，将案例升级为 `Node × Surface`：正式界面支持
`front / left / right / top`，数据层同时预留 `back / bottom / unknown`。相邻节点只会
比较同名表面；缺失单元格记录为 `PAIR_SURFACE_MISSING`，不会伪造比较或直接判异常。

- **Simple Mode**：每个节点只上传 `front`，兼容 v0.1 的快速现场演示。
- **Multi-Surface Mode**：显示 N1/N2/N3 × front/left/right/top 上传矩阵、触发表面和
  单元格状态。
- **机器能力**：D02/D03 由活动 YOLO26n 检测；其他可靠视觉变化写成
  `UNKNOWN_VISUAL_CHANGE`。
- **人工闭环**：D01/D04/D05、正常变化和不确定项通过 append-only `review_events`
  复核，不覆盖机器结果，并记录 supersede 链与 payload SHA-256。
- **Demo A/B/C/D**：外部演示包位于
  `E:\JianZhengData\runtime\mvp-v0.2\demo`；Demo C 只来自冻结公开 val，Demo D 是
  12 张合成多表面端到端案例。构建命令为
  `python scripts/demo/build_demo_cases.py`。

现场启动：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/demo/self-check-competition-mvp.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/demo/start-competition-mvp.ps1
```

停止：

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/demo/stop-competition-mvp.ps1
```

启动脚本不修改系统执行策略；`-ExecutionPolicy Bypass` 只作用于该次 PowerShell
进程。v0.2 使用独立的 `E:\JianZhengData\runtime\mvp-v0.2`，不会覆盖 v0.1。
