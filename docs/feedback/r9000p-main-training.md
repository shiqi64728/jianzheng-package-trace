# R9000P 主训练机环境配置与安全清理反馈

## 基本信息

- 项目：件证——基于连续外观数字指纹的快递损伤异常节点定位与责任辅助认定系统
- 正式仓库：`https://github.com/shiqi64728/jianzheng-package-trace.git`
- 指定工作目录：`E:\Artificial-intelegence-training`
- 首次执行：2026-07-19
- 接续清理与复验：2026-07-22
- 主机：LENOVO 83LV，Windows 11 64-bit，AMD Ryzen 9 8945HX，31.3 GiB RAM
- GPU：NVIDIA GeForce RTX 5060 Laptop GPU，8151 MiB，驱动 582.05
- 审计：`D:\下载的应用\_audit`
- 备份：`D:\下载的应用\_backups\r9000p-20260719-210748`
- 隔离：`D:\下载的应用\_quarantine\20260719-210748`

## 本轮目标

1. 建立正式 Git 工作区和训练环境分支。
2. 安装隔离的 Miniconda/Python 3.12 环境。
3. 安装官方稳定版 PyTorch CUDA wheel 与全部训练工具。
4. 验证 RTX 5060 Laptop GPU、核心导入与 ONNX CPU 推理。
5. 配置并实际验证 PyCharm、VS Code。
6. 建立训练目录、忽略规则、依赖锁和激活脚本。
7. 审计旧 Python、重复工具、孤儿候选并安全清理。
8. 生成环境/清理/反馈报告。
9. 全部通过后限定范围 Commit、Push 并创建 Draft PR。

## 已完成事项

### 审计与恢复

- 建立 `_audit`、`_backups`、`_quarantine` 目录。
- 备份 PyCharm 配置、VS Code 配置和原反馈文件。
- 生成软件、Python、编译器、PATH、磁盘、仓库原始文件、旧 Python 文件和 SHA-256 清单。
- `D:\Python` 共 39,013 个文件；39,013 个 SHA-256 均成功，0 个失败。
- 最终确认 `D:\Python` 仍被真实个人项目、`重连\.venv`、PyCharm SDK 和快捷方式引用；安全停止，不卸载、不隔离、不修改 SDK。
- 对指定三类根目录生成增强版 `orphan-candidates.csv`，记录浅层 EXE、签名、卸载、快捷方式、进程、PATH、文件关联、项目/文档证据和保留决定。

### Git 工作区（最后成功状态）

- 在 `E:\Artificial-intelegence-training` 初始化并连接正式远程仓库。
- 因 VPN 将 GitHub DNS 解析到 loopback，设置仓库级代理 `http://127.0.0.1:7890` 后成功获取远程。
- 创建分支 `feat/training-complete-environment`；最后确认 HEAD `f6ac4d0`。
- 建立 `.gitignore`、训练目录、依赖配置、激活脚本；`.idea/` 与 `.vscode/` 被忽略。
- 2026-07-22 接续时，卷标 `Elements` 的外置 `E:` 盘曾短暂未被系统枚举；08:38 自然恢复为 `E:` 后，仓库顶层、origin、分支、HEAD 和工作树复核正常。未强行重建盘符或复制仓库。

### Miniconda 与 Python

- 官方 Miniconda 安装器 SHA-256：`2D4A6CDCAA60F5A3C67BE17CDD8CC53C835EE00B7973D0E3D6AB5E0A8177524E`，签名有效。
- 中文安装前缀失败后，经用户明确授权使用 `D:\JianzhenApps\Miniconda3`。
- Conda 26.5.3，base Python 3.14.6，`auto_activate_base=false`。
- 正式环境 `jianzhen-training`：`D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe`，Python 3.12.13，pip 25.0，64-bit。
- 未执行 `conda init`，未修改机器 PATH，未注册默认 Python。2026-07-22 仅在用户 PATH 加入 VS Code `bin`、PyCharm `bin` 与 Miniconda `condabin`；未加入 Miniconda 根目录、`Scripts` 或项目环境目录。

