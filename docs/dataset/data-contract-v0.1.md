# 件证数据集输入合同与清单校验说明 v0.1

## 1. 使用目的与适用范围

本合同定义“件证——基于连续外观数字指纹的快递损伤异常节点定位与责任辅助认定系统”第一版数据输入接口。目标是在数据进入训练前，用统一 CSV 清单描述图片及其治理状态，并自动拦截字段、路径、隐私、标注、连续序列和数据划分问题。

本版只定义数据合同和只读校验流程：

- 不采集真实数据；
- 不修改、移动、重命名或删除图片；
- 不训练模型；
- 不下载模型权重；
- 不根据单张图片猜测首次异常节点；
- 不替代隐私人工检查和业务标注复核。

正式文件：

| 用途 | 路径 |
|---|---|
| 本文档 | `docs/dataset/data-contract-v0.1.md` |
| 空白模板 | `dataset/manifests/templates/manifest-v0.1.template.csv` |
| 虚拟示例 | `dataset/manifests/templates/manifest-v0.1.example.csv` |
| 机器可读合同 | `configs/training/manifest-schema-v0.1.json` |
| 校验器 | `scripts/dataset/validate_manifest.py` |

CSV 必须使用 UTF-8 或 UTF-8 with BOM。仓库提供的模板和示例使用 UTF-8 with BOM，便于 WPS/Excel 在中文 Windows 中打开。

## 2. 四类数据来源

`source_type` 必须是以下值之一：

| 值 | 含义 | 典型场景 |
|---|---|---|
| `field_normal` | 快递站真实完好包裹 | 成员 C 在合规条件下采集的真实正常样本 |
| `field_natural_damage` | 快递站偶然发现的真实破损包裹 | 非人为制造的自然破损样本 |
| `controlled_damage` | 团队制作的受控损伤 | 使用团队自有或授权纸箱制作的可控实验样本 |
| `continuous_node` | N1、N2、N3 连续节点序列 | 同一物理包裹跨连续节点采集的配对数据 |

`source_type=continuous_node` 表示该行属于连续节点接口。真实或受控来源背景可在批次说明和 `notes` 中记录，但不得把个人隐私写入 `notes`。

## 3. 字段总表

所有 21 个字段都必须出现在 CSV 表头中。除下表明确允许为空的字段外，每条记录都必须填写值。

| 字段 | 是否必填值 | 定义与要求 |
|---|---|---|
| `schema_version` | 是 | 本版固定为 `0.1` |
| `record_id` | 是 | 一条图片记录的全局唯一 ID；大小写不作为区分依据 |
| `package_id` | 是 | 同一个物理纸箱的稳定 ID；同一纸箱多张图片应重复使用同一 ID |
| `batch_id` | 是 | 一次数据提交批次的 ID |
| `sequence_id` | 条件必填 | `continuous_node` 必填；其他来源必须为空 |
| `source_type` | 是 | 四类数据来源之一 |
| `image_relpath` | 是 | 相对于 `--data-root` 的图片路径，只使用 `/` |
| `surface` | 是 | 包裹表面枚举 |
| `node_id` | 是 | 节点枚举；连续节点不得为 `NA` |
| `capture_time` | 是 | 包含时区的 ISO 8601 时间 |
| `device_id` | 是 | 采集设备匿名编号，不得写序列号或个人手机号 |
| `status` | 是 | `normal` 或 `abnormal` |
| `damage_type` | 是 | 损伤类型枚举 |
| `severity` | 是 | 严重程度枚举 |
| `first_abnormal_node` | 是 | 首次异常节点枚举 |
| `privacy_status` | 是 | 隐私审核状态 |
| `annotation_status` | 是 | 标注状态 |
| `split` | 是 | 数据划分 |
| `collector` | 是 | 采集成员匿名代号，例如 `C` |
| `reviewer` | 条件必填 | `annotation_status=reviewed` 时必填 |
| `notes` | 否 | 非敏感补充说明；不得写姓名、电话、地址、单号或凭据 |

`record_id`、`package_id`、`batch_id`、`sequence_id`、`device_id`、`collector` 和 `reviewer` 使用稳定英文标识：以字母或数字开头，后续只允许字母、数字、点、下划线和连字符，最大 128 个字符。

### 3.1 包裹 ID 的重复与冲突

同一 `package_id` 可以在多行中出现，因为一个物理纸箱可能有多个表面、节点或拍摄角度。以下情况才属于包裹 ID 冲突：

- 同一 `package_id` 出现在不同 `batch_id`；
- 同一 `package_id` 使用不同 `source_type`；
- 同一 `package_id` 跨 `train`、`val`、`test`；
- 团队确认它们实际是不同纸箱却复用了相同 ID。

