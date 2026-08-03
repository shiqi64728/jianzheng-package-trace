# 试采集批次工作流 v0.1

> **当前数据路线说明**：本项目已调整为以公开数据集和公开资料作为主要训练数据来源。本流程不再承担大规模人工采集，而仅用于 D01、D05、明确受潮等类别缺口补拍，少量 N1/N2/N3 连续节点验证，现场演示数据，以及公开数据真实性和域差异对照。公开数据不得伪造成真实物流节点数据。

> 成员 C 第一次填写 21 字段或不清楚如何批量导入图片时，请先阅读 `docs/dataset/member-c-collection-guide-v0.1.md`。该手册逐字段解释了现实含义、信息来源、成员 C 与成员 A 的分工，以及“一张图片一行”的批量导入方法。

## 1. 目标与边界

本工作流用于成员 C 接到明确的补缺采集、连续节点验证或演示数据任务后，建立统一、可核验且默认不覆盖的批次目录。每批数量由已确认的数据缺口决定，应优先使用少量自有或明确授权纸箱和完全脱敏样本，不设为了凑规模而拍摄的数量目标。

本工具不会：

- 生成虚假图片或清单记录；
- 采集摄像头画面；
- 修改、裁剪、重编码、移动或删除原图；
- 自动判断是否获得授权；
- 自动识别姓名、手机号、地址、运单号、人脸或站点信息；
- 创建正式训练集或训练模型。

`privacy_status` 与 `permission_status` 都是人工声明，必须人工复核。

## 2. 初始化命令

先由成员 A 或成员 C 明确创建一个批次输出根目录，再运行：

```powershell
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" `
  "E:\Artificial-intelegence-training\scripts\dataset\init_pilot_batch.py" `
  --output-root "E:\JianZhengData\incoming" `
  --batch-id "BATCH-PILOT-001" `
  --source-type "field_normal" `
  --collector "MEMBER-C" `
  --device-id "PHONE-C-001"
```

要求：

- `output-root` 必须是已经存在的绝对目录；
- `batch-id`、`collector`、`device-id` 使用稳定 ID，不填写人员姓名；
- `batch-id` 不允许包含 `..`、路径分隔符、盘符、绝对路径或 UNC 路径；
- 同名批次存在时直接拒绝，不提供覆盖参数；
- `source-type` 直接复用数据合同 v0.1 的四个来源枚举；
- 未明确提供 `permission-status` 时固定写为 `pending`，绝不自动写为 `approved`。

退出码：

| 退出码 | 含义 |
| --- | --- |
| `0` | 初始化成功 |
| `1` | 输入错误或同名批次冲突 |
| `2` | 第一轮 schema、模板或配置错误 |
| `3` | 非预期内部错误 |

## 3. 标准目录

```text
BATCH-PILOT-001\
├─ images\
├─ annotations\
├─ setup_photos\
├─ reports\
├─ manifest.csv
├─ batch-info.json
├─ README-COLLECTION.txt
└─ SHA256SUMS.txt
```

- `images/`：保留原始测试图片。
- `annotations/`：预留目录；本轮不建立标注工具。
- `setup_photos/`：只允许完全脱敏的布置参考图。
- `reports/`：存放校验和质量审计报告。
- `manifest.csv`：逐图填写数据合同 v0.1 记录。
- `batch-info.json`：人工记录本批次设备与拍摄参数。
- `README-COLLECTION.txt`：批次内操作提醒。
- `SHA256SUMS.txt`：初始化文件的 SHA-256，不是图片哈希清单。

`manifest.csv` 直接复制第一轮 UTF-8 BOM 模板，只含 21 字段表头，不建立第二套字段。

## 4. batch-info.json

稳定字段为：

```text
batch_schema_version
manifest_schema_version
batch_id
source_type
collector
device_id
created_at
purpose
location_type
permission_status
privacy_method
camera_or_phone_model
lens
resolution_setting
aspect_ratio_setting
hdr_status
filter_status
lighting
background
notes
```

其中：

- `manifest_schema_version` 固定引用 `0.1`；
- `created_at` 是包含时区的 ISO 8601 时间；
- `permission_status` 默认是 `pending`；
- `collector` 和 `device_id` 是项目稳定 ID；
- 不得在任何字段写入真实站点名称、人员姓名、手机号、详细地址、运单号、Token、Cookie 或其他凭据。

工具只保存命令行明确提供的批次元数据，不从系统、浏览器、图片或网络中自动提取隐私和授权信息。

## 5. 成员 C 的定向补采与验证要求

只有在公开数据审核确认存在缺口，或项目需要少量真实连续节点验证时，才下达人工采集任务。每次任务应明确目标类别、包裹范围、节点定义和验收数量。建议：

- 仅使用满足任务所需的少量自有或明确授权纸箱；
- 仅采集能够补充 D01、D05、明确 D04 或连续节点验证的完全脱敏图片；
- 固定同一台手机；
- 使用后置主摄和 1× 倍率；
- 固定图片比例，不使用数码变焦；
- 关闭美颜、滤镜和人像模式；
- 保持 HDR 设置一致；
- 使用原图传输，不经微信普通图片压缩；
- 记录设备 ID、手机型号、镜头、分辨率、比例、HDR、滤镜、光照和背景；
- 保留原始文件，不覆盖、不裁剪、不重编码；
- 每张图片填写一条真实 manifest 记录；
- 提交前运行第一轮 manifest 校验和第二轮质量审计。
- 不把公开数据集图片写入 21 字段连续节点 manifest；第二轮工具继续服务于补缺采集和真实试验数据质量验收。

## 6. 提交前命令

先校验数据合同：

```powershell
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" `
  "E:\Artificial-intelegence-training\scripts\dataset\validate_manifest.py" `
  --manifest "E:\JianZhengData\incoming\BATCH-PILOT-001\manifest.csv" `
  --data-root "E:\JianZhengData\incoming\BATCH-PILOT-001" `
  --schema "E:\Artificial-intelegence-training\configs\training\manifest-schema-v0.1.json" `
  --report "E:\JianZhengData\incoming\BATCH-PILOT-001\reports\validation-report.json" `
  --check-files
```

再运行图像质量审计，具体命令见 `image-quality-audit-v0.1.md`。

## 7. 失败清理保证

初始化期间发生错误时，工具只尝试删除本次明确创建的文件和空目录，不使用递归删除，也不删除任何此前已存在的目录。同名批次冲突时不会写入任何内容。
