# Competition RC v1.1 能力真实性矩阵

本表是比赛作品文本、PPT、视频和答辩的统一事实来源。RC v1.1 没有新增产品功能，重点是数据来源标识、模型硬化和系统冻结。

| 能力/证据 | 数据来源 | 实现类型 | 当前状态 | 允许表述 | 禁止表述 |
|---|---|---|---|---|---|
| D02 表面凹陷 | PUBLIC DATA | AI AUTO + HUMAN REVIEW | IMPLEMENTED | YOLO26n imgsz960 自动候选检测，人工复核 | 行业级准确率、自动判责 |
| D03 纸箱破口 | PUBLIC DATA | AI AUTO + HUMAN REVIEW | IMPLEMENTED | YOLO26n imgsz960 自动候选检测，人工复核 | 行业级准确率、自动判责 |
| D01 胶带/封装变化 | SYNTHETIC/PUBLIC PROXY | OPEN SET + HUMAN REVIEW | IMPLEMENTED | 开放集视觉变化提示后人工确认 | D01 自动 AI 分类 |
| D04 污损/受潮 | SYNTHETIC/PUBLIC PROXY | OPEN SET + HUMAN REVIEW | IMPLEMENTED | 开放集视觉变化提示后人工确认 | D04 自动 AI 分类 |
| D05 其他异常 | SYNTHETIC/PUBLIC PROXY | OPEN SET + HUMAN REVIEW | IMPLEMENTED | 开放集视觉变化提示后人工确认 | D05 自动 AI 分类 |
| 首次异常区间 | SYNTHETIC CONTROLLED RULE | RULE ENGINE | IMPLEMENTED | 在已有节点证据中定位首次异常区间 | 对现实全行业的统计准确率 |
| 责任风险辅助 | SYNTHETIC CONTROLLED RULE | RULE ENGINE | IMPLEMENTED | 可解释 0–100 风险辅助与人工复核提示 | 法律责任概率或法律判责 |
| 视频损伤关键帧 | SYNTHETIC VIDEO + PUBLIC FRAME | AI AUTO | IMPLEMENTED | `VIDEO_DAMAGE_KEYFRAME_SCREENING` | 行为识别、抛扔识别 |
| 工单和 Dashboard | SYNTHETIC CONTROLLED RULE | SYSTEM BEHAVIOR | IMPLEMENTED | SQLite 业务闭环与真实查询 | 企业线上生产数据 |
| 真实 N1/N2/N3 校准 | REAL DATA | CONTROLLED CALIBRATION | PENDING_EXTERNAL_DATA | 已给出采集规范，待合规真实数据 | 已完成真实环境准确率验证 |
| YOLO26s@640 候选 | PUBLIC DATA train/val | EXPERIMENT ONLY | NOT_PROMOTED | val 容量假设实验，0/3 晋级项 | 已替代 active detector |

## Demo 与指标来源

- Demo D、5/5 稳定性、性能：`SYNTHETIC CONTROLLED RULE`；Demo D 使用程序合成的固定 N1/N2/N3 多表面图像与确定性流程。
- D02/D03 模型 val 指标：`PUBLIC DATA`，冻结 Roboflow 数据集。
- Near-duplicate audit：仅用于数据泄漏审计；test 模型预测没有被访问。
- `REAL DATA` 场景全部明确为 `PENDING_EXTERNAL_DATA`，没有以 synthetic/public 冒充 real。
