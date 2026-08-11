# D02/D03 YOLO26n 首个正式目标检测基线 v0.1

## 结果

本轮完成了一条可复现的 `defect-cardboard → 冻结D02/D03数据 → YOLO26n smoke → 100 epoch正式训练 → val/test评估 → release` 链路。模型只包含：

- `0 = D02_surface_dent`：表面凹陷；
- `1 = D03_carton_tear`：纸箱破口。

没有加入 D01、D04、D05、NORMAL、ABNORMAL_GENERAL 或 TAMPAR 类别，也没有进行分割、连续节点、责任判定、ONNX 或部署开发。

## 冻结数据

数据版本：`detect-d02-d03-v0.1`。

| 项目 | 数量 |
| --- | ---: |
| 原始治理候选图片 | 1,036 |
| 因包含 dirt 整图排除 | 184 |
| 其他治理状态排除 | 141 |
| 最终图片 | 711 |
| train / val / test | 614 / 64 / 33 |
| D02 bbox | 9,514 |
| D03 bbox | 1,790 |
| 总 bbox | 11,304 |

保留原始 train/valid/test，仅将目录名 `valid` 规范为 `val`。没有随机重拆 test。所有图片按原始字节复制，源与训练副本 SHA-256 全部一致。自定义验证和 Ultralytics 8.4.102 预检均读取到 614/64/33 张图片，空标签、缺失配对、非法类别、非法坐标、精确重复和跨 split 重复均为 0。

`dataset-lock.json` SHA-256：

```text
6d496281ade6486434c0eb85a473b2bd3e8e5574bcc51ca1d371895851ea6e97
```

## 预训练权重

只下载 `yolo26n.pt`，来源为当前已安装 Ultralytics 包的官方资产解析机制：

```text
https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt
```

- 大小：5,544,453 字节；
- SHA-256：`9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`；
- detect 加载：通过；
- RTX 5060 Laptop GPU 合成图片推理：通过。

## Smoke test

- 3 epoch；
- `fraction=0.25`；
- `imgsz=640`；
- `batch=-1`，实际 batch 9；
- CUDA、AMP、checkpoint、validation 和绘图正常；
- results.csv 无 NaN/Inf；
- 总耗时 76.089 秒。

## 正式训练

固定参数：100 epoch、patience 25、batch -1、device 0、workers 4、cache false、seed 42、deterministic true、optimizer auto、pretrained true、AMP true、save period 10。

- 实际 batch：8；
- 实际 epoch：100；
- early stop：否；
- best epoch：97；
- 总训练时间：1,180.176 秒（约 19 分 40 秒）；
- 平均 epoch：11.802 秒；
- 记录的 PyTorch peak allocated GPU memory：4,727,974,912 字节。

## 正式指标

### Validation（best.pt）

| 类别 | Precision | Recall | AP50 | AP50-95 |
| --- | ---: | ---: | ---: | ---: |
| overall | 0.331108 | 0.242798 | 0.193225 | 0.083132 |
| D02 | 0.292472 | 0.192493 | 0.131522 | 0.037191 |
| D03 | 0.369744 | 0.293103 | 0.254927 | 0.129074 |

`last.pt` validation：Precision 0.367590、Recall 0.231518、mAP50 0.192978、mAP50-95 0.080858。以 `best.pt` 作为正式候选。

### 独立 Test（best.pt）

Precision 0.409177、Recall 0.185970、mAP50 0.183131、mAP50-95 0.071481。

测试集来自原始合法 test split，没有把 val 当作 test。

## 混淆矩阵和失败分析

Validation 混淆矩阵中正确类别分配 285，D02/D03 互相混淆 1，背景相关漏检/假阳性 1,989。主要问题是召回率低和背景相关错误，而不是 D02/D03 互相混淆。

Test 自动失败分析共 1,065 条记录：低 IoU 413、小目标失败 478、高置信假阳性 33、D02/D03 混淆 16、漏检 125。失败类型可交叠，例如一个漏检的小目标同时产生两条分析记录。未修改任何标签。

## 定性结果与制品

从 test 以 seed 42 确定性抽取 20 张，分别保存预测图和 GT 可视化。正式运行和 release 位于：

```text
E:/JianZhengData/training/runs/detect-d02-d03-yolo26n-v0.1
E:/JianZhengData/models/releases/d02-d03-yolo26n-baseline-v0.1
```

`best.pt` SHA-256：

```text
1959fcaf71987e52e5475f7601fc10ca7e40e7b747ddf085705135dccb0ed74f
```

模型二进制、数据、运行图和大型日志均保留在 Git 仓库外。

## 复现命令

```powershell
& $python scripts/training/prepare_d02_d03_dataset.py `
  --external-root E:/JianZhengData/external `
  --manifest E:/JianZhengData/external/converted/manifests/defect-cardboard-v0.1.csv `
  --license-report E:/JianZhengData/external/reports/external-license-audit-v0.1.json `
  --class-mapping E:/JianZhengData/external/reports/external-class-mapping-audit-v0.1.csv `
  --output-dir E:/JianZhengData/training/detect-d02-d03-v0.1 `
  --source-commit 337248254c590bb4b783a8524d763cd2e2781ca6
& $python scripts/training/train_d02_d03_baseline.py --config configs/training/experiments/d02-d03-yolo26n-baseline-v0.1.json --mode prepare-weight
& $python scripts/training/train_d02_d03_baseline.py --config configs/training/experiments/d02-d03-yolo26n-baseline-v0.1.json --mode preflight
& $python scripts/training/train_d02_d03_baseline.py --config configs/training/experiments/d02-d03-yolo26n-baseline-v0.1.json --mode smoke
& $python scripts/training/train_d02_d03_baseline.py --config configs/training/experiments/d02-d03-yolo26n-baseline-v0.1.json --mode train
& $python scripts/training/evaluate_d02_d03_baseline.py --config configs/training/experiments/d02-d03-yolo26n-baseline-v0.1.json
```

冻结目录和正式运行目录默认拒绝覆盖。重新实验必须新建数据版本或显式 rerun 名称。

## 限制和禁止用途

当前指标较低，尤其 D02 和小目标召回不足；公开数据存在类别不平衡、背景和域偏差。本模型不能识别 D01、D04、D05、二次封装，不能定位真实物流责任节点，也不能认定物流责任。模型输出必须人工复核。