### PyTorch 与训练工具

- 2026-07-19 从 PyTorch 官方来源选择稳定版 Windows pip CUDA 13.0 wheel。
- 安装 `torch==2.13.0+cu130`、`torchvision==0.28.0+cu130`。
- 安装 numpy、scipy、pandas、scikit-learn、OpenCV、Pillow、matplotlib、albumentations、PyYAML、tqdm、rich、psutil、tensorboard、ultralytics、ONNX 工具、pytest、ruff、JupyterLab、ipykernel。
- 未安装系统级 CUDA Toolkit、系统级 cuDNN、nightly PyTorch 或第三方 GPU wheel。
- 已创建 `environment-r9000p.yml` 与 150 行依赖锁文件。

### IDE

- VS Code 1.108.1 安装 Python 2026.4.0、Pylance 2026.3.1、固定版本的 Python Environments 1.20.1、Jupyter 2025.9.1。
- VS Code 工作区配置精确指向正式环境；使用工作区终端的进程级 `-ExecutionPolicy Bypass` 解决 Conda hook 限制，未修改全局执行策略。
- 2026-07-19 与 2026-07-22 VS Code 新终端实测：正式 Python 路径、Python 3.12.13、torch 2.13.0+cu130、CUDA True。
- 用户 PATH 已加入 VS Code `bin`、PyCharm `bin` 和 Miniconda `condabin`；新进程中 `code`、`pycharm64`、`conda` 均可直接调用，机器 PATH 和默认 Python 未改变。
- PyCharm 2024.1.7 的 Conda 向导与 Conda 26.5.3 出现兼容错误，改用 System Interpreter 指向同一个正式 Conda 环境。
- 2026-07-19 与 2026-07-22 PyCharm Terminal 实测：正式 Python 路径、Python 3.12.13、torch 2.13.0+cu130、CUDA True。
- 旧 Python 3.9 的 PyCharm SDK 因现存项目引用而保留。

### 安全清理

- 正式环境 pip 缓存：释放 2,291,760,107 B。
- 旧 Python/共享 pip 缓存：释放 866,123,209 B；未执行旧 pip 安装命令。
- Conda 缓存：释放 281,996,822 B。
- 当前用户 Temp：删除 229，跳过 15，释放 10,586,059 B。
- CrashDumps：删除 1，释放 1,215,933 B。
- Windows Temp：扫描时无文件。
- 三个同一物理文件的 Miniconda 安装器硬链接在全部门禁恢复后删除，释放 130,747,768 B。
- 删除 Pylance 2026.2.1 和不兼容的 Python Environments 1.36.0 两个已验证过期扩展目录；清理前对 7,760 个文件全部计算 SHA-256，净减少 103,510,877 B。
- Python Environments 使用 VS Code 官方 CLI 卸载后精确安装 1.20.1，最终唯一记录 `pinned=True`，避免再次自动生成不兼容的 1.36.0。
- 可核算净清理总量：3,685,940,775 B（3.433 GiB），其中本轮两个已验证 VS Code 过期扩展目录净减少 103,510,877 B（98.72 MiB）。
- 未卸载任何独立软件主程序，未移动任何软件目录，未删除任何用途不明项。

## 执行过的关键命令

```powershell
git init
git remote add origin https://github.com/shiqi64728/jianzheng-package-trace.git
git config --local http.proxy http://127.0.0.1:7890
git fetch origin --prune
git checkout -B main origin/main
git switch -c feat/training-complete-environment

D:\JianzhenApps\Miniconda3\Scripts\conda.exe create -n jianzhen-training python=3.12 pip --yes --solver classic
D:\JianzhenApps\Miniconda3\Scripts\conda.exe config --set auto_activate_base false

python -m pip install torch==2.13.0 torchvision==0.28.0 --index-url https://download.pytorch.org/whl/cu130
python -m pip check

D:\JianzhenApps\Miniconda3\Scripts\conda.exe clean --all --yes
python -m pip cache purge

git --version
git lfs version
nvidia-smi --query-gpu=name,driver_version,memory.total,compute_cap --format=csv,noheader
```

