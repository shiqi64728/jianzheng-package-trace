# 外部类别映射 v0.1

机器可读配置：`configs/training/external-class-mapping-v0.1.json`。

## 1. 映射状态

- `direct`：原始语义可以直接进入对应项目类别候选，但仍需正常质量抽样；
- `candidate`：只能作为候选，必须人工批准；
- `general_only`：只保留一般完好/异常语义；
- `change_detection_only`：仅用于变化检测或表面归一化；
- `unmapped`：不映射项目损伤类别；
- `blocked`：证据不足，禁止进入训练。

## 2. defect-cardboard

| 原始类别 | 状态 | 项目类别 | 任务 | 人工审核 |
|---|---|---|---|---|
| `dent` | `direct` | D02 | damage_detection | 训练前抽样 |
| `hole` | `direct` | D03 | damage_detection | 训练前抽样 |
| `dirt` | `candidate` | D04候选 | damage_detection | 必须 |
| `defects-in-cardboards` | `unmapped` | 无 | research_only | 零标注类别 |

`dirt`可能包含普通污点、阴影或印刷，不等于受潮。成员C审核前不得成为正式D04。

COCO原始bbox完整保留在稳定annotation引用中。工具不创建polygon；一张图有多个bbox时不会丢失annotation。

## 3. Damaged Box Detection

| 原始类别 | 状态 | 项目类别 | 任务 |
|---|---|---|---|
| `undamagedpackages` | `general_only` | NORMAL | damage_binary_classification |
| `damagedpackages` | `general_only` | ABNORMAL_GENERAL | damage_binary_classification |

禁止从 `damagedpackages` 推导D01—D05。README说明导出包含旋转增强，但没有可靠父图映射，因此 `parent_or_augmented_from` 保持空值，不通过文件名猜测，也不把增强版本视作独立物理包裹。

## 4. TAMPAR

所有TAMPAR记录：

```text
mapped_project_status = change_detection_only
mapped_project_class = 空
project_task = change_detection 或 surface_normalization
```

COCO中实际标注的是normal box的bbox、真实polygon和keypoints。篡改图不自动获得项目D01—D05标签；732个normal box不会扩展成2,751个损伤标注。

配对状态：

- `confirmed`：必须有发布方或人工确认的逐图证据；
- `probable`：相同split和显式parcel id，按拍摄时间邻近选择参考图，仍需人工审核；
- `unresolved`：没有充分参考证据，进入隔离和审核清单。

reference/tampered不是N1/N2，不生成内部sequence或首次异常节点。

## 5. 国家邮政局统计

```text
mapped_project_status = unmapped
project_task = industry_statistics
```

统计记录只保留文章、日期、统计周期、指标、值、单位、同比、网址、抓取时间和原始HTML哈希。当前独立许可证/引用证据未登记完整，记录保持blocked，仅用于行业背景审核，不进入图像训练。

## 6. 首个基线建议

治理审计完成后优先考虑 **D02/D03目标检测**：

1. defect-cardboard没有已知精确重复；
2. bbox原始标注完整；
3. D02/D03与项目核心损伤类别直接相关；
4. 训练前排除 `dirt`，完成人工抽样和类别不平衡检查；
5. 冻结无跨split重复的数据版本后再开始下一轮训练。

二分类和TAMPAR变化检测仍是备选。当前不进行多任务融合，也不声称具备真实连续节点定位能力。