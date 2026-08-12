# 真实连续包裹序列最小验证协议 v1.0

状态：`REAL_WORLD_CALIBRATION = PENDING_EXTERNAL_DATA`

## 结论

2026-08-12 对 `E:\JianZhengData` 进行只读扫描后，未发现满足以下全部条件的数据：同一自有/获授权包裹、N1/N2/N3 三个连续节点、至少两个相同表面、可核验时间顺序、权限与隐私复核完成。现有 `BATCH-PILOT-001` 清单只有表头，且权限状态仍为 `pending`，不能作为真实验证证据。

这不阻断 Competition RC v1.0。RC 中的合成与公开数据序列必须继续标为 `SYNTHETIC_DEMO`、`SIMULATED_NODE_SEQUENCE` 或 `PUBLIC_DATA_DEMO`，不得称为真实物流轨迹。

## 最小采集规模

1. 使用 3 个由团队自有或已获得明确授权的包裹别名：`REAL-PKG-001` 至 `003`。
2. 每个包裹采集 N1、N2、N3；每节点采集 `front/left/right/top` 四表面，共 36 张原始图像。
3. 至少包含：一条全程正常序列、一条 N1→N2 人工可逆凹陷/污损序列、一条 N2→N3 胶带变化序列。
4. 只记录匿名 `package_alias`、`location_alias`、`device_alias`；不记录姓名、手机号、详细地址或完整运单号。

## 采集控制

- 固定设备、分辨率、焦距、距离和背景；每一表面尽量正对镜头。
- 节点时间采用带时区 ISO 8601；N1 < N2 < N3。
- 人工变化必须在自有包裹上完成并可恢复；记录操作前后照片及操作者别名。
- 图像进入仓库前进行面单、二维码、人脸和环境隐私复核；原始图像只放外部工作区。
- 对每张图像记录 SHA-256，禁止覆盖原文件。

## 清单最低字段

`sequence_id, package_alias, node_id, surface, capture_time, image_relpath, image_sha256, source_type, permission_status, privacy_status, change_control, reviewer_alias`

## 验收条件

- 3/3 序列矩阵完整，或缺失单元格被明确标为 `MISSING`。
- 权限与隐私状态均为 `approved`。
- 系统对正常、N1→N2、N2→N3 三种预期行为分别产生可复核输出。
- 结果独立记录为 `REAL_CONTROLLED_VALIDATION`，不与模型 accuracy 或当前 `SYSTEM BEHAVIOR VALIDATION` 混写。