校验器能够发现前三种情况。是否为不同物理纸箱仍需成员 C 和成员 A 人工核对。

## 4. 枚举值

### 4.1 表面

`surface`：

```text
FRONT
LEFT
RIGHT
TOP
BACK
BOTTOM
```

### 4.2 节点

`node_id`：

```text
N1
N2
N3
NA
```

非连续样本通常使用 `NA`。`continuous_node` 必须使用 `N1`、`N2` 或 `N3`。

### 4.3 状态、损伤类型与等级

`status`：

```text
normal
abnormal
```

`damage_type`：

| 值 | 含义 |
|---|---|
| `NONE` | 无损伤 |
| `D01` | 箱角挤压 |
| `D02` | 表面凹陷 |
| `D03` | 纸箱破口 |
| `D04` | 受潮污损 |
| `D05` | 胶带变化或疑似二次封装 |
| `MULTI` | 多种损伤并存 |

`severity`：

```text
none
light
medium
heavy
unknown
```

逻辑约束：

- `normal` 必须使用 `damage_type=NONE`；
- `normal` 必须使用 `severity=none`；
- `abnormal` 不得使用 `damage_type=NONE`；
- `abnormal` 不得使用 `severity=none`；
- 无法可靠确定异常等级时可以使用 `unknown`，但必须进入人工复核流程。

### 4.4 首次异常节点

`first_abnormal_node`：

```text
NONE
N1
N2
N3
UNKNOWN
```

规则：

- 非连续正常样本使用 `NONE`；
- 非连续异常样本可使用 `UNKNOWN`，不得使用 `NONE`；
- 连续序列的所有行必须填写一致的 `first_abnormal_node`；
- 完整 N1/N2/N3 序列不得使用 `UNKNOWN`；
- `first_abnormal_node=N2` 时，N1 不得已有异常记录，N2 至少应有一条异常记录；
- 序列全部正常时使用 `NONE`；
- 程序不得根据单张图片自动推断首次异常节点。

### 4.5 隐私状态

`privacy_status`：

```text
masked
not_applicable
rejected
pending_review
```

含义：

- `masked`：可能出现的姓名、电话、地址、运单条码等已完成脱敏；
- `not_applicable`：受控样本等经人工确认不存在隐私信息；
- `rejected`：发现隐私风险，拒绝进入接收清单；
- `pending_review`：等待隐私人工复核。

本校验器面向正式接收清单，因此只有 `masked` 和 `not_applicable` 可以通过。`rejected` 与 `pending_review` 会返回错误，必须返工。

尤其是 `field_normal` 和 `field_natural_damage`：

- 不得以 `pending_review` 进入正式清单；
- 不得以 `rejected` 进入任何可训练划分；
- 含未脱敏姓名、电话、地址、运单号或条码的图片必须拒绝；
- 即使 CSV 填写 `masked`，成员 A 仍必须抽查图片，校验器不能识别图片内全部隐私。

### 4.6 标注状态

`annotation_status`：

```text
unlabelled
labelled
reviewed
needs_review
```

规则：

- `train`、`val`、`test` 记录必须为 `labelled` 或 `reviewed`；
- `reviewed` 必须填写 `reviewer`；
- `unlabelled` 和 `needs_review` 只能暂存于 `unassigned`，完成后再进入训练划分。

### 4.7 数据划分

`split`：

```text
unassigned
train
val
test
```

`unassigned` 表示尚未进入正式训练、验证或测试集合。

## 5. 路径规则

`image_relpath` 必须：

- 相对于命令行 `--data-root`；
- 使用 `/`，不使用 `\`；
- 不包含 Windows 盘符；
- 不使用 UNC 路径；
- 不以 `/` 开头；
- 不包含 `..`、`.` 或空路径段；
- 解析后仍位于 `data-root` 内；
- 使用支持的图片扩展名：
  `.jpg`、`.jpeg`、`.png`、`.bmp`、`.tif`、`.tiff`、`.webp`。

合格：

```text
images/BATCH-202607/PKG-000001/N1_FRONT_001.jpg
```

不合格：

```text
E:\parcel\N1.jpg
\\server\share\N1.jpg
../private/N1.jpg
images\PKG-001\N1.jpg
/images/PKG-001/N1.jpg
```

开启 `--check-files` 后，校验器会：

1. 检查文件是否存在；
2. 使用 OpenCV 只读解码；
3. 把不存在、损坏、空内容或无法读取的图片记录为错误；
4. 不修改图片和 CSV。

## 6. 建议文件命名

推荐目录：

```text
<data-root>/
  manifest.csv
  images/
    <batch_id>/
      <package_id>/
        <record_id>_<node_id>_<surface>.<ext>
