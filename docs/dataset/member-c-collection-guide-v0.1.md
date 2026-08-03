# 成员 C 公开数据审核与补缺采集指南 v0.1

> **路线定位**：公开数据集和公开资料是主要训练数据来源；成员 C 的主要职责已从大规模普通损伤图片采集，调整为公开数据人工抽查、类别映射复核，以及 D01、D05、明确 D04 和少量 N1/N2/N3 连续节点的定向补采。本指南保留 21 字段和拍摄规范，是为了接收少量真实补缺与验证数据，而不是要求成员 C 长期驻站采集。

公开数据不得套用内部 21 字段来伪造 `package_id`、`sequence_id`、`node_id`、`capture_time` 或 `first_abnormal_node`。只有团队自有或明确授权、按真实流程拍摄的数据才使用本指南中的内部 manifest。

## 1. 先回答成员 C 最关心的三个问题

### 1.1 为什么现实中看不到全部 21 个字段？

这 21 个字段不是“手机一次显示的 21 项信息”，而是把以下三类信息放到同一张机器可校验的表中：

1. **成员 A 或工具预先给定的信息**：合同版本、批次 ID、设备匿名 ID、采集者代号、初始数据划分等。
2. **成员 C 在拍摄时记录的信息**：这是哪个纸箱、拍的是哪个表面、图片文件名、拍摄时间、肉眼看到的外观状态等。
3. **成员 A 或复核者后续填写的信息**：最终标注状态、复核者、训练/验证/测试划分，以及连续节点的首次异常节点。

成员 C 不应猜测自己无法知道的信息。成员 A 应先建立批次、给出匿名编号规则并预填固定列；成员 C 主要填写每张图片真正发生变化的少数列。

### 1.2 做少量连续节点验证时，我怎样知道节点、首次异常节点、训练划分等信息？

这些信息不能仅靠一台手机或一张包裹照片得到：

- `node_id` 是团队定义的流程节点，不是手机自动显示的信息。
- `first_abnormal_node` 必须比较同一包裹在多个节点的图片后确定，不能根据单张图片猜测。
- `split` 是成员 A 在数据验收后做的训练集划分，成员 C 初始统一填写 `unassigned`。
- `annotation_status` 是标注工作状态，成员 C 初始通常填写 `unlabelled` 或 `needs_review`。
- `reviewer` 只有完成复核后才填写。

如果成员 A 尚未书面定义 N1、N2、N3 在本次试验中分别代表什么，成员 C **不得自行发明节点含义**。此时只做非连续试采集：

```text
sequence_id = 留空
node_id = NA
```

### 1.3 图片一次只能导入一张吗？

不是。收到明确的补缺或连续节点验证任务后，可以一次复制该任务指定的多张图片到 `images` 目录；图片数量由缺口和验证方案决定。

但是 CSV 的基本规则是：

> **一个图片文件对应 `manifest.csv` 中的一行。**

例如一次复制 30 张图片，就需要 30 行图片记录。当前版本没有图形界面，也没有“选择多张图片后自动生成 30 行”的导入按钮；图片复制和 CSV 填写是两个步骤。

---

## 2. 当前工作的适用边界

成员 C 当前首先承担公开数据审核：

- 抽查 `defect-cardboard` 的 `dent`、`hole`、`dirt`，重点判断 `dirt` 是否真正符合 D04 受潮污损；
- 抽查 Damaged Box Detection 的 `undamagedpackages` 与 `damagedpackages`，识别错标、非纸箱样本、背景偏差和明显增强样本；
- 抽查 TAMPAR 的参考图与篡改图配对，记录配对争议，不把它们命名为 N1/N2/N3；
- 只记录争议和审核结论，不移动、删除、覆盖或擅自修改公开数据原始文件、标签、许可证与来源记录。

仅在公开数据不能满足明确目标时，才补拍：

- D01 箱角挤压；
- D05 胶带变化或疑似二次封装；
- 能够明确证明受潮语义的 D04 样本；
- 少量自有包裹 N1/N2/N3 连续节点序列；
- 现场演示和公开数据域差异对照样本。

每次补采必须由成员 A 给出书面任务，明确类别缺口、数量上限、纸箱范围、节点定义和验收方法。数据合同 v0.1 没有单独的 `controlled_normal` 枚举；自有完好纸箱若是受控实验的损伤前基线，应按任务统一放入 `controlled_damage` 批次并在 `notes` 中记录 `CONTROL_BASELINE`，不得冒充真实站点来源的 `field_normal`。

