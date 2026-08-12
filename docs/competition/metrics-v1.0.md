# Competition RC v1.0 实测指标

生成依据均为 2026-08-12 R9000P 本机实际运行结果；不包含预测百分比。

## 质量门槛

| 指标 | 实际 | 目标 | 结果 | 证据 |
|---|---:|---:|---|---|
| 原有测试 | 255/255 | 255/255 | PASS | `evidence/test-summary-v1.0.json` |
| 新增有意义测试 | 76/76 | ≥50 | PASS | 同上 |
| 全量测试 | 331/331 | 全通过 | PASS | 同上 |
| Uvicorn E2E | 11/11 assertions | 全通过 | PASS | `competition-e2e-v1.0.json` |
| 稳定完整演示 | 3/3 | 3/3 | PASS | `competition-release-stability-v1.0.json` |
| SYSTEM BEHAVIOR VALIDATION | 17/17 | ≥16 | PASS | `competition-validation-summary-v1.0.json` |
| 视频异常采样帧 | 4 | ≥1 | PASS | `competition-demo-assets-v1.0.json` 与 E2E |
| 主 Demo 自动化计时 | 1.943 s | ≤180 s | PASS | `demo-duration-v1.0.json` |

上述相对路径均位于 `E:\JianZhengData\runtime\competition-rc-v1.0`；验证矩阵位于 `E:\JianZhengData\runtime\competition-validation-v1.0`。

## 性能

| 指标 | 实际 |
|---|---:|
| cold HTTP analyze | 4097.121 ms |
| warm 1 | 1297.389 ms |
| warm 2 | 821.700 ms |
| warm 3 | 858.888 ms |
| warm 4 | 954.766 ms |
| warm 5 | 940.674 ms |
| warm median | **940.674 ms** |
| v0.2 reference median | 1023.000 ms |
| 50% 退化上限 | 1534.500 ms |

warm median 同时满足 ≤1500 ms 和相对 v0.2 不恶化超过 50%。计时分别记录 `core_analysis / database / risk_engine / report / total_request`，HTML 报告耗时没有并入 detector 字段。

## 当前 SQLite Dashboard 快照

该快照包含从 v0.2 bootstrap 的历史案例及本轮 RC 验证案例，因继续运行验证会增长，现场应以 API 当前返回为准。

| 指标 | 快照值 |
|---|---:|
| case_count | 35 |
| abnormal_case_count | 33 |
| review_pending_count | 15 |
| work_order_count | 15 |
| resolved_work_order_count | 15 |
| human D01 / D04 / D05 events | 1 / 1 / 18 |
| front / left / right / top captures | 99 / 81 / 81 / 81 |
| E3 analysis results | 33 |
| MEDIUM latest risk records | 21 |
| average_analyze_time_ms（历史分析 JSON） | 1976.823 |

来源：SQLite `cases`、`analysis_results`、`review_events`、`work_orders`、`case_nodes`、`risk_assessments`，由 `EvidenceDatabase.dashboard_summary()` 查询，无写死业务展示数值。

## 非 accuracy 指标说明

17/17 是受控业务规则行为验证，不是模型 accuracy。当前活动模型测试集 mAP 边界沿用已有模型审计，不因 RC 业务功能增加而被夸大；本轮未训练新模型。