GPU 复验使用 CUDA 张量矩阵运算、反向传播与同步；ONNX 复验创建本地两层小网络、导出 opset 18、执行 `onnx.checker`、使用 `CPUExecutionProvider` 推理并删除临时目录。

## 新增或修改的文件

最后确认已在仓库创建：

- `.gitignore`
- `ai/training/.gitkeep`
- `ai/models/.gitkeep`
- `ai/models/releases/.gitkeep`
- `ai/evaluation/.gitkeep`
- `ai/export/.gitkeep`
- `dataset/manifests/.gitkeep`
- `configs/training/environment-r9000p.yml`
- `configs/training/requirements-r9000p-lock.txt`
- `docs/experiments/main-training/environment-r9000p.txt`
- `docs/experiments/main-training/cleanup-r9000p.md`
- `docs/feedback/r9000p-main-training.md`
- `scripts/training/activate-r9000p.ps1`

忽略且不提交：`.vscode/settings.json`、`.idea/`、环境、缓存、审计、安装器、数据集、模型与 ONNX 临时文件。

主机审计新增：

- `D:\下载的应用\_audit\old-python-files.csv`
- `D:\下载的应用\_audit\old-python-sha256.csv`
- `D:\下载的应用\_audit\old-python-references.txt`
- `D:\下载的应用\_audit\orphan-candidates.csv`
- `D:\下载的应用\_audit\cleanup-plan.md`
- `D:\下载的应用\_audit\cleanup-package-manager.log`
- `D:\下载的应用\_audit\cleanup-actions.csv`
- `D:\下载的应用\_audit\cleanup-temp-summary.csv`
- `D:\下载的应用\_audit\cleanup-targets-after.csv`
- `D:\下载的应用\_audit\disk-after.csv`
- `D:\下载的应用\_audit\path-before-global-tools.txt`
- `D:\下载的应用\_audit\path-after-global-tools.txt`
- `D:\下载的应用\_audit\vscode-duplicate-extension-files.csv`
- `D:\下载的应用\_audit\vscode-duplicate-extension-cleanup.csv`
- `D:\下载的应用\_audit\vscode-python-envs-official-reinstall.log`
- `D:\下载的应用\_audit\duplicate-installation-decisions-current.csv`
- `D:\下载的应用\_audit\post-global-tools-validation.txt`

## 测试结果

| 测试 | 结果 | 证据摘要 |
|---|---|---|
| Conda/Python | PASS | Conda 26.5.3；Python 3.12.13；64-bit |
| 全局隔离 | PASS | 只将 `condabin` 加入用户 PATH；base/环境解释器不在用户或机器 PATH；裸 `python` 仍为 WindowsApps；无 PYTHONHOME/PYTHONPATH |
| 全局工具 | PASS | 新用户环境中 `code`、`pycharm64`、`conda` 分别解析到预期路径；用户 PATH 去重后 9 项 |
| pip 依赖 | PASS | `No broken requirements found` |
| 核心导入 | PASS | OpenCV、NumPy、pandas、sklearn、albumentations、ultralytics、ONNX/ORT 等 |
| CUDA | PASS | torch 2.13.0+cu130；CUDA 13.0；cuDNN 92000 |
| GPU | PASS | RTX 5060 Laptop；capability `(12, 0)`；`sm_120` |
| 正反向传播 | PASS | CUDA forward/backward 与梯度有限性检查通过 |
| ONNX | PASS | opset 18；CPUExecutionProvider；最大误差 2.9802322387695312e-08 |
| ONNX 临时清理 | PASS | 测试临时目录不存在 |
| VS Code 扩展 | PASS | Python、Pylance 2026.3.1、Jupyter 已安装；Python Environments 仅有 1.20.1 且 `pinned=True` |
| VS Code/PyCharm 终端 | PASS（2026-07-19、2026-07-22） | 两个 IDE 均输出正式解释器和 CUDA True |
| 清理后 GPU/ONNX | PASS（2026-07-22） | 缓存清理后重新执行成功 |
| 当前仓库/IDE 项目复验 | PASS | `Elements` 恢复后 origin、分支、HEAD、工作树与两个 IDE 终端均正常 |
| 安装器清理 | PASS | 三个已校验硬链接删除，安装后的 Conda/GPU 复验通过 |
| Commit/Push/Draft PR | 报告生成后执行 | 只发布允许的仓库路径，最终结果见任务回复与 GitHub |

