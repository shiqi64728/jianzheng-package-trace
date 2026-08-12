# 开源组件与数据来源审计 v1.0

版本与许可证来自本机已安装包 METADATA、`frontend/package-lock.json` 或现有数据源 registry；没有证据的项目标为 `REVIEW_REQUIRED`。

## Python / Runtime

| 名称 | 版本 | 用途 | 许可证证据 | 来源 |
|---|---|---|---|---|
| Ultralytics | 8.4.102 | YOLO26n 推理封装 | `AGPL-3.0`（installed METADATA） | `https://github.com/ultralytics/ultralytics` |
| PyTorch | 2.13.0+cu130 | 活动模型运行时 | installed License-Expression：`Apache-2.0 AND Apache-2.0 WITH LLVM-exception AND BSD-2-Clause AND BSD-3-Clause AND BSL-1.0 AND MIT` | `https://github.com/pytorch/pytorch` |
| opencv-python | 5.0.0.93 | 图像、配准、视频解码/编码 | `Apache 2.0`（installed METADATA） | `https://github.com/opencv/opencv-python` |
| FastAPI | 0.141.1 | HTTP API | `MIT`（installed License-Expression） | `https://github.com/fastapi/fastapi` |
| Uvicorn | 0.52.1 | ASGI server | `BSD-3-Clause`（installed License-Expression） | `https://github.com/Kludex/uvicorn` |
| ONNX | 1.22.0 | 实验性模型格式 | `Apache-2.0`（installed License-Expression） | `https://github.com/onnx/onnx` |
| ONNX Runtime | 1.27.0 | 实验性 ONNX runtime | `MIT License`（installed METADATA） | `https://onnxruntime.ai` |
| NumPy | 2.4.4 | 数值与图像数组 | installed License-Expression：`BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0` | `https://github.com/numpy/numpy` |

ONNX 路线仍是 experimental；RC active runtime 是 PyTorch。

## Frontend

| 名称 | 版本 | 用途 | 许可证 | 来源证据 |
|---|---|---|---|---|
| Vue | 3.5.41 | 轻量单页界面 | MIT | `frontend/package-lock.json` |
| Vite | 7.3.6 | 本地构建 | MIT | `frontend/package-lock.json` |
| @vitejs/plugin-vue | 6.0.8 | Vue SFC 构建 | MIT | `frontend/package-lock.json` |

比赛运行使用预构建 `frontend/dist`，不访问 npm registry。

## 实际下载并治理的数据源

| 名称 | 版本 | 用途 | 许可证 | 来源 |
|---|---|---|---|---|
| defect-cardboard | v1 | D02 dent / D03 hole 候选检测数据；dirt 需人工复核 | CC BY 4.0 | `https://universe.roboflow.com/salima/defect-cardboard-h0kjy` |
| Damaged Box Detection | v1 | 完好/破损候选预训练数据；不直接证明 D01-D05 | CC BY 4.0 | `https://universe.roboflow.com/project-33xgh/damaged-box-detection` |
| TAMPAR | 1.0 | 外观变化、配准和篡改对演示 | CC BY 4.0 | `https://zenodo.org/records/10057090` |

来源证据：`E:\JianZhengData\external\registry\source-registry-v0.1.csv` 及 citations/licenses/source-pages。

## 仅登记、未批准作为本轮训练输入

| 名称 | 状态 | 原因 |
|---|---|---|
| Parcel Box Damage Classification v2 | REVIEW_REQUIRED / not downloaded | damage_A/B/C 没有公开类别语义，禁止自动映射 |
| Parcel2D Real 1.0 | metadata only | 不是 D01-D05 损伤标签 |
| Parcel3D 1.0 | REVIEW_REQUIRED / not downloaded | registry 记录为 other-nc / academic research only，存在组件限制与域差距 |

## 合规约束

所有公开数据演示必须保留来源和署名。公开图像、合成序列和真实物流序列必须分开标注；公开数据不能证明真实节点责任。当前项目不存姓名、手机号、详细地址或完整运单号。