成员 C 不再承担大规模普通破损图片采集、大批量快递站拍摄、私人运单网页爬取、个人信息收集、社交平台面单图片抓取，也不得修改公开数据的许可证或来源登记。

---

## 3. 先理解：一个“批次”、一个“纸箱”和一张“图片”是什么关系

### 3.1 批次

一次集中提交称为一个批次，例如：

```text
BATCH-PILOT-001
```

一个补缺或验证批次只包含任务明确要求的图片和纸箱；本批次应使用同一种 `source_type`、同一个采集成员代号和同一台设备匿名 ID。

### 3.2 纸箱

每个真实物理纸箱分配一个匿名 `package_id`，例如：

```text
PKG-PILOT-001
PKG-PILOT-002
PKG-PILOT-003
```

一个纸箱拍六个表面，会在 CSV 中出现六行，但六行都使用同一个 `package_id`。

### 3.3 图片记录

每个图片文件分配一个唯一 `record_id`，例如：

```text
REC-P001-FRONT-01
REC-P001-LEFT-01
REC-P001-TOP-01
```

即使是同一个纸箱、同一个表面的重拍，也必须使用不同的 `record_id` 和不同文件名。

关系如下：

```text
一个批次
├─ 纸箱 PKG-PILOT-001
│  ├─ 图片记录 REC-P001-FRONT-01
│  ├─ 图片记录 REC-P001-LEFT-01
│  └─ 图片记录 REC-P001-TOP-01
├─ 纸箱 PKG-PILOT-002
│  ├─ 图片记录 REC-P002-FRONT-01
│  └─ 图片记录 REC-P002-BACK-01
└─ ……
```

---

## 4. 21个字段逐项解释

下表增加了“信息来自哪里”和“成员 C 怎么做”，用于把数据合同映射到现实工作。

| 序号 | 字段 | 现实中代表什么 | 信息来源 | 成员 C 当前怎么填写 |
|---:|---|---|---|---|
| 1 | `schema_version` | 这张表使用哪一版填写规则 | 成员 A/模板 | 固定为 `0.1`，整列复制，不要修改 |
| 2 | `record_id` | 这一张图片记录的唯一匿名编号 | 项目编号规则 | 每张图片一个新 ID，例如 `REC-P001-FRONT-01` |
| 3 | `package_id` | 真实物理纸箱的匿名编号 | 成员 A/C贴纸或登记表 | 同一个纸箱所有图片重复使用同一 ID，例如 `PKG-PILOT-001` |
| 4 | `batch_id` | 本次定向补采或验证图片属于哪次提交 | 初始化工具/成员 A | 整批固定，例如 `BATCH-PILOT-001` |
| 5 | `sequence_id` | 同一纸箱跨 N1/N2/N3 的连续序列编号 | 成员 A定义连续流程 | 当前非连续试采集留空；只有正式连续采集才填，例如 `SEQ-PILOT-001` |
| 6 | `source_type` | 图片属于哪种来源 | 成员 A在建批次时决定 | 当前批次固定为一个值，不要混用 |
| 7 | `image_relpath` | 程序从批次根目录怎样找到图片 | 图片实际存放位置 | 填相对路径，例如 `images/PKG-PILOT-001/REC-P001-FRONT-01.jpg` |
| 8 | `surface` | 这张照片主要拍纸箱哪一面 | 成员 C拍摄时记录 | `FRONT/LEFT/RIGHT/TOP/BACK/BOTTOM` 之一 |
| 9 | `node_id` | 图片属于团队定义的哪个流程节点 | 成员 A的节点方案 | 非连续采集填 `NA`；连续采集才使用 `N1/N2/N3` |
| 10 | `capture_time` | 原图实际拍摄时间 | 手机相册“详细信息” | 使用带时区格式，例如 `2026-07-29T14:35:22+08:00` |
| 11 | `device_id` | 使用哪台设备拍摄的匿名编号 | 成员 A预先分配 | 例如 `PHONE-C-001`；不得写 IMEI、手机号或设备序列号 |
| 12 | `status` | 当前外观是否可见异常 | 成员 C初看，成员 A复核 | 明显完好填 `normal`；明显有异常填 `abnormal`；无法判断时不要猜，交成员 A复核 |
| 13 | `damage_type` | 肉眼看到的损伤类型 | 外观观察/后续标注 | 正常必须填 `NONE`；异常从 `D01—D05/MULTI` 选择 |
| 14 | `severity` | 当前损伤大致程度 | 外观观察/后续标注 | 正常填 `none`；异常可填 `light/medium/heavy`，无法定级填 `unknown` |
| 15 | `first_abnormal_node` | 连续流程中最早在哪一节点出现异常 | 比较完整序列后得到 | 非连续正常填 `NONE`；非连续异常填 `UNKNOWN`；连续序列由成员 A复核后填写 |
| 16 | `privacy_status` | 图片的隐私人工检查结果 | 人工检查，不是算法 | 自有空白纸箱且确认无隐私填 `not_applicable`；已人工完成脱敏填 `masked`；不确定时不能进入正式通过清单 |
| 17 | `annotation_status` | 这行是否已经标注和复核 | 标注流程 | 成员 C初始填 `unlabelled`；需要 A判断可填 `needs_review` |
| 18 | `split` | 最终进入训练、验证还是测试集 | 成员 A后续划分 | 成员 C一律先填 `unassigned` |
| 19 | `collector` | 谁执行了采集，但不记录姓名 | 成员 A预分配代号 | 例如 `MEMBER-C` 或 `C`，整批固定 |
| 20 | `reviewer` | 谁完成最终标注复核 | 成员 A/复核者 | 初始留空；只有 `annotation_status=reviewed` 时填写复核者匿名代号 |
| 21 | `notes` | 不适合放进其他列的非敏感说明 | 成员 C/A | 可写 `RETAKE`、`NEEDS_STATUS_REVIEW`；不得写姓名、电话、地址、单号或凭据 |

