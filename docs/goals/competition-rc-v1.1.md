# Competition RC v1.1 Goal Tracker

- 分支：`experiment/competition-rc-v11-hardening`
- `origin/main` 基线：`dd68382a50473cb21453b17ba6f61c7191221538`
- 开始测试：`331/331 PASS`
- 最终测试：`372/372 PASS`（新增 41）
- 外部运行目录：`E:\JianZhengData\runtime\competition-rc-v1.1`
- 范围：仅 real-world calibration、D02/D03 model hardening 与最终冻结，不新增产品功能。

| Goal ID | Risk Addressed | Goal | Priority | Status | Metric | Target | Current | Evidence | Blocker | Next Action |
|---|---|---|---:|---|---|---|---|---|---|---|
| GOAL-01 | RISK-01/RISK-02 | RC v1.0 regression safety | MUST | PASS | 原测试与历史资产 preflight/postflight | 331/331；不可变 payload 异常变化 0 | 331/331 PASS；结束时 raw、冻结图片/标签内容、旧模型、旧 runtime、RC v1.0 与 active registry 均与 preflight 一致；Ultralytics 仅重建了内容相同的派生 `labels/train.cache`，其 mtime 漂移已披露 | `evidence/preflight-test-summary-v1.1.json`；`evidence/preflight-invariants-v1.1.json`；`evidence/postflight-invariants-v1.1.json` | 无 | 无 |
| GOAL-02 | RISK-01 | 真实序列发现与导入 | MUST | PENDING_EXTERNAL_DATA | 合规同包裹 N1/N2/N3 序列 | ≥3 包裹、36 图 | 已搜索允许的 `E:\JianZhengData`；incoming 无图片，未发现合规序列；60 行采集任务已生成 | `evidence/real-sequence-discovery-v1.1.json`；`real-calibration/capture-worklist.csv` | 缺少完成权限/隐私审核的真实采集 | 等待成员 C 交付 |
| GOAL-03 | RISK-01 | 真实 registration/change calibration | MUST | PENDING_EXTERNAL_DATA | usable/误报/检出/区间/surface | 工程目标 80%/20%/80%/80% | 无真实序列，不计算或伪造指标；校准 parser/metrics 待验证 | `docs/dataset/real-world-calibration-pack-v1.1.md` | 同 GOAL-02 | 真实数据到达后只跑 calibration |
| GOAL-04 | RISK-02 | D02/D03 failure audit | MUST | PASS | val 失败分类、D02 ≥50 GT、跨 split 近重复 | 审计完成且 test 预测不用于调参 | 1,299 条 val failure；50 个 D02 GT；711 图跨 split DCT audit，0 exact、3 perceptual near duplicates | `evidence/detector-error-audit-v1.1.*`；`evidence/near-duplicate-audit-v1.1.json` | 无；3 组疑似 leakage 只报告不删除 | 执行单一候选 |
| GOAL-05 | RISK-02 | 单一 YOLO26s@640 实验 | MUST | PASS | smoke、100 epochs、val-only | 单一候选，固定参数 | 官方 yolo26s SHA `646f8bc3...`; smoke 3/3；100 epochs；val 完成，无 NaN/OOM | `evidence/yolo26s-{smoke,training,val}-v1.1.json` | 无 | 无 |
| GOAL-06 | RISK-02 | 候选模型晋级决策 | MUST | PASS | 三模型指标与 promotion gate | ≥2/3 提升且延迟≤1.75× | 0/3 提升项达 10%；延迟 PASS；`KEEP_CURRENT_ACTIVE`；未访问 candidate test | `evidence/detector-comparison-v1.1.json`；`docs/training/d02-d03-detector-comparison-v1.1.md` | 无 | 保持 n960 active |
| GOAL-07 | RISK-01/RISK-02 | 真实/代理场景系统验证 | MUST | PASS | 行为场景、5 次 Demo、cold×1/warm×10 | 5/5；median≤1500ms；P90≤2000ms | 17/17 代理场景 PASS；5 个真实场景 pending；Demo 5/5；cold 3568.115ms；warm median 914.278ms、P90 981.976ms | validation v1.1；stability v1.1；performance v1.1 | 无 | 无 |
| GOAL-08 | RISK-01/RISK-02 | Competition RC v1.1 final freeze | MUST | PASS | manifest、文档、工程门禁与不变性 | 全部 PASS | 独立 runtime；372/372；53-file manifest；Ruff/py_compile/pip/npm PASS；历史不可变 payload postflight PASS，派生 cache metadata 漂移已单列 | release manifest；final test/security/postflight evidence；v1.1 文档 | 无 | 无 |

## 状态边界

- GOAL-02/03 允许因真实数据缺失保持 `PENDING_EXTERNAL_DATA`，不阻断 RC v1.1。
- `REAL_WORLD_CALIBRATION = PENDING_EXTERNAL_DATA` 不是模型或系统准确率结论。
- D01/D04/D05 始终为 `OPEN_SET_DETECTION + HUMAN_REVIEW`。
- 本轮 test 只允许 near-duplicate 泄漏审计；只有候选达到 `PROMOTION_ELIGIBLE` 后才允许一次候选 test evaluation。
- YOLO 训练会重建冻结目录中的派生 `labels/train.cache`。其文件数、字节数及全树内容 SHA 与 preflight 一致，只有 mtime 改变；图片、标签、lock 和其他不可变 payload 均未改变。postflight 将这一已解释的工具副作用与 unexpected payload change 分开记录。

## 最终证据索引

| 证据 | 绝对路径 |
|---|---|
| Preflight tests | `E:\JianZhengData\runtime\competition-rc-v1.1\evidence\preflight-test-summary-v1.1.json` |
| Final tests | `E:\JianZhengData\runtime\competition-rc-v1.1\evidence\final-test-summary-v1.1.json` |
| Preflight invariants | `E:\JianZhengData\runtime\competition-rc-v1.1\evidence\preflight-invariants-v1.1.json` |
| Postflight invariants | `E:\JianZhengData\runtime\competition-rc-v1.1\evidence\postflight-invariants-v1.1.json` |
| Real discovery | `E:\JianZhengData\runtime\competition-rc-v1.1\evidence\real-sequence-discovery-v1.1.json` |
| Detector audit | `E:\JianZhengData\runtime\competition-rc-v1.1\evidence\detector-error-audit-v1.1.json` |
| Near duplicates | `E:\JianZhengData\runtime\competition-rc-v1.1\evidence\near-duplicate-audit-v1.1.json` |
| YOLO26s smoke/train/val | `E:\JianZhengData\runtime\competition-rc-v1.1\evidence\yolo26s-*-v1.1.json` |
| Model decision | `E:\JianZhengData\runtime\competition-rc-v1.1\evidence\detector-comparison-v1.1.json` |
| Validation | `E:\JianZhengData\runtime\competition-validation-v1.1\competition-validation-summary-v1.1.json` |
| 5-run stability | `E:\JianZhengData\runtime\competition-rc-v1.1\competition-release-stability-v1.1.json` |
| Performance | `E:\JianZhengData\runtime\competition-rc-v1.1\performance-v1.1.json` |
| Release manifest | `E:\JianZhengData\runtime\competition-rc-v1.1\release\competition-release-manifest-v1.1.json` |
