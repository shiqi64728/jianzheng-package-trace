# Competition Release Candidate v1.0 Goal Tracker

- 分支：`feat/competition-release-candidate-v10`
- `origin/main` 基线：`809a1493f0c5fb067bef46290fddedf39fe12eba`
- 启动基线：`255/255 PASS`
- 最终全量：`331/331 PASS`（原 255 + 新增 76）
- 外部运行根目录：`E:\JianZhengData\runtime\competition-rc-v1.0`
- `REAL_WORLD_CALIBRATION = PENDING_EXTERNAL_DATA`（允许状态，不阻断 Competition RC）

| Goal ID | Goal | Priority | Status | Metric | Target | Current | Evidence | Blocker | Next Action |
|---|---|---:|---|---|---|---|---|---|---|
| GOAL-01 | 保持 MVP v0.2 全部能力 | MUST | PASS | 原测试及最终全量测试 | 255/255 + 新测试全通过 | 原 255 保留；331/331 PASS | `evidence/test-summary-v1.0.json` | 无 | 无 |
| GOAL-02 | 可解释责任辅助规则引擎 | MUST | PASS | 确定性、分解一致、失败配准降级 | ≥10 测试；0-100；失败配准不得 HIGH | 九项分解；18 测试；失败配准 cap=59 | `ai/runtime/risk_engine.py`；test_risk_engine_v10 | 无 | 无 |
| GOAL-03 | 工单闭环 | MUST | PASS | 状态机和 HTTP E2E | OPEN→IN_REVIEW→RESOLVED PASS | 3 事件、append-only、报告历史；3/3 演示通过 | stability JSON；workflow tests | 无 | 无 |
| GOAL-04 | 运营统计看板 | MUST | PASS | SQLite 真实指标 | ≥8 项 | 11 类汇总指标 + 4 趋势 series | Dashboard API；`metrics-v1.0.md` | 无 | 无 |
| GOAL-05 | 结构化物流节点接入 | MUST | PASS | JSON/CSV E2E | JSON、CSV、错误字段 PASS | TestClient 与真实 Uvicorn 全通过 | `competition-e2e-v1.0.json`；logistics tests | 无 | 无 |
| GOAL-06 | 视频关键帧异常筛查 | MUST | PASS | MP4 解码和确定性关键帧 | ≥1 异常关键帧且时间戳正确 | 30 帧视频；6 帧采样；4 帧异常；keyframe HTTP 200 | demo assets JSON；E2E；video tests | 无 | 无 |
| GOAL-07 | Evidence Report v1.0 | MUST | PASS | Demo D HTML/JSON 完整性 | 字段完整、UTF-8、图片有效 | 三次稳定演示均生成完整报告；固定声明精确 | stability report paths；report tests | 无 | 无 |
| GOAL-08 | 比赛级演示稳定性 | MUST | PASS | 完整演示连续运行 | 3/3 PASS | 3/3；0 crash/corruption/missing model/frontend | `competition-release-stability-v1.0.json` | 无 | 无 |
| GOAL-09 | 性能不明显退化 | MUST | PASS | cold + warm×5 | median≤1500ms 且退化≤50% | cold 4097.121ms；warm median 940.674ms | `performance-v1.0.json` | 无 | 无 |
| GOAL-10 | 比赛验证矩阵 | MUST | PASS | SYSTEM BEHAVIOR VALIDATION | ≥16 且全通过 | 17/17 PASS | `competition-validation-summary-v1.0.json` | 无 | 无 |
| GOAL-11 | 能力真实性矩阵 | MUST | PASS | 分类和边界完整 | 指定分类全部明确 | D01-D05、视频、risk/legal 边界全部明确 | `docs/competition/capability-matrix-v1.0.md` | 无 | 无 |
| GOAL-12 | 比赛 Release 文档包 | MUST | PASS | 指定文档和 runbook | 7 份指定文档 | 7/7；runbook 含检查、A-D、Dashboard、Review、工单、报告、fallback、停止 | `docs/competition/` | 无 | 无 |
| GOAL-13 | 开源与数据来源清单 | MUST | PASS | 版本/用途/许可证/来源 | 不猜测；缺证据 REVIEW_REQUIRED | 依据 installed METADATA、package-lock、source registry | `open-source-and-data-sources-v1.0.md` | 无 | 无 |
| GOAL-14 | 比赛材料证据包 | MUST | PASS | 截图/录屏/指标/架构/风险 | 所有数字可追溯 | 实际指标、版本、Mermaid、步骤和边界齐全 | `material-evidence-pack-v1.0.md` | 无 | 无 |

## 验证证据索引

| 证据 | 绝对路径 |
|---|---|
| Preflight invariants | `E:\JianZhengData\runtime\competition-rc-v1.0\evidence\preflight-invariants.json` |
| 测试总结 | `E:\JianZhengData\runtime\competition-rc-v1.0\evidence\test-summary-v1.0.json` |
| Release manifest | `E:\JianZhengData\runtime\competition-rc-v1.0\release\competition-release-manifest-v1.0.json` |
| 真实 Uvicorn E2E | `E:\JianZhengData\runtime\competition-rc-v1.0\competition-e2e-v1.0.json` |
| 3/3 稳定性 | `E:\JianZhengData\runtime\competition-rc-v1.0\competition-release-stability-v1.0.json` |
| 性能 | `E:\JianZhengData\runtime\competition-rc-v1.0\performance-v1.0.json` |
| Demo 计时 | `E:\JianZhengData\runtime\competition-rc-v1.0\demo-duration-v1.0.json` |
| 17 场景矩阵 | `E:\JianZhengData\runtime\competition-validation-v1.0\competition-validation-summary-v1.0.json` |
| 视频 demo | `E:\JianZhengData\runtime\competition-rc-v1.0\demo\competition-demo-assets-v1.0.json` |
| 真实序列发现审计 | `E:\JianZhengData\runtime\competition-rc-v1.0\evidence\real-sequence-discovery-v1.0.json` |
| start/self-check/stop 终验 | `E:\JianZhengData\runtime\competition-rc-v1.0\evidence\start-selfcheck-stop-v1.0.json` |
| Postflight invariants | `E:\JianZhengData\runtime\competition-rc-v1.0\evidence\postflight-invariants-v1.0.json` |

## 前置与边界审计

- 五个 MVP v0.2 提交均为 `origin/main` ancestor。首次 pull 遇到临时 TLS 失败；随后成功 fetch，并在干净工作树上安全快进与重建分支。
- active model SHA、raw、frozen、model history、runtime v0.1/v0.2 已在 preflight 固化；postflight 逐项比较全部 `unchanged=true`。
- 没有训练、下载、导出或替换模型。`STRETCH-MODEL-01 = NOT_EXECUTED`。
- 未发现获授权且隐私审核完成的同包裹 N1/N2/N3 多表面真实序列；协议为 `docs/dataset/real-sequence-validation-protocol-v1.0.md`。
- 允许的剩余项仅为 `REAL_WORLD_CALIBRATION = PENDING_EXTERNAL_DATA`。