---

## 5. 四种 source_type 怎样映射到现实

| `source_type` | 现实含义 | 当前成员 C 是否建议使用 |
|---|---|---|
| `field_normal` | 合规条件下的真实完好包裹 | 只有授权和隐私流程明确后使用；不得用自有纸箱冒充真实站点来源 |
| `field_natural_damage` | 真实流程中自然出现的破损包裹 | 当前不建议主动寻找；不能人为制造后冒充自然损伤 |
| `controlled_damage` | 团队自有或明确授权纸箱上的受控损伤 | 首批建议使用，容易控制隐私和变量 |
| `continuous_node` | 同一物理纸箱在 N1/N2/N3 的连续采集 | 只有成员 A先定义节点和配对方法后使用 |

一个批次不要混合多种来源。例如正常纸箱和受控损伤纸箱应分别建立两个批次：

```text
BATCH-PILOT-NORMAL-001      source_type=field_normal
BATCH-PILOT-CONTROLLED-001  source_type=controlled_damage
```

如果“正常纸箱”其实是受控损伤实验开始前的同一自有纸箱基线，它可以继续放在 `controlled_damage` 批次中，图片行使用 `status=normal`、`damage_type=NONE`、`severity=none`，并在 `notes` 中写 `CONTROL_BASELINE`。

---

## 6. 表面 surface 怎么判断

在拍第一张图之前，先给每个自有纸箱定义固定朝向：

1. 选择一个不含个人信息的参考面作为 `FRONT`。
2. 面向 `FRONT` 时，左右两面分别为 `LEFT` 和 `RIGHT`。
3. 上下两面为 `TOP` 和 `BOTTOM`。
4. 与 `FRONT` 相对的一面为 `BACK`。

可以在自有试验纸箱上贴不含身份信息的临时方向标记。不要把快递面单默认当作 `FRONT`，因为面单可能包含姓名、电话、地址和条码。

建议一张图片只突出一个主要表面。若一张照片同时包含多个表面且无法确定主要表面，应重新拍摄，不要随意选择。

---

## 7. 损伤字段怎样判断

### 7.1 正常图片

三列必须组合填写：

```text
status = normal
damage_type = NONE
severity = none
```

`first_abnormal_node`：

- 非连续正常图片填 `NONE`；
- 连续序列全部正常时，整个序列填 `NONE`。

### 7.2 异常图片

损伤类型：

| 值 | 肉眼示例 |
|---|---|
| `D01` | 箱角被压扁、挤压变形 |
| `D02` | 纸箱表面出现凹陷 |
| `D03` | 纸板破口、裂开或穿孔 |
| `D04` | 受潮、水渍或明显污损 |
| `D05` | 胶带发生变化或疑似二次封装 |
| `MULTI` | 同时存在多类损伤 |

异常记录必须满足：

```text
status = abnormal
damage_type = D01/D02/D03/D04/D05/MULTI
severity = light/medium/heavy/unknown
```

