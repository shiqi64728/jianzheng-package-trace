# Competition RC v1.1 实测指标

以下数字均来自 2026-08-12 R9000P 本机实际执行证据。

## 模型对比（val）

| Model | imgsz | P | R | mAP50 | mAP50-95 | D02 AP50-95 | D03 AP50-95 | inference ms/image |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| YOLO26n | 640 | 0.331108 | 0.242798 | 0.193225 | 0.083132 | 0.037191 | 0.129074 | 6.471 |
| YOLO26n | 960 | 0.358709 | 0.261359 | 0.221814 | 0.094648 | 0.040010 | 0.149285 | 8.191 |
| YOLO26s | 640 | 0.321941 | 0.299039 | 0.238414 | 0.102231 | 0.039505 | 0.164956 | 10.177 |

YOLO26s 相对 active n960：overall AP +8.012%、D02 AP −1.261%、D02 recall +7.368%，0/3 达到 +10%；延迟低于 1.75× 上限，但提升项不足，结果为 `KEEP_CURRENT_ACTIVE`。因此没有 candidate test，active 仍为 `d02-d03-yolo26n-imgsz960-v0.1`。

## 失败与数据审计

- val failure records：1,299；D02 1,206、D03 93。
- 失败类型：low IoU 817、small object 226、missed detection 180、false positive 52、D02/D03 confusion 24。
- D02 val GT 审计：50；good label 49、questionable label 1。
- 类别标注量：D02 9,514、D03 1,790，比例 5.315:1。
- 711 张冻结图像跨 split：0 exact SHA duplicate；3 组 perceptual near duplicate，均在 train↔val；属于疑似 leakage，未删除或修改冻结数据。

## 系统验证

| 指标 | 实际 | 状态 |
|---|---:|---|
| RC v1.0 回归开始测试 | 331/331 | PASS |
| v1.1 新增测试 | 41 | PASS |
| SYSTEM BEHAVIOR VALIDATION | 17/17 executed | PASS |
| 真实场景 | 0 executed / 5 pending | PENDING_EXTERNAL_DATA |
| 主 Demo | 5/5 | PASS |
| server crash/corruption/missing model/frontend | 0/0/0/0 | PASS |

## 性能（active n960）

- cold：3568.115 ms。
- warm×10：905.863、950.050、887.301、924.411、1453.789、892.932、922.693、899.071、834.963、981.976 ms。
- warm median：914.278 ms；P90 nearest-rank：981.976 ms；min 834.963 ms；max 1453.789 ms。
- 目标 median≤1500ms、P90≤2000ms：PASS。

## 真实 calibration

`REAL_WORLD_CALIBRATION = PENDING_EXTERNAL_DATA`。合规真实包裹/图片/surface 当前均为 0；usable rate、正常误报率、变化检出率、首次区间与 trigger surface 正确率均为 `NOT_AVAILABLE`，不填造数字。change config 保持 v0.2，没有强行生成 v0.3。

## 不可变性说明

raw、冻结图片/标签内容、旧 release、runtime v0.1/v0.2、Competition RC v1.0 与 active registry 的 postflight 内容校验均通过。Ultralytics 在训练时重建了内容相同的派生 `labels/train.cache`，因此冻结目录的 metadata SHA（mtime）变化，但文件数、总字节数和包含该 cache 的全树内容 SHA 与 preflight 完全一致；这不是训练样本或标注变更，已在 postflight evidence 中单列披露。
