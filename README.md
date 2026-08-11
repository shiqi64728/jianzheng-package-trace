# 件证

基于连续外观数字指纹的快递损伤异常节点定位与责任辅助认定系统。

## Competition MVP v0.1

- 环境：Windows、`jianzhen-training` Python 3.12、Node.js 24。
- 启动：`powershell -ExecutionPolicy Bypass -File scripts/demo/start-competition-mvp.ps1`
- 访问：[http://127.0.0.1:8000](http://127.0.0.1:8000)
- Demo：运行 `python scripts/demo/build_demo_cases.py`，外部案例位于
  `E:\JianZhengData\runtime\mvp-v0.1\demo`。
- 主链路：Vue → FastAPI → D02/D03 Detector + ORB/RANSAC + absdiff →
  Sequence Locator → SQLite + HTML 报告。
- 代码目录：`ai/runtime`、`app/backend`、`frontend`、`scripts/demo`；模型、
  图片、数据库和运行报告均保存在 `E:\JianZhengData`，不提交 Git。

当前模型仅支持 D02 表面凹陷和 D03 纸箱破口；其他外观变化只输出
`UNKNOWN_VISUAL_CHANGE`。系统结果用于视觉异常定位与责任辅助判断，不直接构成
法律责任结论。
