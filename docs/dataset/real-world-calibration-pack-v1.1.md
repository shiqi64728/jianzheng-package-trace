# Real-World Calibration 最小采集包 v1.1

用途仅为 `CONTROLLED REAL-WORLD CALIBRATION`，不是训练集，也不代表行业 accuracy。只拍摄自有或明确授权纸箱，不得损坏客户包裹。

## 数量与案例

- 推荐 5 箱：每箱 N1/N2/N3 × front/left/right/top，共 60 张。
- 最低 3 箱：共 36 张。
- CASE-R01：全程正常。
- CASE-R02：N1 正常，完成 N1 后、拍 N2 前在指定 surface 加轻度局部变化；N3 保持。
- CASE-R03：N1/N2 正常，完成 N2 后、拍 N3 前加入变化。
- CASE-R04：轻度凹陷或纸箱结构变化。
- CASE-R05：胶带位置或封装视觉变化。

## 固定拍法

同一手机、同一后置主摄、1×、关闭美颜/滤镜/人像，尽量避免自动 HDR 差异；固定距离、纸箱朝向、背景和光照。每个 surface 完整入画，减少严重透视、遮挡和反光。

## 记录与验收

按 `capture-worklist.csv` 填写实际 ISO 8601 时区时间和图片路径。真实变化必须记录施加在何节点之后、具体 surface、变化类型；不得猜测。`ownership_status` 只能是 `SELF_OWNED` 或 `EXPLICITLY_AUTHORIZED`，`privacy_status` 必须为 `PASSED`；画面不得含姓名、手机号、地址、完整运单号、人脸或其他个人照片。

数据到达后只运行 registration、change detection 和 sequence locator。达到至少 3 箱才对照工程目标：registration usable≥80%、正常 pair UNKNOWN 误报≤20%、明确变化检出≥80%、首次异常区间正确≥80%；样本更少只报告 `OBSERVATIONAL`。