如果成员 C 能确认“有异常”但不能可靠判断严重程度，可以填：

```text
severity = unknown
annotation_status = needs_review
split = unassigned
notes = NEEDS_SEVERITY_REVIEW
```

如果连“正常还是异常”都无法判断，不要为了让表格完整而猜测。将图片单独交给成员 A确认后再进入正式 manifest。

---

## 8. N1、N2、N3 和 first_abnormal_node 到底是什么

N1、N2、N3 是**项目实验节点代号**，不是固定的行业通用名称，也不是手机能够识别的字段。

成员 A必须在每次连续试验开始前给出类似以下书面定义：

```text
本次实验：
N1 = <成员A定义的第一个拍摄检查点>
N2 = <成员A定义的第二个拍摄检查点>
N3 = <成员A定义的第三个拍摄检查点>
```

在没有这份定义时，不使用 `continuous_node`。

连续采集时，同一个物理纸箱必须保持：

```text
package_id 相同
sequence_id 相同
```

但每个节点、每张图片的 `record_id` 和 `image_relpath` 不同。

例：如果同一纸箱同一表面在 N1 正常、N2 首次异常、N3 仍异常，则三行都填写：

```text
first_abnormal_node = N2
```

它不是“本行的节点”，而是“整个连续序列第一次出现异常的节点”。这个值应在 N1/N2/N3 图片齐全后由成员 A复核。

---

## 9. 图片实际怎样导入

### 9.1 第一步：确认批次目录

成员 A发来的目录应类似：

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

### 9.2 第二步：从手机导出原图

建议使用 USB 数据线、手机厂商原图传输或不压缩的文件传输方式。不要使用微信“普通图片”方式传输。

一次可以选择并复制多张图片。例如将 30 张原图一次复制到：

```text
BATCH-PILOT-001\images\
```

也可以按纸箱建立子目录：

```text
images\
├─ PKG-PILOT-001\
├─ PKG-PILOT-002\
└─ PKG-PILOT-003\
```

### 9.3 第三步：规范命名

建议文件名直接使用记录 ID、表面和拍摄序号：

```text
REC-P001-FRONT-01.jpg
REC-P001-LEFT-01.jpg
REC-P001-TOP-01.jpg
```

文件名不得包含真实姓名、电话、地址、运单号、设备序列号或站点名称。

### 9.4 第四步：把路径写入 manifest

假设实际文件是：

```text
BATCH-PILOT-001\images\PKG-PILOT-001\REC-P001-FRONT-01.jpg
```

`manifest.csv` 中只能写相对于批次根目录的路径，并统一使用 `/`：

```text
images/PKG-PILOT-001/REC-P001-FRONT-01.jpg
```

不能写：

```text
E:\BATCH-PILOT-001\images\...
images\PKG-PILOT-001\...
../images/...
```

---

## 10. 多张图片怎样写进表

规则非常简单：**一张图片一行**。

同一纸箱拍三面时：

| 图片 | `record_id` | `package_id` | `surface` | `image_relpath` |
|---|---|---|---|---|
| 正面图 | `REC-P001-FRONT-01` | `PKG-PILOT-001` | `FRONT` | `images/PKG-PILOT-001/REC-P001-FRONT-01.jpg` |
| 左侧图 | `REC-P001-LEFT-01` | `PKG-PILOT-001` | `LEFT` | `images/PKG-PILOT-001/REC-P001-LEFT-01.jpg` |
| 顶面图 | `REC-P001-TOP-01` | `PKG-PILOT-001` | `TOP` | `images/PKG-PILOT-001/REC-P001-TOP-01.jpg` |

注意：

- 三行的 `package_id` 相同，因为是同一个物理纸箱。
- 三行的 `record_id` 不同，因为是三个图片文件。
- 三行的 `image_relpath` 不同。
- 同一个图片文件不能重复写入两行。
- 把同一图片复制成两个文件名也会被 SHA-256 审计识别为重复内容。

### 10.1 WPS/Excel 填写建议

1. 使用 WPS表格或 Excel 打开 `manifest.csv`。
2. 不要删除、增加或调换21列表头。
3. 将 ID、时间、路径列按文本处理，避免自动变成科学计数法或日期格式。
4. 对整批不变化的列，可填写第一行后向下复制。
5. 对每张图片变化的列逐行填写。
6. 保存时选择 UTF-8 CSV；不要只保存成 `.xlsx`。
7. 保存后重新运行校验器。

---

## 11. 成员 C 实际需要填写的列并没有21项那么多