## 实验指标

本轮不执行模型训练，不下载数据集，因此没有精度、召回率、F1 或训练耗时指标。

环境验证指标：

- GPU：NVIDIA GeForce RTX 5060 Laptop GPU
- 显存：8151 MiB
- 驱动：582.05
- CUDA Runtime：13.0
- Compute capability：12.0
- PyTorch arch：包含 `sm_120`
- ONNX 最大绝对误差：`2.9802322387695312e-08`
- 可核算净清理量：`3.433 GiB`

## 遇到的问题

1. GitHub 直连受本机 VPN/代理 DNS 行为影响；仓库级代理后成功。
2. Miniconda 官方 Windows 安装器不能可靠处理中文目标前缀；用户授权改用 `D:\JianzhenApps\Miniconda3`。
3. 一次 libmamba 环境创建结果缺少 pip；改用 classic solver 后成功。
4. 初始大批 pip 下载与 PyTorch 下载出现超时/挂起；只停止由本轮启动的精确进程，分批并用官方 wheel 重试成功。
5. ONNX 首次导出因 Windows PowerShell GBK 无法输出导出器的 `✅` 字符而失败；设置 `PYTHONUTF8=1` 后成功，模型本身无错误。
6. PyCharm Conda 向导报 `lateinit property envs_dirs has not been initialized`；改用精确环境的 System Interpreter，Terminal 实测成功。
7. VS Code 首次 Conda 自动激活被 PowerShell 执行策略阻止；使用工作区终端进程级 Bypass 解决，未修改系统或用户策略。
8. VS Code 尝试更新 Python Environments 1.36.0 时与 Code 1.108.1 不兼容，并在首次删除后自动重生成目录；改用官方 CLI 卸载扩展、精确安装并固定 1.20.1，再按新 SHA-256 清单删除重生成残留。启动 30 秒后仅有 1.20.1 且 `pinned=True`。
9. 临时文件首轮删除完成后，详细日志因 Windows PowerShell 5.1 将无 BOM UTF-8 脚本中的中文审计路径解码错误而写入失败；实际删除计数和字节数从命令输出写入独立汇总，修正为 ASCII 构造路径后记录剩余跳过项。
10. 2026-07-22 外置 `Elements` 盘曾未出现于 `Get-Disk`、`Get-Volume` 或 `Get-PSDrive`，导致正式仓库短暂不可访问；08:38 自然恢复为 `E:`。没有执行磁盘初始化、盘符强占或仓库替代复制。
11. Computer Use 的 Windows 自动化连接因本地 kernel assets 路径错误不可用；改用 Windows 自带窗口激活和剪贴板粘贴，只在两个 IDE 集成终端执行只读验证并将输出写入审计目录，验证成功。

## 尚未解决的问题

- 环境、GPU、IDE、旧 Python 安全判断与清理均无阻断项。
- 外置 `Elements` 盘曾短暂掉线；后续训练写入期间应保持连接稳定。
- 25 个历史 EXE/MSI 和 17 个用途不明目录因无法证明安全而保留；它们不是本项目环境阻断项。

## 对其他电脑的接口或文件需求

当前不需要其他电脑提供数据集、模型、Token、Cookie 或私有凭据。

后续训练机/采集机之间建议只通过仓库内以下稳定接口协作：

