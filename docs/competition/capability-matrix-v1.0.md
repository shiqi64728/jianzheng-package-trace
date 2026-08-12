# Competition RC v1.0 能力真实性矩阵

本文件是作品文本、PPT、演示视频和答辩的统一事实来源。

## 分类定义

| 分类 | 含义 |
|---|---|
| `AI_AUTO` | 活动模型可以自动输出的已知类别 |
| `OPEN_SET_DETECTION` | 发现无法归入活动模型已知类别的可靠视觉变化 |
| `HUMAN_REVIEW` | 需要匿名人员复核、分类或确认 |
| `RULE_ENGINE` | 透明、确定性、可解释的业务规则，不是学习模型 |
| `DEMO_ONLY` | 受控合成/公开数据演示，不代表真实物流轨迹 |
| `FUTURE` | 当前未实现 |

## D01-D05

| 类别 | 真实能力归类 | 自动支持 | 说明 |
|---|---|---:|---|
| D01 | `OPEN_SET_DETECTION + HUMAN_REVIEW` | 否 | 由可靠外观变化触发后人工确认为胶带/封装变化 |
| D02 | `AI_AUTO + HUMAN_REVIEW` | 是 | YOLO26n 自动检测表面凹陷；关键结论仍允许人工复核 |
| D03 | `AI_AUTO + HUMAN_REVIEW` | 是 | YOLO26n 自动检测纸箱破口；关键结论仍允许人工复核 |
| D04 | `OPEN_SET_DETECTION + HUMAN_REVIEW` | 否 | 污损/受潮候选变化由人工确认，不宣传为模型自动分类 |
| D05 | `OPEN_SET_DETECTION + HUMAN_REVIEW` | 否 | 二次封装/胶带变化由人工确认，不宣传为模型自动分类 |

## 其他能力

| 能力 | 分类 | 状态 | 真实边界 |
|---|---|---|---|
| 同表面 ORB/RANSAC 配准 | `RULE_ENGINE` | IMPLEMENTED | 配准失败明确降级，不把失败对当异常证明 |
| 首次异常区间 | `RULE_ENGINE` | IMPLEMENTED | 从相邻同表面证据定位，不等同责任归属 |
| 外观数字指纹 | `RULE_ENGINE` | IMPLEMENTED | 工程记录与完整性摘要，不是跨摄像机身份识别 |
| UNKNOWN_VISUAL_CHANGE | `OPEN_SET_DETECTION` | IMPLEMENTED | 只说明存在可靠未分类变化 |
| 风险辅助评分 | `RULE_ENGINE` | IMPLEMENTED | 0-100 可解释证据风险分，不是概率，不是法律结论 |
| 工单闭环 | `RULE_ENGINE` | IMPLEMENTED | 状态可变，事件历史 append-only |
| Dashboard | `RULE_ENGINE` | IMPLEMENTED | 指标来自 SQLite 实际查询 |
| JSON/CSV 物流 metadata | `RULE_ENGINE` | IMPLEMENTED | 匿名通用适配层，不冒充企业 API |
| damage keyframe screening | `AI_AUTO` | IMPLEMENTED | MP4 固定间隔采样后调用现有 D02/D03 检测器 |
| behavior recognition | `FUTURE` | NOT IMPLEMENTED | 不识别抛扔、违规动作或人员行为 |
| Demo A/B/C/D | `DEMO_ONLY` | IMPLEMENTED | 合成或公开数据的模拟节点序列 |
| 真实同包裹 N1/N2/N3 校准 | `FUTURE` | `PENDING_EXTERNAL_DATA` | 不阻断 RC，但不得宣称已完成真实验证 |
| risk assistance | `RULE_ENGINE` | IMPLEMENTED | 责任辅助复核优先级与证据强度整理 |
| legal responsibility | `FUTURE` | `NOT_SUPPORTED` | 不自动判责，不输出赔偿结论 |

## 统一答辩表述

> 件证当前由 D02/D03 已知损伤检测、开放集外观变化、同表面时序证据、人工 D01/D04/D05 复核和可解释规则引擎共同提供异常定位与证据整理；系统不自动认定法律责任。
