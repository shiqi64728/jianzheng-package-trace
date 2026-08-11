# D02/D03 YOLO26n 输入分辨率单变量实验 v0.1

## 实验合同

本实验只将训练输入尺寸从 `640` 提高到 `960`。模型仍为 YOLO26n，初始化仍为同一个官方 `yolo26n.pt`，冻结数据、split、seed、epochs、patience、optimizer、增强默认值、AMP 和其他训练参数均未改变。配置差异审计没有发现非许可差异。

- 实验 ID：`d02-d03-yolo26n-imgsz960-v0.1`；
- 数据版本：`detect-d02-d03-v0.1`；
- dataset-lock SHA-256：`6d496281ade6486434c0eb85a473b2bd3e8e5574bcc51ca1d371895851ea6e97`；
- 预训练权重 SHA-256：`9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`；
- candidate 从官方预训练权重开始，没有从 640 best.pt 继续训练；
- candidate test 未访问，模型选择和对比只使用 val。

## GT 目标尺寸

11,304 个 GT bbox 的归一化面积 Q25/Q50/Q75 分别为 `0.00228470 / 0.00456177 / 0.00941772`。按整体面积分位数划分后，每个 quartile 均为 2,826 个框。

最小四分位中：

- D02：2,003；D03：823；
- 640 投影平均宽×高约 `26.32×25.65 px`；
- 960 投影平均宽×高约 `39.48×38.48 px`。

D02 自身面积 Q25/Q50/Q75 为 `0.00255371 / 0.00479309 / 0.00966171`；D03 为 `0.00133240 / 0.00260376 / 0.00806259`。D03 的面积分布整体更小，且 1,790 个 D03 框中有 823 个落入整体最小四分位。

## 训练前诊断

640 baseline best.pt 在 val、imgsz 640 上逐值复现上一轮指标：

| 设置 | Precision | Recall | mAP50 | mAP50-95 | inference ms/image |
| --- | ---: | ---: | ---: | ---: | ---: |
| baseline best @640 | 0.331108 | 0.242798 | 0.193225 | 0.083132 | 6.471 |
| baseline best @960，仅推理 | 0.301011 | 0.234115 | 0.178323 | 0.068943 | 8.025 |

只提高旧模型的推理分辨率没有改善结果，因此 960 的效果必须由重新训练验证，不能把纯推理变化当成新模型收益。

## Smoke 与正式训练

960 smoke 完成 3/3 epoch，实际 batch 4，无 OOM、NaN/Inf，AMP、checkpoint 和 validation 均通过。

正式训练参数为 100 epoch、patience 25、batch -1、device 0、workers 4、cache false、seed 42、deterministic true、optimizer auto、pretrained true、AMP true。结果：

- 实际 batch：3；
- 实际 epoch：100；
- early stop：否；
- best epoch：99；
- 总耗时：2,747.331 秒，约 45 分 47 秒；
- 平均 epoch：27.473 秒；
- `torch.cuda.max_memory_allocated` 峰值：10,620,080,640 字节。

显存峰值包含 AutoBatch 探测。Windows WDDM 可以用共享内存支持部分分配，因此该数字可高于 8,151 MiB 独立显存，不能解释为稳定训练阶段一直占用 9.89 GiB；正式 epoch 日志显示的训练阶段 GPU memory 约在 1.25–1.81 GiB 范围。为与 640 基线一致，正式成本表仍保留相同 PyTorch 峰值口径。

## Candidate val 指标

| 类别 | Precision | Recall | AP50 | AP50-95 |
| --- | ---: | ---: | ---: | ---: |
| overall | 0.358709 | 0.261359 | 0.221814 | 0.094648 |
| D02 | 0.289831 | 0.203753 | 0.138476 | 0.040010 |
| D03 | 0.427588 | 0.318966 | 0.305152 | 0.149285 |

last.pt 的总体 val 为 Precision 0.332003、Recall 0.269789、mAP50 0.223085、mAP50-95 0.093839。本实验候选仍使用 best.pt。

## 640 → 960 变化

| 指标 | 640 | 960 | 绝对变化 | 相对变化 |
| --- | ---: | ---: | ---: | ---: |
| 总体 Precision | 0.331108 | 0.358709 | +0.027601 | +8.336% |
| 总体 Recall | 0.242798 | 0.261359 | +0.018561 | +7.645% |
| 总体 mAP50 | 0.193225 | 0.221814 | +0.028589 | +14.796% |
| 总体 mAP50-95 | 0.083132 | 0.094648 | +0.011516 | +13.852% |
| D02 Precision | 0.292472 | 0.289831 | -0.002642 | -0.903% |
| D02 Recall | 0.192493 | 0.203753 | +0.011260 | +5.850% |
| D02 AP50 | 0.131522 | 0.138476 | +0.006954 | +5.287% |
| D02 AP50-95 | 0.037191 | 0.040010 | +0.002819 | +7.581% |
| D03 Precision | 0.369744 | 0.427588 | +0.057844 | +15.644% |
| D03 Recall | 0.293103 | 0.318966 | +0.025862 | +8.824% |
| D03 AP50 | 0.254927 | 0.305152 | +0.050225 | +19.702% |
| D03 AP50-95 | 0.129074 | 0.149285 | +0.020212 | +15.659% |