```

示例：

```text
images/BATCH-202607/PKG-000001/REC-000001_N1_FRONT.jpg
```

文件名只用于定位。真实身份、电话号码、地址、运单号、快递单条码和设备真实序列号不得进入文件名。

## 7. 包裹级数据划分与防泄漏

划分必须先按物理包裹分组，再决定 `train`、`val` 或 `test`：

- 同一 `package_id` 的所有图片只能进入一个正式集合；
- 不得把同一纸箱的不同表面分到不同集合；
- 不得把同一纸箱的不同拍摄时间分到不同集合；
- 同一 `sequence_id` 的 N1/N2/N3 必须进入同一集合；
- `unassigned` 不属于正式训练集合，应在分配完成后重新校验；
- 数据划分变更必须以整个 `package_id` 和整个 `sequence_id` 为单位。

校验器会对 `package_id` 和 `sequence_id` 分别检查跨集合泄漏。

## 8. 连续节点序列规则

`source_type=continuous_node` 时：

- `sequence_id` 必填；
- `node_id` 必须为 `N1`、`N2` 或 `N3`；
- 一个序列必须同时包含 N1、N2、N3；
- 同一序列只能对应一个 `package_id`；
- 同一序列所有行必须使用相同 `split`；
- 同一序列所有行的 `first_abnormal_node` 必须一致；
- 同一序列的相同 `node_id + surface` 不得重复；
- 已知完整序列必须填写真实首次异常节点；
- 不能因为某个表面在 N3 看起来正常，就覆盖同一节点其他表面已确认的异常。

非连续记录不得填写 `sequence_id`。

## 9. 合格记录示例

以下是单行示意；正式 CSV 使用文档定义的完整表头：

```csv
0.1,REC-EX-FD-001,PKG-EX-FD-001,BATCH-EX-001,,field_natural_damage,images/example/PKG-EX-FD-001_TOP.jpg,TOP,NA,2026-07-01T09:05:00+08:00,DEVICE-EX-01,abnormal,D03,medium,UNKNOWN,masked,reviewed,val,C,A,EXAMPLE_ONLY_DO_NOT_USE
```

它满足：

- 版本正确；
- ID 格式有效；
- 使用相对路径；
- 异常样本有损伤类型和等级；
- 非连续异常样本使用 `UNKNOWN`；
- 隐私和标注已通过；
- reviewer 已填写。

仓库中的 `manifest-v0.1.example.csv` 包含四类来源和一个完整 N1/N2/N3 虚拟序列。所有路径和 ID 都是虚构的，不对应真实数据。

## 10. 不合格记录示例

```csv
0.1,REC-BAD-001,PKG-BAD-001,BATCH-BAD-001,,field_normal,E:\private\parcel.jpg,FRONT,NA,2026-07-01 09:00,PHONE-13800000000,normal,D01,medium,NONE,pending_review,reviewed,train,张三,,真实地址
```

该行至少存在：

- 使用绝对路径；
- 时间不含时区；
- 设备字段疑似包含隐私；
- 正常样本错误填写损伤类型和等级；
- 隐私仍待审核；
- reviewed 未填写 reviewer；
- collector 和 notes 包含个人信息风险。

校验器可发现结构化规则错误，但个人信息语义仍需人工复核。

## 11. 模板与示例的使用方式

正式批次应：

1. 复制 `manifest-v0.1.template.csv` 到批次数据根目录并改名为 `manifest.csv`；
2. 不要把 `manifest-v0.1.example.csv` 当作正式清单；
3. 示例文件仅用于学习字段和值，正式清单不得保留 `REC-EX-*` 示例行；
4. 保持表头名称和顺序不变；
5. 不要用 Excel/WPS 自动把 ID 转为数字或科学计数法；
6. 保存为 UTF-8 CSV。

示例文件中的图片路径是虚拟路径，因此可用于不带 `--check-files` 的结构验证；不能用它证明图片存在。

## 12. 成员 C 交付流程

1. 为本次提交创建唯一 `batch_id`。
2. 给每个物理纸箱分配稳定 `package_id`。
3. 连续节点数据给整个 N1/N2/N3 组分配唯一 `sequence_id`。
4. 完成图片脱敏，人工确认姓名、电话、地址和条码不可识别。
5. 按模板填写所有字段；不把真实隐私写入文件名或 `notes`。
6. 将图片放在批次 `data-root` 内，并填写相对路径。
7. 使用正式解释器运行校验器，必须开启 `--check-files`。
8. 退出码不为 0 时，根据 JSON 报告返工。
9. 将 CSV、JSON 验证报告和数据批次通过团队批准的非 Git 方式交给成员 A。
10. 原始图片、标注输出和验证报告不得提交到 Git。

命令示例：

```powershell
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" `
  "E:\Artificial-intelegence-training\scripts\dataset\validate_manifest.py" `
  --manifest "E:\某批次\manifest.csv" `
  --data-root "E:\某批次" `
  --schema "E:\Artificial-intelegence-training\configs\training\manifest-schema-v0.1.json" `
  --check-files `
  --report "E:\某批次\validation-report.json"
```

