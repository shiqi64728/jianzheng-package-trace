# 图像质量自动审计 v0.1

## 1. 用途

本工具在数据进入标注或训练准备之前，自动筛查图片可读性、分辨率、比例、模糊候选、曝光候选、批次尺寸离群和精确重复内容。

它首先直接调用第一轮 `validate_manifest.validate_manifest()`。第一轮 21 字段、枚举、路径、隐私、数据划分和连续节点规则没有复制、没有修改，原 CLI、错误代码和退出码保持不变。只有第一轮结构验证无错误时，才读取图片并计算质量指标。

本轮没有修改 `scripts/dataset/validate_manifest.py`。

工具还会自动读取 `data-root\batch-info.json`，检查稳定字段、必填值、带时区时间、设备与拍摄参数完整性，以及 `batch_id`、`source_type`、`collector`、`device_id` 是否与 manifest 一致。它只核对人工填写的元数据，不从图片推断设备、隐私或授权事实。

## 2. 运行命令

```powershell
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" `
  "E:\Artificial-intelegence-training\scripts\dataset\audit_image_quality.py" `
  --manifest "E:\JianZhengData\incoming\BATCH-PILOT-001\manifest.csv" `
  --data-root "E:\JianZhengData\incoming\BATCH-PILOT-001" `
  --schema "E:\Artificial-intelegence-training\configs\training\manifest-schema-v0.1.json" `
  --quality-config "E:\Artificial-intelegence-training\configs\training\image-quality-v0.1.json" `
  --report-json "E:\JianZhengData\incoming\BATCH-PILOT-001\reports\quality-report.json" `
  --report-csv "E:\JianZhengData\incoming\BATCH-PILOT-001\reports\quality-report.csv" `
  --check-files
```

`--check-files` 必须显式提供。未提供时返回退出码 `2`，且不会读取图片；只需要结构检查时应运行第一轮校验器。

退出码：

| 退出码 | 含义 |
| --- | --- |
| `0` | `PASS` 或 `PASS_WITH_WARNINGS`；只有 WARN 时仍为 `0` |
| `1` | manifest 数据错误、不可读图片或记录级质量 FAIL |
| `2` | CLI、schema、阈值配置或报告路径错误 |
| `3` | 非预期内部错误 |

## 3. 每张图片的指标

报告至少包括：

```text
record_id
image_relpath
sha256
file_size_bytes
width
height
channels
aspect_ratio
mean_gray
std_gray
laplacian_variance
underexposed_ratio
overexposed_ratio
readable
quality_status
quality_flags
quality_messages
```

工具使用原始文件字节计算 SHA-256，再由 OpenCV 在内存中解码；不记录图片二进制或 Base64，不修改原图。

可读性要求：

- 文件存在且是普通文件；
- 文件不是 0 字节；
- OpenCV 能够解码；
- 图片数组非空；
- 宽高大于 0；
- 通道数为 1、3 或 4。

失败统一保留 `record_id` 和相对路径，标记 `UNREADABLE_IMAGE`，批次为 `FAIL`。

## 4. 工程初始阈值

配置文件为 `configs/training/image-quality-v0.1.json`。这些值只是**第一版工程初始值**，没有经过真实快递数据验证：

| 配置 | 初始值 | 作用 |
| --- | ---: | --- |
| `min_width` | `640` | 最低宽度，低于时 FAIL |
| `min_height` | `480` | 最低高度，低于时 FAIL |
| `allowed_aspect_ratio_min` | `0.5` | 最小长宽比 |
| `allowed_aspect_ratio_max` | `2.0` | 最大长宽比 |
| `blur_warn_below` | `100.0` | 模糊候选阈值 |
| `blur_fail_below` | `20.0` | 严重模糊候选阈值 |
| `underexposed_pixel_max` | `20` | 暗像素上界 |
| `overexposed_pixel_min` | `235` | 亮像素下界 |
| `mean_gray_warn_low` | `45.0` | 整体偏暗候选 |
| `mean_gray_warn_high` | `210.0` | 整体偏亮候选 |
| `underexposed_ratio_warn` | `0.35` | 欠曝面积候选比例 |
| `overexposed_ratio_warn` | `0.35` | 过曝面积候选比例 |
| `resolution_outlier_min_batch_size` | `4` | 开始判断尺寸离群的最小批次数 |
| `resolution_outlier_max_fraction` | `0.25` | 少数尺寸占比上限 |