- `dataset/manifests/`：数据清单与分割描述，不提交原始图片。
- `configs/training/`：环境与训练配置。
- `ai/models/releases/**/README.md`：发布模型的版本、校验和、输入输出契约；模型二进制走外部制品存储。
- `docs/experiments/main-training/`：环境与实验记录。

## 下一轮建议

1. 在训练前执行 `scripts\training\activate-r9000p.ps1` 并保存实验配置快照。
2. 先接入小规模、已脱敏的数据清单到 `dataset/manifests/`，验证数据加载和增强链路。
3. 建立首个可复现实验配置、随机种子、TensorBoard 日志和指标基线。
4. 模型权重、ONNX、原始数据和运行输出继续走忽略目录或外部制品存储，不提交到 Git。
5. 外置盘写入期间保持供电和连接稳定；训练前后记录磁盘健康与剩余空间。

## 第一轮：数据合同与清单自动校验器

### 1. 本轮目标

在不接触正式原始数据、不训练模型、不下载权重、不修改系统环境的前提下，建立第一版数据集输入合同、CSV 模板、机器可读合同、只读清单校验器和自动测试，使成员 C 的真实完好、自然破损、受控损伤及 N1/N2/N3 连续节点数据能够在进入训练前统一验收。

### 2. 开始前仓库状态

- E 盘卷标 `Elements`，HealthStatus `Healthy`，OperationalStatus `OK`。
- 正式仓库：`E:\Artificial-intelegence-training`。
- `origin`：`https://github.com/shiqi64728/jianzheng-package-trace.git`。
- 开始时旧分支 `feat/training-complete-environment` 工作树干净，无 merge、rebase 或 cherry-pick。
- 本地 `main` 原为 `f6ac4d0`，在 `git fetch origin` 后通过 `git pull --ff-only origin main` 快进到 `666ce9d88133c17abae6a6689ad513e79307f606`。
- 从更新后的 `main` 创建 `feat/training-dataset-contract-v01`，没有直接在 `main` 开发。
- 审计 `ai`、`configs`、`dataset`、`docs`、`scripts`、README 和 `.gitignore` 后，确认仓库只有空的 `dataset/manifests` 接口，没有既有数据合同、模板、校验器或测试目录，因此本轮没有重复建设或公共接口冲突。

### 3. 实际执行命令

主要命令：

```powershell
git status --short --branch
git remote -v
git branch -vv
git log -5 --oneline --decorate
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c feat/training-dataset-contract-v01

& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" --version
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" -m pip check
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" -c "import sys, torch, cv2, numpy, pandas; ..."

& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" -m unittest discover -s "E:\Artificial-intelegence-training\tests" -v
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" -m ruff check "E:\Artificial-intelegence-training\scripts\dataset" "E:\Artificial-intelegence-training\tests\dataset"
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" -m ruff format --check "E:\Artificial-intelegence-training\scripts\dataset" "E:\Artificial-intelegence-training\tests\dataset"
git diff --check
git status --short
```

另外使用临时目录分别运行合法虚拟示例和人工构造的非法清单；临时 CSV、图片和 JSON 报告由 `TemporaryDirectory` 在验证完成后删除。

### 4. 新增和修改文件

新增：

- `configs/training/manifest-schema-v0.1.json`
- `dataset/manifests/templates/manifest-v0.1.template.csv`
- `dataset/manifests/templates/manifest-v0.1.example.csv`
- `docs/dataset/data-contract-v0.1.md`
- `scripts/dataset/__init__.py`
- `scripts/dataset/validate_manifest.py`
- `tests/dataset/__init__.py`
- `tests/dataset/test_validate_manifest.py`

修改：

- `.gitignore`
- `docs/feedback/r9000p-main-training.md`

两个 CSV 均已验证以 UTF-8 BOM `EF BB BF` 开头。模板只有表头；虚拟示例包含 6 行，覆盖四种来源和一个完整 N1/N2/N3 序列。