代价：实际 batch `8→3`；总训练时间 `1,180.176→2,747.331 秒`（+132.790%）；平均 epoch 同比 +132.790%；val inference `6.471→8.191 ms/image`（+26.578%）。权重大小只增加 65,536 字节。

## 失败关联与对比

上一轮公开的 413/478/125 等失败数量来自 test，不可用于本轮 candidate 选择。本轮没有读取这些 test prediction；而是对同一 val、同一匹配逻辑重新生成 640 和 960 失败记录，并用 `image_relpath + label_index` 可靠关联到 GT bbox。

| 失败类型 | 640 val | 960 val | 变化 |
| --- | ---: | ---: | ---: |
| low IoU | 842 | 817 | -25（-2.969%） |
| smallest-quartile failure | 226 | 226 | 0 |
| high-confidence false positive | 89 | 52 | -37（-41.573%） |
| D02/D03 confusion | 24 | 24 | 0 |
| missed detection | 221 | 180 | -41（-18.552%） |

最小四分位总体失败率在两模型中均为 `226/285 = 79.298%`，没有改善；D02 最小四分位失败率反而由 80.242% 升至 82.258%。改善主要出现在 q3、最大四分位、漏检和高置信假阳性。因此本轮证明了总体 val 和 D02/D03 指标改善，但没有证明最小目标问题得到解决。

960 best 混淆矩阵中背景相关错误为 `263+16+1606+83=1,968`，640 为 1,989，减少 21；正确类别分配由 285 增至 287，D02/D03 跨类混淆由 1 增至 5。

## 制品与结论

- 比较目录：`E:/JianZhengData/training/comparisons/d02-d03-yolo26n-640-vs-960-v0.1`；
- candidate 目录：`E:/JianZhengData/models/experiments/d02-d03-yolo26n-imgsz960-v0.1`；
- candidate best.pt SHA-256：`2dd857412b63df66d1273b326dc51afaed895da1d360c97e184762c882181a97`；
- 20 张固定 val 样例均包含 GT、640 和 960 三份可视化；
- raw 与 dataset-lock 管理的冻结文件前后不变；Ultralytics 派生 `.cache` 不属于 dataset-lock，不计入冻结内容树；
- 当前正式 release 仍是 `d02-d03-yolo26n-baseline-v0.1`，未被覆盖。

推荐：**PROMOTE_FOR_TEST**。原因是总体 mAP50-95、D02 AP50-95、D02 Recall 和全部 D03 指标均改善，满足优先指标；但该建议只表示可以由用户批准后执行一次正式 test，不是自动晋级。960 candidate 本轮未访问 test。

## 复现命令

```powershell
& $python scripts/training/analyze_d02_d03_object_sizes.py --dataset-root E:/JianZhengData/training/detect-d02-d03-v0.1 --output-dir E:/JianZhengData/training/comparisons/d02-d03-yolo26n-640-vs-960-v0.1
& $python scripts/training/compare_d02_d03_experiments.py --config configs/training/experiments/d02-d03-yolo26n-imgsz960-v0.1.json --mode snapshot-pre
& $python scripts/training/compare_d02_d03_experiments.py --config configs/training/experiments/d02-d03-yolo26n-imgsz960-v0.1.json --mode diagnose
& $python scripts/training/train_d02_d03_baseline.py --config configs/training/experiments/d02-d03-yolo26n-imgsz960-v0.1.json --mode smoke
& $python scripts/training/train_d02_d03_baseline.py --config configs/training/experiments/d02-d03-yolo26n-imgsz960-v0.1.json --mode train
& $python scripts/training/compare_d02_d03_experiments.py --config configs/training/experiments/d02-d03-yolo26n-imgsz960-v0.1.json --mode evaluate
& $python scripts/training/compare_d02_d03_experiments.py --config configs/training/experiments/d02-d03-yolo26n-imgsz960-v0.1.json --mode snapshot-post
```

所有固定输出默认拒绝覆盖。重复实验必须使用新的实验 ID 和目录，不能删除或覆盖本轮结果后静默重跑。