所有状态级别也在配置中集中定义。配置缺字段、类型错误、范围错误或阈值次序错误时明确返回退出码 `2`。

正式阈值必须根据成员 C 的首批 20—50 张完全脱敏图片重新校准。

## 5. 质量标记

| 标记 | 默认状态 | 说明 |
| --- | --- | --- |
| `UNREADABLE_IMAGE` | FAIL | 不存在、不是普通文件、0 字节或 OpenCV 无法解码 |
| `LOW_RESOLUTION` | FAIL | 宽或高低于最低值 |
| `EXTREME_ASPECT_RATIO` | WARN | 长宽比位于配置范围外 |
| `POSSIBLE_BLUR` | WARN | Laplacian 方差低于候选阈值 |
| `SEVERE_BLUR` | FAIL | Laplacian 方差低于严重候选阈值 |
| `POSSIBLE_UNDEREXPOSURE` | WARN | 灰度均值或暗像素比例触发 |
| `POSSIBLE_OVEREXPOSURE` | WARN | 灰度均值或亮像素比例触发 |
| `DUPLICATE_CONTENT` | WARN | 不同记录和路径的原始字节 SHA-256 相同 |
| `RESOLUTION_OUTLIER` | WARN | 同批次中属于少数尺寸 |

同一图片的全部标记都会保留，不会只保留最后一个。

纯色纸箱可能天然获得很低的 Laplacian 方差；深色纸箱可能触发欠曝候选；浅色或反光包装可能触发过曝候选。因此模糊和曝光结果只是筛查依据，不是“已经确认模糊”或“拍摄错误”的业务结论。

## 6. 精确重复内容

工具对原始文件字节计算 SHA-256。如果不同 `record_id`、不同 `image_relpath` 的 SHA-256 完全相同，则产生 `DUPLICATE_CONTENT`，并生成：

```text
duplicate_group_id
sha256
record_ids
image_relpaths
```

SHA-256 只能发现字节完全相同的内容。裁剪、重新编码、压缩或轻微修改后的重复图片不会被发现。本轮不做感知哈希，也不会删除、移动或修改重复文件。

## 7. 报告

JSON 报告包含批次状态、记录统计、可读性统计、分辨率分组、亮度摘要、模糊摘要、重复组、第一轮 manifest 验证摘要和逐图结果。

`batch_info_validation` 另外记录：

- 缺失或无法读取的 `batch-info.json`；
- 必填字段缺失或为空；
- 设备、镜头、分辨率、比例、HDR、滤镜、光照或背景记录不完整；
- manifest 与批次元数据不一致；
- `permission_status=pending` 或 `privacy_method=pending_manual_review` 的人工复核提醒。

CSV 报告：

- 每张图片一行；
- 使用 UTF-8 BOM；
- 多个标记用 `|` 分隔；
- 只记录 `image_relpath`，不记录真实绝对图片路径；
- 不包含图片、Base64 或个人隐私字段。

报告路径不得与 manifest、schema、质量配置或任何原始图片相同，避免误覆盖输入。

## 8. 状态解释

- `PASS`：没有记录级 WARN/FAIL，也没有第一轮结构警告。
- `PASS_WITH_WARNINGS`：至少有 WARN，但没有 FAIL；退出码仍为 `0`，必须人工抽查。
- `FAIL`：第一轮结构错误或至少一张图片为 FAIL；退出码为 `1`。

## 9. 隐私、授权和业务边界

> 隐私和授权字段是人工声明，不是图像质量工具自动识别结果。

自动工具不能：

- 证明图片已经完全脱敏；
- 判断是否取得快递站授权；
- 判断纸箱是否真实受潮；
- 确认损伤类别是否语义正确；
- 代替人工抽查。

测试只允许使用程序生成的合成图片，不得使用真实快递图片。

## 10. 成员 A 验收流程

```text
接收批次
→ 校验压缩包或传输完整性
→ 运行第一轮 manifest 验证
→ 运行第二轮图像质量审计
→ 查看所有 FAIL
→ 人工抽查 WARN
→ 返回补采或修正清单
→ 合格后才进入数据版本
```