### 5. 数据合同摘要

- schema 版本固定为 `0.1`。
- 21 个稳定字段覆盖身份、图像、状态/损伤和数据治理。
- 四类来源：`field_normal`、`field_natural_damage`、`controlled_damage`、`continuous_node`。
- 表面、节点、状态、损伤类型、等级、首次异常节点、隐私状态、标注状态和 split 均使用固定枚举。
- 路径必须相对 `data-root`，只使用 `/`，不得包含盘符、UNC、绝对路径、空路径段、`.` 或 `..`，解析结果必须留在数据根目录内。
- 同一个物理纸箱允许多行共用 `package_id`；跨批次、跨来源或跨 train/val/test 才判为 ID 冲突或数据泄漏。
- 连续序列必须填写 `sequence_id`，包含 N1/N2/N3，保持包裹、split 和首次异常节点一致。
- 正式接收清单只允许 `privacy_status=masked` 或 `not_applicable`；`rejected` 和 `pending_review` 必须返工。
- train/val/test 记录必须完成标注；`reviewed` 必须填写 reviewer。

### 6. 验证器支持的检查项目

- 空清单、缺少表头、缺少必需列、重复表头和额外列警告；
- 必填值、schema 版本、ID 格式、枚举值和带时区 ISO 8601 时间；
- `record_id` 重复、图片路径重复引用；
- 包裹 ID 跨批次/来源冲突；
- 正常/异常与损伤类型、等级、首次异常节点的逻辑；
- 连续记录缺少 `sequence_id`、使用 `node_id=NA`、缺少 N1/N2/N3；
- 非连续记录错误填写 `sequence_id`；
- 同一包裹或连续序列跨 train/val/test；
- 同一序列对应多个包裹、节点/表面槽位重复、首次异常节点冲突或与实际状态不一致；
- 隐私状态、标注状态和 reviewer；
- 路径绝对化、UNC、盘符、反斜杠、越级目录、根目录逃逸和不支持的图片扩展；
- 开启 `--check-files` 后检查文件存在性和 OpenCV 解码；
- 控制台中文摘要和 UTF-8 JSON 报告；
- 数据错误返回 1，使用错误返回 2，非预期内部错误返回 3。

校验器默认只读，不修改 CSV，不移动、删除、重命名或自动修复图片。

### 7. 自动测试结果

- 使用 Python 标准库 `unittest`，没有安装新依赖。
- 共运行 21 个测试，全部通过。
- 覆盖任务要求的 15 类必测场景，并增加合法连续序列、额外列警告、包裹跨批次冲突、隐私拒绝、空清单和退出码区分。
- `ruff check`：PASS。
- `ruff format --check`：PASS，4 个 Python 文件均已格式化。
- `py_compile`：PASS。
- 机器可读 JSON 解析：PASS，schema `0.1`、21 个字段。

### 8. 合法示例验证结果

对 `dataset/manifests/templates/manifest-v0.1.example.csv` 运行真实 CLI，不开启文件检查，因为示例路径明确为虚拟路径：

```text
退出码：0
总记录：6
通过记录：6
失败记录：0
错误：0
警告：0
```

JSON 报告成功生成在临时目录，并在验证结束后清理。

### 9. 非法示例验证结果

在临时目录人工构造 1 行非法清单并开启 `--check-files`：

```text
退出码：1
总记录：1
通过记录：0
失败记录：1
错误：6
警告：0
```

实际错误代码：

- `INVALID_CAPTURE_TIME`
- `ABSOLUTE_IMAGE_PATH`
- `NORMAL_WITH_DAMAGE_TYPE`
- `NORMAL_WITH_SEVERITY`
- `PRIVACY_NOT_APPROVED`
- `REVIEWER_REQUIRED`

JSON 报告成功生成并包含行号、`record_id`、字段、错误代码和中文说明；临时清单及报告随后自动删除。

### 10. 环境复验结果

