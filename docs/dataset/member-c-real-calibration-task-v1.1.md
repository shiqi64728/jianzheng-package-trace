# 成员 C：真实校准拍摄任务 v1.1

## 拍什么、拍多少

优先拍 5 个自有/明确授权纸箱；最低 3 个。每箱依次拍 N1、N2、N3，每个节点拍 front、left、right、top：推荐 60 张，最低 36 张。

- CASE-R01：始终正常。
- CASE-R02：拍完 N1 后，在记录的一个 surface 制造轻微可逆局部变化；N2/N3 保持。
- CASE-R03：拍完 N2 后再加入变化。
- CASE-R04：轻度凹陷/结构变化。
- CASE-R05：胶带位置/封装视觉变化。

不得损坏真实客户包裹。

## 怎么拍和命名

同一手机后置主摄、1×，关闭美颜/滤镜/人像；固定距离、朝向、背景和光照，四个面完整入画。文件名：

```text
CASE-R01_N1_front_20260812T130000+0800.jpg
```

依次替换包裹、节点、surface 和真实时间。不要使用微信二次压缩文件。

## 变化与隐私

在 `capture-worklist.csv` 填真实 `capture_time`、`image_path`、变化施加节点、surface 和类型。不得猜。拍摄前遮住/移除姓名、手机号、地址、运单号、二维码、人脸和私人物品；将 `ownership_status` 和 `privacy_status` 填为实际审核结果。

## 怎么交付

将原图放入一个新目录，连同填完的 `capture-worklist.csv` 一起交给负责人；不要放进 Git，不要修改 `E:\JianZhengData\external\raw` 或冻结训练集。负责人校验后再导入 `E:\JianZhengData\runtime\competition-rc-v1.1\real-calibration`。
