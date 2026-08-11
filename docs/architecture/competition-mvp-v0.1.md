# 件证 Competition MVP v0.1 架构

## 1. 项目痛点

快递包裹在多个交接节点被重复拍摄，但单张图片只能说明“现在是否异常”，不能说明
“异常首次出现在哪个相邻区间”。MVP把已知损伤检测、跨拍摄配准、未知变化检测和
时序规则组合为可解释证据链。

## 2. 系统数据流

```text
N1/N2/N3上传 → D02/D03检测 → 相邻图像配准 → 变化区域 → 首次异常区间
            → 图片/模型SHA-256 → SQLite → API → Vue与HTML报告
```

所有案例运行数据位于 `E:\JianZhengData\runtime\mvp-v0.1`，不写入训练数据或
Git 工作树。

## 3. AI 检测

活动模型由冻结 test 的 mAP50-95 单指标选择。960 candidate 为 `0.0755004514`，
高于 640 baseline 的 `0.0714805047`，因此活动模型为
`d02-d03-yolo26n-imgsz960-v0.1`。统一 `Detector.predict(image)` 接口屏蔽
Ultralytics 后端差异，只允许输出 D02 表面凹陷和 D03 纸箱破口。

## 4. 图像配准

`ImageRegistrar` 使用 ORB → BFMatcher KNN ratio → RANSAC Homography →
`warpPerspective`。输出关键点、匹配点、内点、重叠率、矩阵、状态和警告。
状态只有 `SUCCESS`、`LOW_CONFIDENCE`、`FAILED`；失败时允许 resize-only
fallback，但明确降低证据置信度，不伪造可靠配准。

## 5. 变化检测

配准后执行灰度化、Gaussian blur、`absdiff`、阈值、形态学开闭和轮廓聚合。
区域未与 D02/D03 框重叠时统一标为 `UNKNOWN_VISUAL_CHANGE`，绝不自动猜测
D01/D04/D05。参数集中在 `configs/runtime/change-detection-v0.1.json`；这些是
比赛 MVP 和合成回归默认值，尚未经过大规模真实物流数据校准。

## 6. 连续节点定位

`locate_first_abnormality` 支持 N1...Nn，MVP API 至少要求连续 N1/N2/N3。
规则覆盖首节点已有异常、N1→N2 首次异常、N2→N3 首次异常、全正常、仅未知变化和
配准失败人工复核。节点状态为 `NORMAL`、`KNOWN_DAMAGE`、`UNKNOWN_CHANGE`、
`KNOWN_DAMAGE_AND_CHANGE` 或 `INSUFFICIENT_EVIDENCE`。

## 7. 外观数字指纹定义

`appearance_fingerprint_v0.1` 包含原图 SHA-256、尺寸、ORB 关键点数量、规范化
descriptor bytes 的 SHA-256 和已知损伤摘要。descriptor digest 是工程级版本
标识，不是稳定的跨拍摄视觉身份 hash，也不宣称具备密码学视觉唯一身份能力。

## 8. 证据固化

每次分析保留原图 SHA-256、模型版本与哈希、detections、配准与变化指标、首次异常
区间、E0/E1/E2/E3 技术证据等级、警告、创建时间和 pipeline version。JSON/HTML
报告固定声明：本报告用于视觉异常定位与责任辅助分析，不能单独作为法律责任认定
结论。

## 9. API

FastAPI 提供健康、模型信息、单图检测、双图变化、案例创建、节点上传、分析、案例
详情、报告和案例列表共 10 类接口。上传只允许 JPG/JPEG/PNG/WEBP，并同时检查
大小、后缀、MIME 和 OpenCV 解码；文件名由服务端生成，避免 `../`、盘符、UNC、
绝对路径和覆盖。

## 10. SQLite

标准库 `sqlite3` 建立 `cases`、`case_nodes`、`detections`、`pair_changes`、
`analysis_results`、`reports` 六表。案例默认匿名，不设计姓名、手机号、地址或真实
运单号字段。

## 11. 前端

Vue 3 + Vite 单页采用三栏答辩布局：匿名案例、N1/N2/N3 上传、技术结论。节点卡片
显示原图、检测框、状态、数量和最高置信度；变化区显示配准状态、变化分数、面积比
和区域数。API 基址只在 `frontend/src/api.js` 通过 `VITE_API_BASE` 管理。生产构建
由 FastAPI `StaticFiles` 托管，现场只访问一个地址。

## 12. 已支持能力

- D02/D03 YOLO26n 推理；
- ORB/RANSAC 配准和显式 fallback；
- 未分类外观变化区域；
- N1...Nn 首次异常区间；
- 工程外观指纹、技术证据等级；
- SQLite、JSON/HTML 报告、FastAPI、Vue 和一键启动；
- 合成 Demo A、公开 TAMPAR 模拟 Demo B。

## 13. 尚未支持能力

D01/D04/D05 模型、分割、真实物流 API、账号权限、云部署、移动端、实时视频、真实
责任或赔偿结论均不在 v0.1 范围。ONNX 已导出并可推理，但 parity 的 mAP50 差值
`-0.0111765` 略超 `0.01` 工程阈值，因此当前运行时仍为 PyTorch，ONNX 标为
experimental。

## 14. 比赛演示流程

1. 运行 `scripts/demo/build_demo_cases.py` 生成外部 Demo A/B；
2. 运行 `scripts/demo/start-competition-mvp.ps1`；
3. 浏览器访问 `http://127.0.0.1:8000`；
4. 上传 N1/N2/N3，点击“开始完整分析”；
5. 查看检测框、变化指标、首次异常区间和 E 级别；
6. 打开 HTML 报告并说明 SHA-256、SQLite 和模型版本证据链。

真实端到端验证中，Demo A 得到 `N1_TO_N2 / E3`，两组配准均 `SUCCESS`；API、
SQLite、报告与前端静态页面全部通过。

## 15. 风险和边界

活动模型 test mAP50-95 仍低，D02/D03 漏检与假阳性是最明显比赛风险；变化阈值也
尚未用真实连续物流样本校准。TAMPAR probable pair 未经人工确认，只用于
`DEMO_ONLY` 观察，不形成性能指标。结论只允许写“首次观察到异常”“异常可能发生于
某区间”“建议人工复核”，不输出责任方、赔偿、违规或人为拆封认定。
