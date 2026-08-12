# Detector Optimization Goal Mode v2.0 Tracker

## 状态

- 基线：`origin/main` = `a33ee7d175e4d856bc46280516a3d7106f2cd83d`
- 分支：`experiment/training-detector-goal-v20`
- 开始回归：`372/372 PASS`
- 最终状态：`BEST_EFFORT_BUDGET_EXHAUSTED`
- CURRENT BEST（生产）：`d02-d03-yolo26n-imgsz960-v0.1`，val mAP50-95 `0.094648`
- FINAL VAL WINNER（预算耗尽后的最高 overall AP）：`EXP-01 / YOLO26s@640`，val mAP50-95 `0.102231`
- LEVEL-1 STATUS：`NOT_ACHIEVED`
- LEVEL-2 STATUS：`NOT_ACHIEVED`
- LEVEL-3 STATUS：`NOT_ACHIEVED`
- RUN BUDGET USED：`6/6`
- RUN BUDGET REMAINING：`0`
- test policy：搜索期间封存；仅 EXP-01 由 single-access guard 在最终选择后访问一次 test。
- promotion：`KEEP_CURRENT_ACTIVE`；未创建 v2.0 release，未改 active registry。

## 正式实验

| Experiment ID | Hypothesis | Model | Dataset | Training change | Data change | imgsz | Epochs | Batch | Val P | Val R | Val mAP50 | Val mAP50-95 | D02 AP50 | D02 AP50-95 | D02 Recall | D03 AP50 | D03 AP50-95 | D03 Recall | Latency | VRAM* | Status | Decision | Evidence |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| BASELINE | 当前 active | YOLO26n | v0.1 | official pretrained / seed 42 | 无 | 960 | 100 | auto | .358709 | .261359 | .221814 | .094648 | .138476 | .040010 | .203753 | .305152 | .149285 | .318966 | 8.191ms | 10,620,080,640B | ACTIVE | CURRENT BEST | RC v1.1 comparison |
| EXP-01 | 增加容量可能比继续放大分辨率更有效 | YOLO26s | v0.1 | n→s | 无 | 640 | 100 | auto | .321941 | .299039 | .238414 | **.102231** | .142476 | .039505 | .218767 | .334351 | **.164956** | .379310 | 10.177ms | 7,118,001,664B | COMPLETED（复用已验证正式 run） | overall +8.012%，但 D02 AP -1.261%；`TRADEOFF`。预算耗尽后作为最高 overall AP 的 final val winner | `E:\JianZhengData\runtime\competition-rc-v1.1\evidence\yolo26s-*.json` |
| EXP-02 | 广义 train-only crops/hard-example emphasis 可改善小目标 | YOLO26n | v0.2 | 无超参变化 | +344 crops；+79 hard-example copies；排除 3 个泄漏源 | 960 | 100 | auto | .362493 | .255874 | .226997 | .090926 | .129791 | .036678 | .184162 | .324202 | .145175 | .327586 | 9.562ms | 10,620,080,640B | COMPLETED | overall、D02 均低于 active，`REJECT` | `...\evidence\exp-02-*.json` |
| EXP-03 | 保守的一源一张 D02 crop 可避免 EXP-02 过度强调 | YOLO26n | v0.3 | 无超参变化 | +103 D02 crops；无 hard-example copies；排除 3 个泄漏源 | 960 | 100 | auto | .344916 | .250615 | .214457 | .095361 | .134378 | .038139 | .190885 | .294535 | .152583 | .310345 | 8.230ms | 10,620,080,640B | COMPLETED | overall 仅略高 active，D02 仍下降，`TRADEOFF/REJECT` | `...\evidence\exp-03-*.json` |
| EXP-04 | 稳定的 s@640 容量方向与 960 输入结合可跨越 Level-1 | YOLO26s | v0.1 | imgsz 640→960 | 无 | 960 | 97（patience early-stop） | auto | .403286 | .219499 | .214165 | .084271 | .126254 | .037100 | .137274 | .302076 | .131442 | .301724 | 13.405ms | 15,720,076,288B | COMPLETED | 精度与 D03 均回退，`REJECT` | `...\evidence\exp-04-*.json` |
| EXP-05 | 禁用 mosaic 可保留原生凹痕尺度和箱体上下文 | YOLO26n | v0.1 | mosaic 1.0→0.0 | train-only augmentation | 960 | 100 | auto | .296035 | .259483 | .200486 | .087638 | .114808 | .032116 | .200000 | .286164 | .143159 | .318966 | 6.823ms | 10,620,080,640B | COMPLETED | 未改善 D02，`REJECT` | `...\evidence\exp-05-*.json` |
| EXP-06 | 从 active checkpoint 二阶段微调并降低 mosaic 暴露可保留定位能力 | YOLO26n | v0.1 | active init；mosaic=0.5 | train-only augmentation | 960 | 26（patience early-stop） | auto | .343636 | .234487 | .201489 | .085430 | .128509 | .035905 | .175871 | .274469 | .134954 | .293103 | 8.109ms | 10,620,080,640B | COMPLETED | 最佳 epoch=1，继续训练无收益，`REJECT` | `...\evidence\exp-06-*.json` |

