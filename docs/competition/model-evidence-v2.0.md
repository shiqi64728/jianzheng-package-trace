# 比赛模型证据 v2.0

## 可用于答辩的事实

- 原始正式 active：YOLO26n@960，val mAP50-95 `0.094648`，D02 `0.040010`，D03 `0.149285`，Recall `0.261359`。
- 本轮六个正式 run 中最高 val：YOLO26s@640，mAP50-95 `0.102231`，D02 `0.039505`，D03 `0.164956`，Recall `0.299039`。
- 相对 active val：overall AP `+8.012%`、Recall `+14.417%`、D03 AP `+10.498%`，但 D02 AP `-1.261%`；因此必须称为“总体/D03 改善但 D02 有 tradeoff”，不能宣称全面提升。
- final candidate 的 test 只访问一次：overall AP `0.075155`、D02 AP `0.034843`、D03 AP `0.115467`；相对 active test overall AP `-0.458%`。
- promotion gate 要求 overall AP≥`0.095` 且 D02 AP≥`0.050`；结果为 `KEEP_CURRENT_ACTIVE`。
- 正式 active 仍是 `d02-d03-yolo26n-imgsz960-v0.1`，SHA-256 `2dd857412b63df66d1273b326dc51afaed895da1d360c97e184762c882181a97`。

## 数据与验证原则

- 数据版本：冻结 `detect-d02-d03-v0.1`；train-only 派生 `v0.2` 与诊断性 `v0.3`。
- v0.2/v0.3 的 val、test 与 v0.1 内容完全相同；仅 train 变化。
- 审计发现 3 个 perceptual train→val near-duplicate；派生 train 排除了对应源，派生审计为 0 exact / 0 perceptual cross-split pair。
- 模型选择仅依据 val；33 张 test 只在 winner 锁定后执行一次；test 结果没有用于继续训练。
- 所有数据来源、派生规则、源图 ID、bbox ID、crop coordinates 与 SHA 均在外部 manifest/lock 中保留。

## 能力边界

- 自动 detector 只支持 D02（表面凹陷）和 D03（纸箱破口）。
- D01、D04、D05 仍是 `OPEN_SET_DETECTION + HUMAN_REVIEW`，不得表述为五类自动识别。
- 极小/细微凹痕、纹理/折痕/胶带背景混淆、遮挡和真实驿站域差异仍是主要限制。
- 当前公开数据不足以证明真实物流场景泛化，也不能直接给出法律责任结论。

## 证据入口

- Goal tracker：`docs/goals/detector-optimization-v2.0.md`
- 完整对比：`docs/training/detector-optimization-v2.0.md`
- 外部证据：`E:\JianZhengData\runtime\detector-goal-v2.0\evidence`
- final-test lock：`E:\JianZhengData\runtime\detector-goal-v2.0\evidence\final-test-lock-v2.0.json`