- 正式解释器：`D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe`
- Python：3.12.13
- `pip check`：`No broken requirements found.`
- PyTorch：2.13.0+cu130
- CUDA：True
- GPU：NVIDIA GeForce RTX 5060 Laptop GPU
- OpenCV：5.0.0
- NumPy：2.4.4
- pandas：3.0.3

没有安装或升级 Python、PyTorch、CUDA、cuDNN、OpenCV、pandas、Ultralytics、pytest 或系统工具；没有修改 PATH、默认 Python、PowerShell 全局执行策略、Miniconda base、IDE 全局设置或 `F:\SecurityLab`。

### 11. Git 状态

- 当前分支：`feat/training-dataset-contract-v01`
- 分支基点：`666ce9d88133c17abae6a6689ad513e79307f606`
- `.gitignore` 已最小补充标注输出、验证报告和常见凭据规则。
- `dataset/manifests/**` 仍明确允许提交，模板和示例未被忽略。
- `git diff --check`：PASS。
- 实现提交：`36310629c2a57900b0cba628e738c700e52e43dd`，提交信息为 `feat(training): add dataset manifest contract and validator`。
- 新分支已推送到 `origin/feat/training-dataset-contract-v01`，实现提交的本地与远程哈希一致。
- `Get-Command gh -ErrorAction SilentlyContinue` 返回不可用；没有安装 GitHub CLI，也没有创建或声称创建 Draft PR。
- GitHub 查询确认该分支当前没有 PR。创建入口：`https://github.com/shiqi64728/jianzheng-package-trace/compare/main...feat/training-dataset-contract-v01?expand=1`。

### 12. 已知限制

- v0.1 只能发现相同路径的重复引用，不能发现“同一图片改名后重复”；内容哈希去重未纳入本轮。
- 程序不能自动证明隐私已经完全脱敏，仍需成员 C 和成员 A 查看图片。
- 程序不能自动判断损伤类型、严重程度和首次异常节点是否符合真实业务事实。
- 程序不能证明两个不同 `package_id` 是否实际属于同一物理纸箱。
- 虚拟示例只证明结构合同通过，不证明示例图片存在。
- 连续节点合同 v0.1 要求完整 N1/N2/N3；部分序列必须补齐后再进入正式接收清单。

### 13. 未完成事项

本轮开发目标已经完成。以下事项明确不在本轮范围内，未执行：

- 正式原始数据接入；
- 采集程序、摄像头、前端或后端开发；
- 模型训练、YOLO/其他权重下载；
- 图片内容哈希或感知哈希去重；
- 第二轮数据准备或训练工作。

### 14. 风险

- WPS/Excel 可能自动改变长 ID、时间或编码，成员 C 保存后必须重新运行校验。
- `privacy_status=masked` 只是声明，不能替代人工隐私抽查。
- 错误的人工标注可能结构合格但语义错误。
- E 盘为 USB 外置盘，写入和校验正式批次时必须保持连接稳定。
- 未来合同变更必须同步更新文档、JSON、模板、验证器和测试，不能静默覆盖 v0.1。

### 15. 回滚方法

提交前可只对本轮路径执行 `git restore` 并删除本轮新增文件；不得使用会影响其他文件的清理命令。提交后优先使用：

```powershell
git revert <本轮提交哈希>
```

该回滚只撤销合同、模板、验证器、测试、反馈和 `.gitignore` 增量，不会接触任何原始数据或图片。本轮校验器从未修改用户数据，因此不需要数据级回滚。

### 16. 下一轮建议

以下仅为建议，本轮未执行：

1. 由成员 C 使用少量、完全脱敏的受控样本进行首次线下交付演练。
2. 由成员 A 按文档进行独立复验，记录结构错误和人工语义错误的差异。
3. 根据试运行反馈决定是否在 v0.2 增加文件 SHA-256/感知哈希、批次元数据和更细的标注字典。
4. 在任何训练开始前，先冻结已验收的 package/sequence 级 split 清单并复查泄漏。