## 13. 成员 A 接收验收流程

1. 核对批次交付渠道和 `batch_id`，不得直接信任成员 C 的本地路径。
2. 在隔离的接收目录解压或复制批次，不覆盖已有数据。
3. 使用成员 A 本机上的正式合同和校验器重新运行 `--check-files`。
4. 比对总记录、通过记录、失败记录、错误数和警告数。
5. 任何错误都必须退回返工。
6. 警告必须逐项人工复核；不能静默忽略额外列或首尾空白。
7. 抽查脱敏、损伤类型、等级和首次异常节点，避免“结构合格但语义错误”。
8. 按 `package_id` 和 `sequence_id` 重新确认数据划分。
9. 验收通过后才能进入后续训练数据准备流程。

## 14. 退出码与 JSON 报告

| 退出码 | 含义 |
|---:|---|
| 0 | 清单验证通过；可能仍有需人工复核的警告 |
| 1 | 清单或图片数据验证失败 |
| 2 | 参数、路径、合同配置或程序使用错误 |
| 3 | 非预期内部错误；控制台会保留异常类型和堆栈 |

JSON 报告包含：

- 校验器版本和生成时间；
- 清单、数据根目录和合同路径；
- 是否启用文件检查；
- 总记录数；
- 通过记录数；
- 失败记录数；
- 错误数；
- 警告数；
- 每个问题的严重度、错误代码、CSV 行号、`record_id`、字段和中文说明。

校验器不会自动修复 CSV。修正必须在源清单中人工完成，然后重新验证。

## 15. 当前自动检查项目

- 空清单和缺少表头；
- 必需列缺失、表头重复和额外列警告；
- 必填值为空；
- schema 版本；
- ID 格式；
- 所有枚举；
- 时间格式和时区；
- 绝对路径、UNC、盘符、反斜杠、`..`、非规范路径和根目录逃逸；
- 图片扩展名；
- `record_id` 重复；
- `image_relpath` 重复；
- 包裹 ID 跨批次或来源冲突；
- 正常/异常与损伤类型、等级的逻辑；
- 连续数据缺少 `sequence_id` 或使用 `node_id=NA`；
- 非连续记录错误填写 `sequence_id`；
- 隐私状态不合格；
- 标注状态不合格和 reviewer 缺失；
- 同一包裹跨 train/val/test；
- 同一序列跨 train/val/test；
- 序列对应多个包裹；
- 连续序列缺少 N1/N2/N3；
- 同一序列节点/表面槽位重复；
- 首次异常节点冲突、不一致或与状态不匹配；
- 开启 `--check-files` 时的图片不存在和 OpenCV 解码失败。

## 16. 必须人工检查的限制

v0.1 不能自动证明：

- 两个不同 `package_id` 是否实际属于同一物理纸箱；
- 图片内容是否真的完成全部隐私脱敏；
- 损伤类型和严重程度是否符合业务事实；
- 图片是否经过不当编辑；
- 同一图片换文件名后是否为内容重复；
- `collector`、`reviewer` 和 `device_id` 是否由团队授权；
- 单张图片能否证明首次异常节点。

这些项目必须由成员 C、成员 A 和后续数据审核流程共同完成。

## 17. 合同版本变更规则

- `schema_version` 使用语义化的主次版本思想，本版为 `0.1`。
- 只修正文档措辞且不改变字段或校验行为时，可以保留 `0.1`。
- 新增可选字段、枚举或警告时，至少升级次版本。
- 删除/重命名字段、改变字段含义或收紧会导致旧清单失败的规则时，必须发布新合同文件和迁移说明。
- 旧合同、旧模板和旧校验器不得被静默覆盖。
- 一个 CSV 清单只能声明一个 `schema_version`。
- 合同变更必须同步更新：
  - 文档；
  - 机器可读 JSON；
  - 模板与示例；
  - 校验器；
  - 自动测试；
  - 项目反馈记录。
