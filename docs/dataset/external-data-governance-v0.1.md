# 公开外部数据治理 v0.1

## 1. 目标与边界

本治理层回答外部图片的来源、许可证、原任务、原类别、项目映射、人工审核、重复、split泄漏和训练用途。它与内部21字段物流manifest完全分离，不生成或推断 `package_id`、`sequence_id`、`node_id`、`capture_time`、`first_abnormal_node`。

治理流程只读访问：

```text
E:\JianZhengData\external\raw
E:\JianZhengData\external\public-stats\spb\raw-html
E:\JianZhengData\external\registry\licenses
E:\JianZhengData\external\registry\citations
```

派生清单和报告只能写入 `converted`、`quarantine` 和 `reports`。工具不联网、不下载、不登录Roboflow、不复制图片、不修改原始标签，也不训练模型。

## 2. 数据用途边界

| 来源 | 允许的候选用途 | 禁止推断 |
|---|---|---|
| `defect-cardboard` | `dent`/D02和`hole`/D03 bbox检测；`dirt`/D04候选审核 | bbox不得伪造成polygon；`dirt`不得自动批准为受潮 |
| Damaged Box Detection | 完好/损伤二分类、负样本和一般异常候选 | `damagedpackages`不得拆成D01—D05；增强图不是独立物理包裹 |
| TAMPAR | reference/tampered配对研究、变化检测、polygon/keypoints/uvmap表面归一化 | 不得伪造成N1/N2、内部sequence或责任节点 |
| 国家邮政局统计 | 行业背景、业务量和收入展示 | 不进入图像训练manifest |

公开数据不能证明真实物流节点责任。真实连续节点定位必须使用少量自有或明确授权包裹，按预先定义的N1/N2/N3流程采集。

## 3. 外部schema

机器可读合同：`configs/training/external-source-schema-v0.1.json`。

- 主键为 `external_record_id`；
- 所有文件路径相对于 `E:\JianZhengData\external` 并使用 `/`；
- COCO图像使用图像级记录，所有原始annotation通过稳定 `annotation_ref` 保存在 `annotation_records_json`；
- TAMPAR额外保留 `pair_id`、reference/tampered路径、原始操作类型和配对置信状态；
- statistics记录不设置图片路径；
- 缺少许可证证据的来源保持 `blocked`。

模板位于 `dataset/external/templates`，仅含表头或虚拟示例，不包含真实外部数据。

## 4. 来源登记验证

```powershell
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" `
  "E:\Artificial-intelegence-training\scripts\dataset\validate_external_registry.py" `
  --source-registry "E:\JianZhengData\external\registry\source-registry-v0.1.csv" `
  --licenses-dir "E:\JianZhengData\external\registry\licenses" `
  --citations-dir "E:\JianZhengData\external\registry\citations" `
  --external-schema "E:\Artificial-intelegence-training\configs\training\external-source-schema-v0.1.json" `
  --external-root "E:\JianZhengData\external" `
  --report "E:\JianZhengData\external\reports\external-registry-validation-v0.1.json"
```

退出码：`0`通过、`1`登记内容错误、`2`参数/配置错误、`3`内部错误。验证器默认只读且不联网补齐证据。

## 5. 清单构建

```powershell
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" `
  "E:\Artificial-intelegence-training\scripts\dataset\build_external_manifests.py" `
  --external-root "E:\JianZhengData\external" `
  --source-registry "E:\JianZhengData\external\registry\source-registry-v0.1.csv" `
  --external-schema "E:\Artificial-intelegence-training\configs\training\external-source-schema-v0.1.json" `
  --class-mapping "E:\Artificial-intelegence-training\configs\training\external-class-mapping-v0.1.json" `
  --output-dir "E:\JianZhengData\external\converted\manifests" `
  --report "E:\JianZhengData\external\reports\external-manifest-build-v0.1.json"
```

生成四类清单。真实清单位于Git仓库之外，不提交Git。

TAMPAR真实数据缺少发布方逐图pair id。本版只能使用目录中的split、显式parcel `id_##` 和拍摄时间邻近规则产生 `probable` 配对；缺少同parcel参考图时为 `unresolved`。本版不生成 `confirmed`，必须由成员C审核。

## 6. 审计和隔离

```powershell
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" `
  "E:\Artificial-intelegence-training\scripts\dataset\audit_external_datasets.py" `
  --external-root "E:\JianZhengData\external" `
  --manifests-dir "E:\JianZhengData\external\converted\manifests" `
  --source-registry "E:\JianZhengData\external\registry\source-registry-v0.1.csv" `
  --class-mapping "E:\Artificial-intelegence-training\configs\training\external-class-mapping-v0.1.json" `
  --report-dir "E:\JianZhengData\external\reports"
```

审计器重新检查相对路径、文件存在性、可读性、尺寸、SHA-256、annotation引用、许可证、类别映射、数据集内重复、跨数据集重复、跨split重复和标签冲突。它只生成隔离清单，不移动或删除任何原文件。

跨split或标签冲突重复是训练阻塞项。同split同类别精确重复只记录，在冻结训练候选前按组处理。

## 7. 成员C审核工作清单

```powershell
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" `
  "E:\Artificial-intelegence-training\scripts\dataset\build_external_review_worklist.py" `
  --manifests-dir "E:\JianZhengData\external\converted\manifests" `
  --report-dir "E:\JianZhengData\external\reports\review-worklists" `
  --seed "jianzheng-external-review-v0.1"
```

工作清单使用SHA-256稳定排序，输入行顺序变化不影响抽样。CSV为UTF-8 BOM，只写相对路径和审核问题，不复制图片、不自动填写结论。

## 8. 许可证边界

- 每个训练候选来源必须保存许可证副本和引用文件；
- 比赛材料、训练元数据、报告和派生发布按许可证要求署名；
- 工具仅总结本地证据，不凭空解释条款，也不提供法律意见；
- “网页可以访问”不等于可以任意再利用；
- 许可证、引用或来源登记不足时保持 `review_required` 或 `blocked`；
- 国家邮政局统计当前未在source registry保存独立许可证/引用证据，因此只作为行业背景并保持blocked，不进入训练。

## 9. 进入训练候选的条件

```text
来源可追溯
许可证证据完整
文件完整
标签语义明确
类别映射获准
没有跨split精确重复
任务类型匹配
人工审核要求已满足
```

本轮只治理数据，不训练、下载权重或导出ONNX。