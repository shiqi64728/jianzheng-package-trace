# D02/D03 Detector Optimization v2.0

## 结论

六个正式 run 已全部使用，最终状态为 `BEST_EFFORT_BUDGET_EXHAUSTED`。没有候选达到 Level-1。最高 overall val 是 EXP-01（YOLO26s@640），但它的 D02 AP 比 active 略低；一次性 test 又未达到 promotion gate，所以正式 active detector 保持不变。

## 模型对比

| Model | Dataset | imgsz | Params | Val mAP50-95 | D02 AP | D03 AP | Recall | Latency | Peak VRAM* | Training time | Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| active YOLO26n | v0.1 | 960 | 2,375,226 | .094648 | .040010 | .149285 | .261359 | 8.191ms | 10.62GB | historical | ACTIVE |
| EXP-01 YOLO26s | v0.1 | 640 | 9,465,954 | **.102231** | .039505 | **.164956** | **.299039** | 10.177ms | 7.12GB | 2,082.22s | FINAL VAL WINNER / TRADEOFF |
| EXP-02 YOLO26n | v0.2 | 960 | 2,375,226 | .090926 | .036678 | .145175 | .255874 | 9.562ms | 10.62GB | 4,274.84s | REJECT |
| EXP-03 YOLO26n | v0.3 | 960 | 2,375,226 | .095361 | .038139 | .152583 | .250615 | 8.230ms | 10.62GB | 2,991.69s | TRADEOFF / REJECT |
| EXP-04 YOLO26s | v0.1 | 960 | 9,465,954 | .084271 | .037100 | .131442 | .219499 | 13.405ms | 15.72GB | 3,787.92s | REJECT |
| EXP-05 YOLO26n | v0.1 | 960 | 2,375,226 | .087638 | .032116 | .143159 | .259483 | 6.823ms | 10.62GB | 2,590.43s | REJECT |
| EXP-06 YOLO26n | v0.1 | 960 | 2,375,226 | .085430 | .035905 | .134954 | .234487 | 8.109ms | 10.62GB | 706.60s | REJECT |

\* 包含 AutoBatch/WDDM 探测开销；不是稳定常驻显存。

## 最终一次 test

候选 SHA-256：`83bf8f7fdc29837af19ef2c9be4f30dd9d5175deaa37142d7ed6c0242378c1ee`。

| Scope | P | R | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| overall | .335742 | .223156 | .185351 | .075155 |
| D02 | .259568 | .166311 | .121838 | .034843 |
| D03 | .411917 | .280000 | .248865 | .115467 |

- 相对 active test overall AP：`-0.458%`。
- D02 test AP：`0.034843 < 0.050`。
- D03 无灾难性回退，latency 9.577ms 也通过 1.75× 门槛。
- 决策：`KEEP_CURRENT_ACTIVE`。
- lock：`E:\JianZhengData\runtime\detector-goal-v2.0\evidence\final-test-lock-v2.0.json`。

## 科学解释

1. 直接增加模型容量（s@640）提高了总体与 D03，但没有解决 D02。
2. 放大到 s@960 增加计算开销却明显回退，说明当前瓶颈不是单纯像素不足。
3. 广义 crops/hard-example sampling 和保守 D02-only crops 都未带来可靠 D02 改善，显示公开数据内部的重采样不能替代新的真实样本。
4. 完全禁用 mosaic 或从 active 二阶段微调同样无效；EXP-06 在 epoch 1 最好并触发 early-stop，说明继续拟合当前数据没有净收益。
5. 下一阶段应冻结模型搜索，采集真实同包裹、多表面、N1/N2/N3 序列，人工复核 D02 与 near-duplicate，再建立独立 calibration split。
