# 件证 Competition MVP v0.2 架构

## 1. v0.1 到 v0.2

v0.1 的一个节点只有一张包裹外观图；v0.2 把主键扩展为
`(case_id, node_id, surface)`，增加多表面融合、append-only 人工复核、合成工程标定、
Demo C/D、模型预热和现场自检/停止能力。活动 D02/D03 模型与 v0.1 runtime 均未替换。

## 2. 多节点多表面数据结构

案例由连续 `N1...Nn` 构成；每个节点可有 `front / left / right / top / back / bottom /
unknown` 的任意子集。第一版 UI 默认只显示前四个。单表面旧客户端未传 surface 时按
`front` 处理。

## 3. surface fingerprint

每个 `node_id + surface` 独立生成 `image_sha256`、宽高、ORB 关键点数、规范化
descriptor digest 和 D02/D03 known damage summary。节点摘要包含可用表面、表面哈希、
已知损伤总数、损伤表面和未知变化表面；不同表面不会拼成虚假的单一图像哈希。

## 4. known detector

`ModelRegistry → Detector` 继续加载
`d02-d03-yolo26n-imgsz960-v0.1`，固定 `imgsz=960`、PyTorch runtime 和既有 SHA-256。
它只自动分类 D02 表面凹陷、D03 纸箱破口。

## 5. open-set change

每个相邻 pair 先用 ORB/RANSAC 配准，再进行灰度 absdiff、阈值、形态学和区域提取。
未与 D02/D03 detection 对应的可靠变化标记为 `UNKNOWN_VISUAL_CHANGE`。v0.2 只把合成
工程标定的 `significant_change_ratio` 从 0.006 调到 0.004，不涉及 detector 阈值或权重。

## 6. human review

机器分析完成后，复核人可以选择 D01/D02/D03/D04/D05、`NORMAL_VARIATION` 或
`UNSURE`，状态为 `CONFIRMED / REJECTED / UNSURE`，并只能使用 MEMBER-A/B/C 或
DEMO-REVIEWER 匿名代号。

## 7. surface fusion

每个区间按 surface 保留 NORMAL、KNOWN_DAMAGE、KNOWN_DAMAGE_AND_CHANGE、
UNKNOWN_CHANGE、MISSING 或 INSUFFICIENT_EVIDENCE。至少一个可靠已知损伤或未知变化
才触发区间；只有缺失/失败不会被判成异常。

## 8. sequence fusion

`sequence_locator.py` 从 N1 开始按相邻区间排序，返回第一个可证实异常区间、目标节点、
`trigger_surfaces`、每表面状态、完整度和 E0–E3 工程证据等级。比较键始终为
`N{k}.surface → N{k+1}.surface`，禁止跨 surface 自动比较。

## 9. evidence report

JSON/HTML 报告包含节点×表面图片矩阵、surface fingerprint、detections、pair 配准与
变化区域、触发表面、机器分析、人工复核和最终区间。新增 review 后生成新 revision
文件，不覆盖之前的报告文件。

## 10. database

v0.2 数据库位于 `E:\JianZhengData\runtime\mvp-v0.2\jianzheng.db`。首次运行可用
SQLite backup API 只读复制 v0.1，再执行幂等 migration；旧 `case_nodes` 保留为
`case_nodes_v01_backup`。`schema_version=2`，`database_migrations` 记录迁移，新增
`surface_analysis` 与 append-only `review_events`，数据库 trigger 禁止修改或删除复核事件。

## 11. API

v0.1 的 health、model info、detect、change、cases、nodes、analyze、case、report 和 list
接口继续兼容。新增 `POST /api/model/warmup`、`POST /api/cases/{case_id}/reviews`、
`GET /api/cases/{case_id}/reviews`。上传文件仍由服务端生成安全文件名。

## 12. frontend

Vue 页面默认 Simple Mode；Multi-Surface Mode 展示 N1/N2/N3 × 四表面矩阵、缩略图、
检测框、变化比、状态与复核结果。复核面板明确分离 machine result 和 human review。
没有引入 Router、Pinia、Tailwind、ECharts 或大型组件库。

## 13. demo

- Demo A：旧合成未知变化回归；
- Demo B：旧 TAMPAR probable pair 回归，非真实物流轨迹；
- Demo C：固定 seed 从冻结公开 val 选取有 ground truth 且活动 detector 有输出的样本；
- Demo D：N1/N2/N3 × front/left/right/top，只有 left 在 N2 首次变化。

Demo D 已通过真实 Uvicorn、HTTP 上传、SQLite、multi-surface analyzer、版本化报告和
构建后的前端完成端到端验证。

## 14. 支持范围

当前真实实现口径为：AI 已知异常检测 + 开放集变化检测 + 人工复核 + 多节点多表面证据
融合。D01/D04/D05 已有发现与人工确认闭环，但不是 AI 自动分类。

## 15. 局限

活动 detector 的既有测试表现有限；合成标定不代表真实物流场景；强视角、背景、光照和
遮挡仍可能导致配准失败或未知变化；缺失拍摄会降低完整度；尚未实现真实物流 API、登录、
云部署、移动端、视频、分割模型或法律责任自动判定。