\* VRAM 是 PyTorch peak allocation，包含 Ultralytics AutoBatch/WDDM 探测阶段；数值可超过物理常驻显存，不能解释为稳定常驻占用。所有 smoke 均通过 CUDA、AMP、有限 loss、val、checkpoint 和 OOM 检查。

## 数据诊断与派生数据

- label audit：11,304 bbox；near-zero 0、短边 `<4px` 3、截边 295、异常长宽比 83、重复 bbox 0、越界 0，合计 376 个几何规则 `label_concern`；未直接改标签。
- D02 taxonomy（全部 1,865 个 val D02 GT）：SUBTLE 476、SMALL 274、MEDIUM 686、LARGE 374、BACKGROUND_AMBIGUITY 2、LABEL_CONCERN 53。
- smallest quartile：D02 `204/248 = 82.258%` failure；D03 `22/37 = 59.459%` failure。
- background：active n960 在 val 的 40 个高置信未匹配预测中，纸箱纹理 23、折痕 3、阴影 2、胶带 4、其他 8；这是确定性外观代理分类，仍需人工复核。
- v0.1 near duplicate：0 exact，3 个 perceptual train→val pair；判为 suspected leakage；未查看 test prediction。
- v0.2：保留 val/test 内容哈希，排除 3 个泄漏 train source；611 个基础 train image + 79 个 hard-example copy + 344 个 crop = 1,034 个 train image；hard-negative prediction 103。
- v0.2 derived audit：0 exact、0 perceptual cross-split pair。
- v0.3：额外的保守自适应候选，仅 103 个 D02 crop；714 个 train image；val/test 同样完全不变。
- v0.2 lock：`E:\JianZhengData\training\detect-d02-d03-v0.2\dataset-lock-v0.2.json`。

## Winner、test 与停止条件

EXP-01 是六个正式 run 中 overall val AP 最高者；相对 active：overall AP `+8.012%`、Recall `+14.417%`、D02 AP `-1.261%`、D03 AP `+10.498%`。D02 tradeoff 未被隐藏，因此搜索阶段没有自动替换 CURRENT BEST；预算耗尽后仅将它作为 final-test candidate。

最终 test 只运行一次：overall P/R/mAP50/mAP50-95 = `.335742/.223156/.185351/.075155`；D02 AP50/AP50-95/Recall = `.121838/.034843/.166311`；D03 AP50/AP50-95/Recall = `.248865/.115467/.280000`。未达到 overall `.095` 与 D02 `.050` 门槛，因此 `KEEP_CURRENT_ACTIVE`。不能再根据该 test 继续训练。

最终没有达到任何 Level。主要瓶颈不是更多超参搜索，而是极小/细微 D02、纸箱纹理背景混淆、3 个跨 split 近重复以及公开数据到真实驿站场景的域差异。