对于当前推荐的“非连续、自有纸箱、未进入训练划分”批次，成员 A可先预填以下固定值：

| 字段 | 示例固定值 |
|---|---|
| `schema_version` | `0.1` |
| `batch_id` | `BATCH-PILOT-001` |
| `sequence_id` | 留空 |
| `source_type` | 本批次约定值 |
| `node_id` | `NA` |
| `device_id` | `PHONE-C-001` |
| `privacy_status` | 自有空白纸箱且人工确认无隐私时为 `not_applicable` |
| `annotation_status` | `unlabelled` |
| `split` | `unassigned` |
| `collector` | `MEMBER-C` |
| `reviewer` | 留空 |

成员 C 每张图片主要填写或确认：

```text
record_id
package_id
image_relpath
surface
capture_time
status
damage_type
severity
first_abnormal_node
notes
```

其中正常、非连续图片的四个外观字段也可以按固定组合填写：

```text
status = normal
damage_type = NONE
severity = none
first_abnormal_node = NONE
```

因此成员 C 的工作重点是正确对应“哪个纸箱、哪张图片、哪个表面、什么时间、看到什么外观”，而不是从手机里寻找全部21项信息。

---

## 12. 完整示例：同一个正常纸箱的三张图片

以下示例假设：

- 自有空白纸箱，人工确认没有隐私；
- 作为受控实验的损伤前正常基线，`source_type=controlled_damage`；
- 非连续采集；
- 一个纸箱拍 FRONT、LEFT、TOP 三面；
- 尚未标注和划分训练集。

```csv
schema_version,record_id,package_id,batch_id,sequence_id,source_type,image_relpath,surface,node_id,capture_time,device_id,status,damage_type,severity,first_abnormal_node,privacy_status,annotation_status,split,collector,reviewer,notes
0.1,REC-P001-FRONT-01,PKG-PILOT-001,BATCH-PILOT-CONTROLLED-001,,controlled_damage,images/PKG-PILOT-001/REC-P001-FRONT-01.jpg,FRONT,NA,2026-07-29T14:35:22+08:00,PHONE-C-001,normal,NONE,none,NONE,not_applicable,unlabelled,unassigned,MEMBER-C,,CONTROL_BASELINE
0.1,REC-P001-LEFT-01,PKG-PILOT-001,BATCH-PILOT-CONTROLLED-001,,controlled_damage,images/PKG-PILOT-001/REC-P001-LEFT-01.jpg,LEFT,NA,2026-07-29T14:36:10+08:00,PHONE-C-001,normal,NONE,none,NONE,not_applicable,unlabelled,unassigned,MEMBER-C,,CONTROL_BASELINE
0.1,REC-P001-TOP-01,PKG-PILOT-001,BATCH-PILOT-CONTROLLED-001,,controlled_damage,images/PKG-PILOT-001/REC-P001-TOP-01.jpg,TOP,NA,2026-07-29T14:37:03+08:00,PHONE-C-001,normal,NONE,none,NONE,not_applicable,unlabelled,unassigned,MEMBER-C,,CONTROL_BASELINE
```

---

## 13. 推荐的现场操作顺序

### 拍摄前

1. 确认本批次 ID、来源类型、设备 ID 和采集者代号。
2. 确认只使用自有或明确允许的纸箱。
3. 给每个纸箱分配 `package_id`。
4. 固定 FRONT/LEFT/RIGHT/TOP/BACK/BOTTOM 的方向。
5. 检查画面中不会出现个人隐私。

### 拍摄时

1. 固定同一手机、后置主摄、1×倍率和图片比例。
2. 一张图片主要对应一个纸箱和一个表面。
3. 不使用数码变焦、美颜、滤镜或人像模式。
4. 不要为了凑数量连续拍完全相同的画面。
5. 无法判断的外观问题记录下来，交给成员 A。

### 导入时

1. 一次复制全部原图到 `images`。
2. 按纸箱建立子目录。
3. 按 `record_id + surface + 序号` 重命名。
4. 每张图片在 manifest 新增一行。
5. 检查图片数量与 CSV 行数是否一致。

### 提交前

1. 检查 `batch-info.json` 的设备和拍摄参数是否完整。
2. 检查 manifest 中没有真实姓名、电话、地址或运单号。
3. 运行第一轮 manifest 校验。
4. 运行第二轮图片质量审计。
5. 修正所有 FAIL。
6. 对全部 WARN 进行人工查看。
7. 将整个批次目录原样压缩后交给成员 A。

---

## 14. 常见错误

### 错误一：把同一个纸箱的每张图片都分配不同 package_id

错误。一个物理纸箱应始终使用同一个 `package_id`。

### 错误二：30张图片只在 CSV 写一行

错误。一张图片对应一行，30张图片需要30行。

### 错误三：直接填写手机绝对路径

错误。只能填写相对路径，例如：

```text
images/PKG-PILOT-001/REC-P001-FRONT-01.jpg
```

### 错误四：不知道节点含义，自己把拍摄顺序叫 N1/N2/N3

错误。节点必须由成员 A预先定义。普通拍摄顺序不等于责任节点。

### 错误五：从单张异常图猜 first_abnormal_node

错误。非连续异常填 `UNKNOWN`；连续序列由成员 A比较完整序列后确定。

### 错误六：把照片中看到的运单号写成 package_id

错误。`package_id` 必须是项目匿名编号，不能使用真实运单号。

### 错误七：认为 privacy_status=masked 就代表算法已经检查过

错误。该字段只是人工声明。当前工具不会自动识别图片中的姓名、电话、地址、条码或人脸。

### 错误八：把正常、自然破损和受控损伤混在一个批次

不建议。第二轮批次审计要求批次级来源信息与 manifest 一致，应分别建立批次。

---

## 15. 成员 A 在交接前必须给成员 C 的信息

成员 A不能只发一个空目录和一张21列表格。至少应同时给出：

```text
batch_id
source_type
collector
device_id
本批次允许使用的纸箱范围
package_id 编号范围
是否做连续节点采集
如果连续，N1/N2/N3 的书面定义
隐私检查和授权流程
异常图片由谁复核
最终交付时间和交付方式
```

推荐成员 A直接预先填写整批固定列，使成员 C只填写每张图片变化的字段。

---

## 16. 当前版本仍然没有的功能

成员 C 需要明确，当前版本是命令行和 CSV 工作流，尚未提供：

- 手机采集 App；
- 网页上传界面；
- 批量选择图片后自动生成 manifest 行；
- 自动读取 EXIF 并填写拍摄时间；
- 自动识别包裹表面；
- 自动识别隐私；
- 自动判断损伤类型；
- 自动推断首次异常节点；
- 自动完成训练集划分。

因此当前补缺采集的目标不是让成员 C 在快递站独立完成全部数据治理，而是验证：

> 明确缺口对应的少量真实图片能否按照统一目录和匿名 ID 被可靠接收，成员 C 与成员 A 之间的人工交接流程是否清晰。

---

## 17. 遇到无法确定的字段时怎么办

按以下优先级处理：

1. 不猜测。
2. 先查看本手册和 `data-contract-v0.1.md`。
3. 在不含隐私的情况下记录问题图片的 `record_id`。
4. 使用 `notes=NEEDS_REVIEW` 或更具体的英文标记。
5. 保持 `split=unassigned`。
6. 使用 `annotation_status=needs_review`。
7. 交给成员 A复核后再运行最终校验。

如果字段规则本身没有定义，例如 N1/N2/N3 的现实节点含义，应停止该类采集并要求成员 A补充书面定义。

---

## 18. 公开数据审核怎样交付

审核公开数据时，成员 C 只使用治理任务生成的路径引用和审核工作清单，不把公开图片复制进 Git，也不直接改动外部数据 `raw` 区。建议每条审核记录至少包含：

```text
external_record_id
source_id
image_relpath
review_decision
review_reason
reviewer_alias
reviewed_at
notes
```

审核重点：

| 数据来源 | 审核重点 | 明确禁止 |
|---|---|---|
| `defect-cardboard` | `dent`、`hole` 语义抽查；`dirt` 是否为明确受潮 | 未复核就把 `dirt` 正式认定为 D04 |
| Damaged Box Detection | normal/damaged 二分类语义、错标、背景偏差、增强与重复 | 把 `damagedpackages` 擅自细分为 D01—D05 |
| TAMPAR | reference/tampered 配对正确性、篡改类型可信度 | 把配对图伪造成真实 N1/N2/N3 或责任节点 |
| 国家邮政局统计 | 来源、时间、指标含义 | 混入图像训练清单 |

遇到争议样本时，应记录为待复核，不猜测、不自动改标签。公开数据只有在来源可追溯、许可证通过、文件完整、标签语义明确、无跨 split 泄漏、类别映射获批且用途与任务匹配后，才能进入训练候选。
