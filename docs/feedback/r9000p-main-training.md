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

## 第二轮：试采集批次初始化与图像质量审计

### 1. 第一轮合并验收

- 2026-07-28 执行 `git fetch origin` 后，`origin/main` 为 `ce70e1477b3bb0abc3a89315f7840b4a4ecf8610`，提交说明为 `Merge pull request #2 from shiqi64728/feat/training-dataset-contract-v01`。
- `git merge-base --is-ancestor 36310629c2a57900b0cba628e738c700e52e43dd origin/main` 返回 `0`。
- `git merge-base --is-ancestor ef3594b3a22d83915a78ec73198634c292b232cd origin/main` 返回 `0`。
- 第一轮实现提交和反馈提交均已进入 `origin/main`，第一轮合并硬闸门通过。
- 本地 `main` 通过 `git pull --ff-only origin main` 快进到 `ce70e1477b3bb0abc3a89315f7840b4a4ecf8610`，与 `origin/main` 完全一致。

### 2. 本轮目标

本轮只建立试采集批次初始化工具、批次级元数据结构、集中式图像质量阈值、只读图像质量审计器、JSON/CSV 报告、自动测试和成员 C/A 工作流文档。

本轮没有使用真实快递数据，没有处理隐私图片，没有训练模型，没有下载权重，没有开发摄像头、标注平台、前端或后端，也没有修改数据合同版本。

### 3. 开始前仓库状态

- 正式仓库：`E:\Artificial-intelegence-training`
- 远程仓库：`https://github.com/shiqi64728/jianzheng-package-trace.git`
- E 盘：`Elements`，NTFS，`Healthy / OK`
- 开始前工作树干净。
- `.git\MERGE_HEAD`、`.git\rebase-merge`、`.git\rebase-apply`、`.git\CHERRY_PICK_HEAD` 均不存在。
- 第二轮分支：`feat/training-pilot-batch-audit-v01`
- 分支基点：`ce70e1477b3bb0abc3a89315f7840b4a4ecf8610`

### 4. 实际执行命令

主要执行：

```powershell
git status --short --branch
git remote -v
git branch -vv
git log -10 --oneline --decorate
git fetch origin
git merge-base --is-ancestor <第一轮提交> origin/main
git switch main
git pull --ff-only origin main
git switch -c feat/training-pilot-batch-audit-v01

& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" --version
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" -m pip check
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" -m unittest discover -s "E:\Artificial-intelegence-training\tests" -v
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" -m ruff check "E:\Artificial-intelegence-training\scripts\dataset" "E:\Artificial-intelegence-training\tests\dataset"
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" -m ruff format --check "E:\Artificial-intelegence-training\scripts\dataset" "E:\Artificial-intelegence-training\tests\dataset"
& "D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe" -m py_compile <第一轮和第二轮 Python 文件>
git diff --check
git diff --cached --check
git push -u origin feat/training-pilot-batch-audit-v01
```

端到端验证脚本位于仓库外：

```text
C:\Users\35001\Documents\Codex\2026-07-19\files-mentioned-by-the-user-r9000p\work\run-round2-pilot-audit-e2e.py
```

它只在 `TemporaryDirectory` 中生成合成图片、临时批次和报告。

### 5. 新增和修改文件

新增：

```text
configs/training/image-quality-v0.1.json
docs/dataset/image-quality-audit-v0.1.md
docs/dataset/pilot-batch-workflow-v0.1.md
scripts/dataset/audit_image_quality.py
scripts/dataset/init_pilot_batch.py
tests/dataset/test_audit_image_quality.py
tests/dataset/test_init_pilot_batch.py
```

修改：

```text
.gitignore
docs/feedback/r9000p-main-training.md
```

`scripts/dataset/validate_manifest.py` 未修改。

### 6. 批次初始化工具

`init_pilot_batch.py`：

- 只在用户明确提供且已存在的绝对 `output-root` 内创建批次；
- 默认拒绝覆盖同名批次，不提供覆盖参数；
- 拒绝含 `..`、路径分隔符、盘符、绝对路径和 UNC 形式的 `batch_id`；
- 复用第一轮 schema 的 ID 规则和 `source_type` 枚举；
- 从第一轮 UTF-8 BOM 模板原样生成仅含 21 字段表头的 `manifest.csv`；
- 不创建虚假图片记录；
- 创建 `images`、`annotations`、`setup_photos`、`reports`；
- 生成 `batch-info.json`、`README-COLLECTION.txt` 和初始化文件 `SHA256SUMS.txt`；
- 初始化失败时只删除本次明确创建的文件和空目录，不递归删除，不接触既有目录；
- 退出码为 `0/1/2/3`，分别表示成功、输入或冲突、模板或配置错误、内部错误。

### 7. batch-info结构

稳定字段：

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

`manifest_schema_version` 固定引用 `0.1`，`created_at` 使用带时区 ISO 8601，`permission_status` 默认只能是 `pending`，不会自动写成 `approved`。

审计器自动读取 `data-root\batch-info.json`，检查字段、必填值、拍摄参数完整性，以及 `batch_id`、`source_type`、`collector`、`device_id` 与 manifest 的一致性。隐私和授权仍然只来自人工声明与复核。

### 8. 图像质量指标

逐图计算：

```text
record_id
image_relpath
sha256
file_size_bytes
width
height
channels
aspect_ratio
mean_gray
std_gray
laplacian_variance
underexposed_ratio
overexposed_ratio
readable
quality_status
quality_flags
quality_messages
```

支持：

```text
UNREADABLE_IMAGE
LOW_RESOLUTION
EXTREME_ASPECT_RATIO
POSSIBLE_BLUR
SEVERE_BLUR
POSSIBLE_UNDEREXPOSURE
POSSIBLE_OVEREXPOSURE
DUPLICATE_CONTENT
RESOLUTION_OUTLIER
```

所有标记可以共存。工具只读打开图片，不写回、不裁剪、不移动、不删除原图。

### 9. SHA-256内容重复检测

- 对原始文件字节计算 SHA-256。
- 不同 `record_id` 和不同 `image_relpath` 的 SHA-256 完全相同时标记 `DUPLICATE_CONTENT`。
- 报告输出稳定的 `duplicate_group_id`、`sha256`、`record_ids`、`image_relpaths`。
- 测试确认两个不同文件名的相同字节文件被归入同一个重复组。
- 不做感知哈希，不安装 `imagehash`，不自动删除、移动或修改重复文件。

### 10. 质量阈值配置

`image-quality-v0.1.json` 集中包含分辨率、长宽比、Laplacian、暗亮像素、灰度均值、曝光面积比例、精确重复级别和尺寸离群级别。

主要第一版工程初始值：

- 最低分辨率：`640×480`
- 长宽比：`0.5—2.0`
- 模糊 WARN：Laplacian 方差低于 `100.0`
- 严重模糊：低于 `20.0`
- 暗像素上界：`20`
- 亮像素下界：`235`
- 灰度均值 WARN：低于 `45.0` 或高于 `210.0`
- 暗/亮像素比例 WARN：`0.35`
- 尺寸离群：批次至少 `4` 张且少数尺寸占比不高于 `0.25`

配置明确声明尚未经过真实快递数据验证，必须由首批 20—50 张完全脱敏图片校准。缺字段、类型错误、范围错误和阈值次序错误均明确返回退出码 `2`。

### 11. 自动测试结果

最终执行 `unittest discover`：

- 总数：59
- 通过：59
- 失败：0
- 错误：0

组成：

- 第一轮 manifest 测试：21
- 第二轮批次初始化测试：12
- 第二轮图像质量审计测试：26

所有测试图片均由 OpenCV 在临时目录运行时生成，未向 Git 提交图片。

### 12. 合成批次端到端验证

在 `TemporaryDirectory` 中完成初始化、生成图片、填写 manifest、运行第一轮校验器、运行第二轮审计器、检查报告并自动清理。

结果：

```text
初始化退出码：0
第一轮校验器退出码：1
第二轮审计器退出码：1
正常图片：PASS / NONE
模糊图片：FAIL / SEVERE_BLUR
欠曝图片：FAIL / SEVERE_BLUR,POSSIBLE_UNDEREXPOSURE
过曝图片：FAIL / SEVERE_BLUR,POSSIBLE_OVEREXPOSURE
重复内容A：WARN / DUPLICATE_CONTENT
重复内容B：WARN / DUPLICATE_CONTENT
不可读文件：FAIL / UNREADABLE_IMAGE
批次总状态：FAIL
重复内容组数：1
JSON报告：成功生成
CSV报告：成功生成，BOM=efbbbf
临时目录清理结果：True
```

第一轮校验器退出码为 `1` 是受控预期，因为端到端批次故意包含一个无法解码文件。

### 13. 第一轮兼容性验证

- 第一轮 21 项测试全部继续通过。
- 第一轮合法示例仍为 6/6 通过，退出码 `0`。
- 第一轮 CLI 参数保持 `--manifest`、`--data-root`、`--schema`、`--report`、`--check-files`。
- 第一轮退出码 `0/1/2/3` 未改变。
- 第一轮错误代码、枚举、路径规则和隐私规则未复制或修改。
- 第二轮审计器直接调用 `validate_manifest()` 完成结构验证。
- 第一轮“同一路径重复”仍由 `DUPLICATE_IMAGE_RELPATH` 发现。

### 14. 环境复验

- 正式 Python：3.12.13
- `pip check`：`No broken requirements found.`
- PyTorch：2.13.0+cu130
- CUDA：True
- GPU：NVIDIA GeForce RTX 5060 Laptop GPU
- OpenCV：5.0.0
- NumPy：2.4.4
- pandas：3.0.3

本轮没有安装、升级或降级任何 Python 包或系统工具，没有修改 PATH、默认 Python、PowerShell 执行策略、Miniconda base、CUDA、cuDNN、IDE 全局设置、其他环境或 `F:\SecurityLab`。

### 15. Git状态

- 分支：`feat/training-pilot-batch-audit-v01`
- 实现提交：`c99efa44498017f469dda32ed58dda91485edc37`
- 实现提交信息：`feat(training): add pilot batch and image quality audit tools`
- 实现暂存差异：8 个文件，2490 行新增，SHA-256 为 `72907A7B4F2F29A6375A0C26904236509B958CD40C4606A919046CD7941C5498`
- 实现提交已经推送到 `origin/feat/training-pilot-batch-audit-v01`。
- 本反馈按任务允许拆为第二个纯文档提交，原因是先取得并记录真实实现提交哈希和首次推送结果。
- `Get-Command gh -ErrorAction SilentlyContinue` 返回不可用；未安装 GitHub CLI。
- Compare 入口：`https://github.com/shiqi64728/jianzheng-package-trace/compare/main...feat/training-pilot-batch-audit-v01?expand=1`

### 16. 已知限制

- Laplacian 方差只是筛查指标；纯色纸箱可能天然低分。
- 深色或浅色纸箱可能分别触发欠曝或过曝候选，必须人工查看。
- SHA-256 只能发现字节完全相同的文件，无法发现裁剪、重编码、压缩或轻微修改后的重复内容。
- 自动工具不能证明图片已经完全脱敏，不能判断是否取得站点授权。
- 自动工具不能确认损伤类型、严重程度或首次异常节点的业务语义。
- 第一版阈值尚未用真实试采集分布校准。

### 17. 未完成事项

本轮开发目标已完成。以下事项明确未执行：

- 真实快递图片或站点数据接入；
- 首批 20—50 张真实试采集审计；
- 阈值校准；
- 感知哈希；
- 正式标注工具；
- 模型训练、摄像头、前端或后端；
- 第三轮开发。

### 18. 风险

- 未校准阈值可能对纯色、深色、浅色或反光纸箱产生 WARN/FAIL 偏差。
- `permission_status`、`privacy_status` 和 `privacy_method` 由人工填写，错误声明不会被图像质量算法纠正。
- WPS/Excel 仍可能改变 ID、时间或编码，保存后必须重新校验。
- E 盘为外置盘，正式批次写入和审计期间必须保持稳定连接。
- 报告包含文件 SHA-256，应按项目数据管理要求保存，不应提交到 Git。

### 19. 回滚方法

实现提交已形成，优先使用：

```powershell
git revert c99efa44498017f469dda32ed58dda91485edc37
```

反馈文档提交需要单独回滚时使用其最终提交哈希执行 `git revert <反馈提交哈希>`。回滚代码不会触碰仓库外试采集批次或原始图片。

### 20. 给成员C的20—50张试采集要求

1. 只使用 3—5 个自有纸箱和完全脱敏样本。
2. 固定同一台手机、后置主摄、1× 倍率和图片比例。
3. 不使用数码变焦、美颜、滤镜或人像模式。
4. 保持 HDR 设置一致。
5. 使用原图传输，不经微信普通图片压缩。
6. 记录设备 ID、手机型号、镜头、分辨率、比例、HDR、滤镜、光照和背景。
7. 保留原始文件，不裁剪、不重编码、不覆盖。
8. 不采集姓名、手机号、地址、运单号、人脸、身份证或站点标识。
9. 每张图片填写一条真实 manifest 记录。
10. 提交前运行第一轮 manifest 校验和第二轮图像质量审计。
11. 将所有 FAIL 修正或补采；WARN 必须人工查看。
12. 提交后由成员 A 独立复验。

### 21. 下一轮建议

本轮不执行第三轮，只提出以下建议：

1. 成员 C 采集第一批 20—50 张完全脱敏测试图片。
2. 成员 A 使用第二轮工具进行真实试采集审计。
3. 根据实际分辨率、亮度和 Laplacian 分布调整阈值。
4. 根据试采集结果决定是否进入标注工具准备。

## 数据路线过渡：公开数据为主、人工采集为补充

### 1. 过渡原因

项目已经完成方案 A 的公开数据获取，训练数据路线由“成员 C 大规模人工采集”调整为“公开数据集和公开资料为主，少量类别缺口补拍，少量 N1/N2/N3 连续节点验证”。本轮只整理和迁移预存文档，不执行公开数据治理适配、外部 manifest、类别映射程序或模型训练。

### 2. 开始前工作树状态

开始分支为 `feat/training-pilot-batch-audit-v01`，存在两项预存变化：

```text
 M docs/dataset/pilot-batch-workflow-v0.1.md
?? docs/dataset/member-c-collection-guide-v0.1.md
```

远程地址为 `https://github.com/shiqi64728/jianzheng-package-trace.git`。E 盘状态为 `Healthy / OK`。两项变化不是上一轮公开数据治理任务生成的，因此没有执行 restore、reset、clean 或删除。

### 3. 两份预存文档内容审查

两份文件均为有效 UTF-8 纯 Markdown，无空文件、NUL 字节、乱码、冲突标记或二进制内容。未发现真实姓名、手机号、地址、运单号、Token、Cookie、密码、私钥或 Roboflow 认证信息。

保留价值包括：21 字段现实映射、一张图片一行、批量导入、匿名 ID、固定手机、后置主摄、1× 倍率、关闭滤镜/美颜/人像模式、原图传输、隐私与授权、manifest 校验、图像质量审计以及 N1/N2/N3 不得猜测的规则。旧内容仍把 20—50 张试采集放在默认入口，需要按新路线收窄。

### 4. Stash备份和哈希

原始文件 SHA-256：

```text
docs/dataset/pilot-batch-workflow-v0.1.md
FEBB539EA45AD571740D07A5FEC0DDE6D39A71968D4FCC564D0651C209DE46C2

docs/dataset/member-c-collection-guide-v0.1.md
6B4C581D58F4B4BA72BC5AEE2D2A65D767759ED98806516368732ABF92C0A875
```

回滚备份：

```text
stash@{0}: On feat/training-pilot-batch-audit-v01: preexisting member-c collection docs before external-data route migration
stash commit: a05a8c51396e2c90346df03c65f59778f993b22d
```

通过 `git stash show --name-status --include-untracked "stash@{0}"` 确认 stash 同时包含修改文件和未跟踪文件。恢复时使用 `git stash apply`，没有执行 `pop`、`drop` 或 `clear`。

### 5. 文档分支

工作树清理后执行 `git fetch origin`、切换 `main` 并使用 `git pull --ff-only origin main` 更新。`main` 从 `ce70e14` 快进到 `c31ae95c143a6d76c66e0323adff9b379e40f509`，与 `origin/main` 一致。随后创建：

```text
docs/external-data-route-transition-v01
```

stash 在新分支应用成功，无冲突。

### 6. 修改和新增文件

修改：

```text
docs/dataset/pilot-batch-workflow-v0.1.md
docs/feedback/r9000p-main-training.md
```

新增：

```text
docs/dataset/member-c-collection-guide-v0.1.md
docs/dataset/data-source-strategy-v0.1.md
```

没有重命名或删除文件；没有修改代码、测试、schema、配置、模板或 `.gitignore`。

### 7. pilot batch流程的新定位

pilot batch 流程不再用于大规模人工采集。它保留为 D01、D05、明确 D04 缺口补拍、少量自有包裹连续节点验证、现场演示和公开数据域差异对照的接收与质量工具。采集量由明确缺口决定，不再设置为了凑规模的默认数量目标。

21 字段合同、初始化工具、manifest 校验器和图像质量审计器继续有效，但只处理真实自有或明确授权的补缺/验证数据；公开数据集图片不得伪造内部物流字段。

### 8. 成员C职责的新定位

成员 C 现在优先负责：

1. 抽查 `defect-cardboard` 的 `dent`、`hole` 和 `dirt`，重点复核 `dirt` 是否符合 D04；
2. 抽查 Damaged Box Detection 的 normal/damaged 语义、错标、非纸箱样本、背景偏差、增强与重复；
3. 抽查 TAMPAR reference/tampered 配对并记录争议；
4. 不改动公开数据 raw、原标签、许可证或来源登记；
5. 仅在明确任务下补拍 D01、D05、明确 D04、少量连续节点和演示样本。

成员 C 不再承担大规模普通破损采集、大批量快递站拍摄、私人运单网页爬取、个人信息收集或社交平台面单图片抓取。

### 9. 公开数据与补缺采集边界

公开数据先经过来源登记、许可证和类别审计、重复/split 泄漏检查及人工映射复核，再形成训练候选。公开数据没有真实内部业务字段，不能证明 N1/N2/N3 异常节点或责任。

人工补采仅解决 D01、D05、明确 D04、真实连续节点和演示/域差异缺口。补采必须使用自有或明确授权纸箱、真实时间与匿名 ID，并继续执行 manifest 和图像质量验收。

### 10. 文档一致性检查

已搜索“成员 C”“大规模采集”“人工采集”“20—50”“快递站”等路线词。历史反馈和既有配置中的 20—50 描述作为第二轮交付历史及工具阈值校准约束保留，没有修改代码或配置。新增路线说明明确：第二轮工具没有废弃，而是转为补缺采集和真实试验数据质量工具。

三份当前操作文档均一致声明公开数据为主、人工采集为补充，且 TAMPAR/公开图片不得伪造连续节点。

### 11. 安全检查

对本轮新增和修改内容执行 UTF-8/二进制检查、冲突标记扫描和凭据/隐私模式扫描。结果：没有新增 NUL 字节、乱码、真实手机号、长数字运单号、凭据、私钥、Roboflow 认证信息或个人路径。本轮内容中的 Token、Cookie、手机号、地址和运单号只出现在禁止记录的规则中；历史反馈保持只追加、不覆盖。

### 12. Git状态

本轮工作限定在 `docs/` 下的 Markdown 文件。提交前使用显式路径暂存，不使用 `git add .`。实现提交和推送结果以本轮最终返回为准。本节不表示公开数据治理功能已经完成。

### 13. 回滚方法

原始两份预存文档仍完整保存在 `stash@{0}`。提交前可从 stash 只读查看或在干净临时分支使用 `git stash apply "stash@{0}"` 恢复；不得直接 pop。文档提交形成后，优先使用 `git revert <本轮文档提交哈希>` 回滚远程历史。stash 在用户确认文档 PR 合并前保持不删除。

### 14. 后续公开数据治理任务恢复条件

只有满足以下条件后，才恢复公开数据治理开发：

1. 本文档分支完成审查并合并到 `origin/main`；
2. 本地 `main` 与 `origin/main` 一致且工作树干净；
3. 两个第二轮提交仍可在 `origin/main` 中验证；
4. E 盘和正式 Python 环境通过前置检查；
5. 外部数据最终核验、许可证、来源登记、数量和 TAMPAR 哈希全部通过；
6. 原 stash 按用户决定保留或在后续独立轮次安全清理。

下一轮不得把本次文档整理误报为公开数据治理功能已经完成，也不得跳过治理审计直接训练模型。

## 公开数据集治理与统一适配

### 1. 前置分支合并验收

执行 `git fetch origin` 后，`origin/main` 为 `bb72bb2a1f27811f478bd52b6a3d8ba456230add`。以下祖先检查退出码全部为 `0`：

- 第二轮实现：`c99efa44498017f469dda32ed58dda91485edc37`；
- 第二轮反馈：`49c0cee147f87956e24d8988567aa0c638d37de6`；
- 数据路线文档：`8ae5147818bbc65688d75a801a20acf16f3177f6`。

本地 `main` 使用 `git pull --ff-only origin main` 快进到同一提交，然后从该提交创建 `feat/training-external-data-governance-v01`。未执行 merge、rebase 或 cherry-pick。

### 2. 本轮目标

建立公开数据来源治理、统一外部 manifest、许可证和类别映射审计、精确重复与 split 泄漏审计、隔离清单、成员 C 审核工作清单及训练任务可用性报告。外部 manifest 与内部 21 字段连续物流 manifest 完全隔离。本轮没有训练模型、下载数据、下载权重、安装依赖或导出 ONNX。

### 3. 开始前 Git 状态

开始时工作树干净，远程地址为 `https://github.com/shiqi64728/jianzheng-package-trace.git`，无用途不明的未跟踪文件。`.git/MERGE_HEAD`、`.git/rebase-merge`、`.git/rebase-apply`、`.git/CHERRY_PICK_HEAD` 均不存在。E 盘 `HealthStatus=Healthy`、`OperationalStatus=OK`。

### 4. Stash 状态

保留项仍为：

```text
stash@{0}: On feat/training-pilot-batch-audit-v01: preexisting member-c collection docs before external-data route migration
stash commit: a05a8c51396e2c90346df03c65f59778f993b22d
```

本轮没有 apply、pop、drop 或 clear stash。

### 5. 外部数据区完整性验收

只读检查了 README、方案 A 获取报告、最终核验、结构变更报告/清单、来源登记、许可证、引用、下载完整性、映射、TAMPAR 和国家邮政局统计材料。结果：最终核验 `10/10`；图片 `7,935` 张且全部可读；defect-cardboard `1,036` 张、`16,592` 条标注；Damaged Box Detection `4,148` 张、已知重复额外图片 `176` 张；TAMPAR `2,751` 个图像资产，归档 `6,407,977,888` 字节；国家邮政局公开文章 `36` 篇、结构化指标 `406` 行。没有 `.partial` 或未完成下载分片。

TAMPAR 归档：MD5 `7a92e796a263998ab5437399f1771fcb`，SHA-256 `08a2e721b28665a75db7c8a90c91b2a98905d05d74c568950d11b081935241e1`，与既有核验一致。

### 6. raw 开始前快照

新增 `E:\JianZhengData\external\reports\governance-preflight-snapshot-v0.1.json`。关键值：

- `raw`：7,952 个文件，13,339,506,276 字节，metadata tree SHA-256 `eb6840b344f1a071fdd99b14984b5e3b38f67b07fad99aafd11f48960047d07c`；
- defect-cardboard：1,043 个文件，97,031,634 字节；
- Damaged Box Detection：4,152 个文件，285,199,215 字节；
- TAMPAR：2,757 个文件，12,957,275,427 字节；
- SPB raw HTML：42 个文件，3,194,399 字节；
- licenses：1 个文件，18,657 字节；citations：3 个文件，940 字节；
- 另记录 TAMPAR 归档、三份 defect COCO、两份 TAMPAR COCO 和 CC BY 4.0 法律文本的 SHA-256。

### 7. external/tools 审查

只读审查 8 个脚本：`audit_external_datasets_v01.py`、`build_final_report_v01.py`、`crawl_spb_stats_v01.py`、`download_roboflow_public_v01.py`、`download_zenodo_multipart_v01.py`、`finalize_structure_report_v01.py`、`init_registry_v01.py`、`update_registry_v01.py`。

复用了流式 SHA-256、图片/COCO 校验、精确重复分组和归档安全检查等通用思路，并在 Git 仓库内重新实现为参数化、可测试、只读 raw 的工具。没有整体复制脚本；没有修改 `external/tools`；没有执行下载、网络爬取、浏览器自动化或解压/删除逻辑；没有读取、输出或提交 Roboflow 凭据。硬编码绝对路径和一次性报告/登记逻辑未复用。

### 8. 实际执行命令

主要执行链为：

```powershell
& $python -m unittest discover -s "E:\Artificial-intelegence-training\tests" -v
& $python scripts\dataset\validate_external_registry.py --source-registry ... --licenses-dir ... --citations-dir ... --external-schema ... --external-root ... --report ...
& $python scripts\dataset\build_external_manifests.py --external-root ... --source-registry ... --external-schema ... --class-mapping ... --output-dir ... --report ...
& $python scripts\dataset\audit_external_datasets.py --external-root ... --manifests-dir ... --source-registry ... --class-mapping ... --report-dir ...
& $python scripts\dataset\build_external_review_worklist.py --manifests-dir ... --report-dir ... --seed 20260803
& $python -m ruff check scripts\dataset tests\dataset
& $python -m ruff format --check scripts\dataset tests\dataset
& $python -m py_compile <scripts/dataset 与 tests/dataset 的 18 个 Python 文件>
& $python -m pip check
```

所有真实输出只写入 `converted`、`quarantine` 和 `reports`。一次初始局部 unittest discover 因 start directory 导致模块路径不适用，随后严格使用项目规定的完整 discover 命令复验，产品测试为 92/92 通过。

### 9. Git 仓库新增和修改文件

实现提交新增 17 个文件：

- 配置：`configs/training/external-source-schema-v0.1.json`、`configs/training/external-class-mapping-v0.1.json`；
- 模板：`dataset/external/templates/README.md`、`external-manifest-v0.1.template.csv`、`external-manifest-v0.1.example.csv`；
- 文档：`docs/dataset/external-data-governance-v0.1.md`、`docs/dataset/external-class-mapping-v0.1.md`；
- 脚本：`scripts/dataset/external_data_common.py`、`validate_external_registry.py`、`build_external_manifests.py`、`audit_external_datasets.py`、`build_external_review_worklist.py`；
- 测试：`tests/dataset/external_test_support.py` 以及 4 个 `test_*.py`。

本反馈章节仅追加修改 `docs/feedback/r9000p-main-training.md`。没有删除或重命名 Git 文件；未修改 `.gitignore`，因为真实数据和输出位于仓库外，且采用显式暂存路径即可防止误提交。内部 manifest schema、图像质量阈值以及前三个既有 CLI 均未修改。

### 10. 外部数据区新增和修改文件

新增 4 个统一 manifest：

```text
converted/manifests/defect-cardboard-v0.1.csv
converted/manifests/damaged-box-detection-v0.1.csv
converted/manifests/tampar-pairs-v0.1.csv
converted/manifests/public-stats-v0.1.csv
```

新增 4 个隔离清单：

```text
quarantine/manifests/ambiguous-class-records-v0.1.csv
quarantine/manifests/duplicate-records-v0.1.csv
quarantine/manifests/blocked-license-records-v0.1.csv
quarantine/manifests/unresolved-pairs-v0.1.csv
```

新增 3 个成员 C 工作清单，以及 registry validation、manifest build、license、class mapping、duplicate、readiness、audit summary、preflight/postflight/invariance 共 11 个报告文件，总计新增 22 个派生文件。真实端到端修正后只覆盖了本轮新生成的同名派生输出；没有修改任何本轮开始前已存在文件，没有删除或移动文件。

### 11. 外部来源 schema

`external-source-schema-v0.1.json` 共 47 个唯一字段，包含要求的 31 个基础字段，并扩展原图/标注引用、TAMPAR 配对和统计记录字段。枚举覆盖 classification、bbox、polygon、pair、statistics、none，以及映射、任务和隔离状态。所有路径均相对 `E:\JianZhengData\external`，统一使用 POSIX 相对路径。schema 明确禁止 `package_id`、`sequence_id`、`node_id`、`capture_time`、`first_abnormal_node`；实际字段中不存在这些内部业务字段。

模板和示例均带 UTF-8 BOM；模板只有表头；示例只有 4 条虚拟的 classification、bbox、pair、statistics 记录，没有真实外部数据或个人信息。

### 12. 类别映射配置

- `dent -> direct / D02 / damage_detection`；
- `hole -> direct / D03 / damage_detection`；
- `dirt -> candidate / D04 / damage_detection / requires_manual_review=true`；
- `undamagedpackages -> general_only / NORMAL / damage_binary_classification`；
- `damagedpackages -> general_only / ABNORMAL_GENERAL / damage_binary_classification`；
- TAMPAR 默认 `change_detection_only`，不映射 D01—D05；
- 国家邮政局统计 `unmapped / industry_statistics`，许可证/引用未形成独立证据时输出 blocked。

### 13. defect-cardboard 适配

真实解析 train/valid/test COCO，共生成 1,036 条图像级记录并保留 16,592 条嵌套稳定标注引用。原 image id、annotation id、类别、bbox、宽高、split、图像 SHA-256 和 COCO 相对路径均可追溯。没有把 bbox 伪造成 polygon，没有修改 COCO、没有复制图片。

状态为 accepted 711、review_required 325。含 dirt 的图像记录 184 条，均保持 D04 候选语义；无标注图像等不明确情况不会被伪造损伤标签。

### 14. Damaged Box Detection 适配

生成 4,148 条分类记录：damagedpackages 2,478、undamagedpackages 1,670；保留 train 3,744、valid 302、test 102。只映射到 ABNORMAL_GENERAL/NORMAL，没有生成 D01—D05。`parent_or_augmented_from` 不做无证据猜测，增强语义只记录在 notes。精确重复只分组，不删除图片。

### 15. TAMPAR 配对适配

生成 2,751 条资产记录并保留真实 COCO 的 732 条 polygon/bbox/keypoints 引用；未扩展不存在的损伤标注。配对仅依据同 split、明确 parcel 标识和相邻采集时间形成 probable：949 条；无法可靠配对的 66 条为 unresolved 并进入审核；confirmed 为 0。其余 base、normal box、UV map 等保持原用途。直接位于 unlabeled/test 的 66 个文件统一标为 `original_operation_type=unlabeled`，不把文件名误当作操作类型。

未把 reference/tampered 伪造成 N1/N2，未生成内部 package、sequence、node、capture_time 或责任字段。

### 16. 国家邮政局统计适配

生成 406 条 statistics 记录，保留文章标题、发布日期、统计期间、指标、数值、单位、同比、获取时间和原始 HTML SHA-256。统计数据不进入图像训练 manifest。由于该来源没有独立进入 source registry，且缺少独立许可证和引用文件，406 条全部 blocked，仅可作为待补证的行业背景资料。

### 17. 许可证审计

四类生成 manifest 中，3 个图像来源许可证/引用证据通过，SPB 统计来源 1 个 blocked，原因组合为 `SOURCE_NOT_IN_REGISTRY|LICENSE_MISSING|CITATION_MISSING`。来源登记验证读取 6 行，3 个已下载来源全部 accepted，0 error、4 warning；warning 仅对应未下载的 metadata-only 来源尚未保留 citation/license 文件，不会进入 accepted 或训练候选。

### 18. 类别映射审计

审计表逐来源/原始类别汇总 image count、annotation count、映射状态、项目类别、任务、人工审核、允许用途、禁止用途和风险。dent/hole 为直接候选，dirt 保持人工审核候选，二分类不细分损伤类型，TAMPAR 仅用于变化检测/表面归一化，SPB 不映射图像类别。

### 19. 数据集内部重复审计

精确 SHA-256 共发现 168 个重复组、176 张额外重复图片，均位于 Damaged Box Detection。隔离清单列出重复组全部 344 个成员记录，原文件未删除。defect-cardboard 和 TAMPAR 未发现精确重复组。

### 20. 跨数据集重复审计

精确 SHA-256 跨数据集重复组为 0，标签冲突组为 0。此结论只覆盖精确文件内容，不等价于感知近重复审计。

### 21. 跨 split 泄漏审计

精确 SHA-256 跨 split 重复组为 0，当前没有已证实的精确 split 泄漏。Damaged Box Detection 的 168 个重复组均在 train 内，但后续冻结数据版本前仍应按重复组去重选样，并补充感知近重复检查。

### 22. 隔离清单

- ambiguous class：250 条，其中 184 条含 dirt 的 D04 候选、66 条 TAMPAR unresolved；
- duplicate records：344 条，对应 168 个精确重复组；
- blocked license：406 条 SPB statistics；
- unresolved pairs：66 条 TAMPAR。

清单只记录相对路径、原因和建议动作，没有移动、删除、改名或修改原文件。

### 23. 成员 C 人工审核工作清单

固定 seed `20260803`，稳定 SHA-256 排序，不使用 Python 内置 `hash()`。输出均为 UTF-8 BOM，只含相对路径，审核结论列为空：

- defect-cardboard：90 条（dent 20、hole 20、dirt 50）；
- Damaged Box Detection：424 条（normal 30、damaged 50、重复记录 344）；
- TAMPAR：96 条（probable 30、unresolved 66、confirmed 0）。

没有复制图片，输入顺序变化不改变抽样结果。

### 24. 可训练性评估

- 完好/损伤二分类：`ready_with_review`；
- D02/D03 目标检测：`ready_with_review`；
- D04 候选目标检测：`not_ready`；
- 实例分割：`not_ready`；bbox 不能证明损伤实例 polygon；
- TAMPAR 前后变化检测：`ready_with_review`；
- TAMPAR 表面归一化：`ready_with_review`；
- 真实连续物流节点定位：`not_ready`。

所有 `ready_with_review` 仍须满足许可证证据、人工审核、重复控制和版本冻结条件，不代表已经批准训练。

### 25. 新增自动化测试

新增 33 项测试：registry 6、manifest builder 11、audit 8、review worklist 8。全部使用 `TemporaryDirectory`、合成图片、虚拟 COCO/分类目录/TAMPAR/许可证/registry，不依赖 13.35 GB 真实数据。覆盖要求的映射、标注保留、缺图失败、原文件不变、重复/冲突/split、readiness、稳定抽样、BOM、相对路径和空审核结论。

### 26. 原 59 项兼容性

最终完整测试为 92/92 通过、0 failure、0 error；原 59 项全部继续通过。未修改：

```text
configs/training/manifest-schema-v0.1.json
configs/training/image-quality-v0.1.json
scripts/dataset/validate_manifest.py CLI
scripts/dataset/init_pilot_batch.py CLI
scripts/dataset/audit_image_quality.py CLI
```

### 27. 真实数据只读端到端验证

执行顺序为 registry validation → 4 个 manifest 构建 → 7,935 张图片/17,324 条标注完整性审计 → license/mapping/duplicate/split 审计 → 4 个隔离清单 → 3 个工作清单 → readiness 报告。完整性 issue 为 0，`raw_modified=false`。manifest 行数分别为 1,036、4,148、2,751、406。

首次真实生成后发现 66 个直接位于 TAMPAR `unlabeled/test` 的文件名不应被视为操作类型；修正适配逻辑、增加回归测试并完整复跑生成/审计/工作清单，最终语义为 `unlabeled`。

### 28. raw 结束后快照及不变性

新增 `governance-postflight-snapshot-v0.1.json` 和 `governance-raw-invariance-v0.1.json`。比较 35 个文件数、总字节、最新 mtime、metadata tree SHA-256 和代表性内容 SHA-256 检查项，最终 `35/35` 一致、`changed_check_count=0`、`raw_unchanged=true`。

第一次比较器使用区分大小写的排序，与 Windows 前置快照的 case-insensitive 排序算法不一致，产生 2 个 metadata tree 假阳性；改正比较器排序后重新计算，文件数、字节、mtime 和内容哈希始终未变。最终 raw 仍为 7,952 个文件、13,339,506,276 字节，TAMPAR SHA-256 仍为 `08a2e721b28665a75db7c8a90c91b2a98905d05d74c568950d11b081935241e1`。

### 29. Ruff 和 py_compile

`ruff check` 全部通过；`ruff format --check` 报告 18 个 Python 文件已格式化；对 `scripts/dataset` 和 `tests/dataset` 的 18 个 Python 文件执行 `py_compile` 全部通过。实现使用 Python 3.12、类型标注、argparse、pathlib、明确 JSON/CSV 编码；没有 bare except、吞异常、内置 `hash()` 稳定 ID 或凭据逻辑。

### 30. 环境复验

正式解释器仍为 `D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe`：Python 3.12.13，pip check 无损坏依赖，PyTorch 2.13.0+cu130，CUDA=True，GPU=`NVIDIA GeForce RTX 5060 Laptop GPU`，OpenCV 5.0.0，NumPy 2.4.4，pandas 3.0.3。本轮未安装或升级依赖，未修改 PATH、PowerShell 策略、Miniconda base、CUDA/cuDNN 或 IDE 全局设置。

### 31. Git 状态

实现提交为 `574aa3070a0e762805dbfe76a00f346eb4fb70d1`，提交说明 `feat(training): add external dataset governance and adapters`。实现提交包含 17 个新增文件、3,198 行新增。反馈采用独立提交；反馈提交哈希和推送后的最终工作树状态以本轮最终回复为准。暂存均使用显式文件路径，未使用 `git add .`。

### 32. 已知限制

1. SPB 统计缺少独立 source registry、license 和 citation 证据，当前全部 blocked；
2. D04 的 dirt 语义不能自动等同受潮；
3. TAMPAR 没有 confirmed pair，probable 仍需人工确认；
4. TAMPAR 和公开图片不提供真实物流节点或责任事实；
5. Damaged Box Detection 只能支持二分类，不能证明 D01—D05；
6. 当前重复审计为精确 SHA-256，不覆盖视觉近重复；
7. 本轮没有建立可训练冻结版本，也没有训练任何模型。

### 33. 未完成事项

成员 C 尚未填写 610 条工作清单记录；D04 尚未批准或否决；重复组尚未从训练候选版本中按组处理；TAMPAR probable/unresolved 尚未人工复核；首个训练任务的数据版本尚未冻结；SPB 许可证/引用证据尚未补齐。上述事项均按范围留给下一轮，本轮未扩展到训练。

### 34. 风险

主要风险为 dirt 类别歧义、二分类背景偏差、增强/近重复导致的泛化高估、TAMPAR probable 误配、许可证证据不足以及把公开外观数据错误外推为真实物流责任证据。训练前必须以人工审核结论和冻结数据版本为准，跨 split 应按内容组而非单文件随机拆分。

### 35. 回滚方法

Git 实现可用 `git revert 574aa3070a0e762805dbfe76a00f346eb4fb70d1` 回滚；反馈提交形成后单独 revert 该提交。外部区 22 个文件全部为本轮派生输出，可按本节第 10 项列出的显式路径删除后重新生成；不得删除、移动或覆盖 raw、SPB raw HTML、licenses 或 citations。原 stash 保持不动，不得 pop/drop/clear。

### 36. 推荐的首个模型任务

推荐在成员 C 审核完成后，先冻结仅含已批准 dent/hole 的 D02/D03 目标检测数据版本：保留真实 bbox，排除未批准 dirt，按精确重复组和后续近重复组控制 split。该建议只是下一轮候选，本轮未训练模型。

### 37. 下一轮建议

仅建议依次完成：成员 C 审核工作清单；批准或否决 D04 候选；清理训练候选中的跨 split/近重复风险；冻结第一个任务的数据版本；然后在二分类、D02/D03 检测或 TAMPAR 变化检测中只选择一个基线。暂不进行多任务融合，不声称已具备真实连续节点定位或责任认定能力。

## 首个正式基线：D02/D03 YOLO26n目标检测

### 1. 本轮目标

完成且只完成 `detect-d02-d03-yolo26n-baseline-v0.1`：以 defect-cardboard 为唯一数据源，冻结 D02 表面凹陷与 D03 纸箱破口二类 YOLO Detect 数据，使用官方 `yolo26n.pt` 完成 3 epoch smoke、100 epoch 正式训练、best/last 验证、独立 test、20 张定性样例、失败分析和外部 release。未执行第二个模型实验、分割、变化检测、连续节点、责任判定或部署。

### 2. Git前置验收

开始时 `origin/main` 与本地 main 均为 `337248254c590bb4b783a8524d763cd2e2781ca6`，工作树干净，无 merge/rebase/cherry-pick，E 盘为 Healthy/OK。治理实现 `574aa3070a0e762805dbfe76a00f346eb4fb70d1` 与治理反馈 `055b988592570775d3db66b6eafd225e498805ab` 均是 `origin/main` 祖先。随后创建 `experiment/training-d02-d03-yolo26n-baseline-v01`。旧 stash `a05a8c51396e2c90346df03c65f59778f993b22d` 仅查看，未 apply/pop/drop/clear。

### 3. 环境验收

正式解释器为 `D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe`，Python 3.12.13、PyTorch 2.13.0+cu130、torchvision 0.28.0+cu130、Ultralytics 8.4.102、OpenCV 5.0.0、NumPy 2.4.4、pandas 3.0.3。CUDA=True，GPU 为 `NVIDIA GeForce RTX 5060 Laptop GPU`，总显存 8,546,484,224 字节；最小 CUDA 前向/反向验证通过，`pip check` 通过。本轮未安装或升级依赖。

### 4. 治理结果验收

实际读取 `E:\JianZhengData\external\converted`、`quarantine` 和 `reports`。D02/D03 detection 为 `ready_with_review`；defect-cardboard 许可证审计为 passed、无 blocking issue。源 manifest 共 1,036 张，SHA-256 为 `17135603a70f1d2334d2d88e457d5760b96924c01d528d8b2e488f9746865cc2`；治理 accepted 711、review_required 325。精确重复审计在 defect-cardboard 中未发现阻塞重复，跨数据集/跨 split 重复为 0。

### 5. D02/D03数据筛选规则

只允许 `source=defect-cardboard`、许可证 passed、`quarantine_status=accepted`、`mapped_project_status=direct` 且类别为 dent/hole 的记录；dent 固定映射 D02/class 0，hole 固定映射 D03/class 1。文件缺失、不可解码、非法/越界/非正宽高 bbox、未知类、阻塞/待审、精确重复、源身份跨 split 均会失败或排除，不补标签、不修框。

### 6. dirt排除策略

只要图片存在任何 dirt annotation 就整图排除，即使同时含 dent/hole 也不保留，避免删除 dirt bbox 后将真实 dirt 区域错误监督为背景。实际因 `DIRT_PRESENT` 排除 184 张；另外 141 张因 `QUARANTINE_NOT_ACCEPTED` 排除。

### 7. 数据版本冻结

冻结目录为 `E:\JianZhengData\training\detect-d02-d03-v0.1`，版本 `detect-d02-d03-v0.1`。最终包含 711 张、排除 325 张、包含 11,304 个 bbox。图片内容树 SHA-256 为 `26e256f34046faa36f275d1c701c4df5d02c75236b0ce88cd37785210aa2dda5`，标签内容树 SHA-256 为 `8efc3abdba9329d9399526fe48b73408147706efaa4b782a78091aef7a6dc057`，`dataset-lock.json` SHA-256 为 `6d496281ade6486434c0eb85a473b2bd3e8e5574bcc51ca1d371895851ea6e97`。构建器默认拒绝覆盖已冻结目录。

### 8. COCO到YOLO转换结果

COCO `[x_min,y_min,width,height]` 依据真实图片宽高转换为归一化 `class x_center y_center width height`。class 0 为 `D02_surface_dent`，class 1 为 `D03_carton_tear`。所有图片以普通文件逐字节复制，没有重编码、硬链接或符号链接；711/711 个源与副本 SHA-256 一致，错配 0。自定义验证器确认空标签、缺失配对、非法类/坐标、重复、跨 split 重复均为 0；Ultralytics 实际预检成功读取全部 split。

### 9. train/val/test统计

保留原数据集 train/valid/test，只将目录名 valid 规范为 val，未随机重拆 test。最终 train 614 张、val 64 张、独立 test 33 张；Ultralytics 预检分别扫描 614/64/33 张，无 corrupt 或 background-only 记录。

### 10. 类别分布

D02 表面凹陷 bbox 为 9,514，D03 纸箱破口 bbox 为 1,790，总计 11,304。类别明显不平衡，D02 bbox 约为 D03 的 5.31 倍；该事实保留为基线限制，本轮未通过重采样或手工调参改变分布。

### 11. 权重下载来源

仅下载 `yolo26n.pt`，通过当前 Ultralytics 8.4.102 的官方资产解析机制 `ultralytics/assets` 获取，release 为 v8.4.0，来源 URL：`https://github.com/ultralytics/assets/releases/download/v8.4.0/yolo26n.pt`。文件位于 `E:\JianZhengData\models\pretrained\ultralytics\yolo26n.pt`，未下载其他模型规模，未使用第三方镜像。

### 12. yolo26n.pt SHA-256

官方预训练权重大小 5,544,453 字节，SHA-256 为 `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`。来源、时间、大小、mtime、Ultralytics/PyTorch/CUDA 版本和加载结果登记在 `E:\JianZhengData\models\pretrained\ultralytics\yolo26n.metadata.json`，不含认证信息。

### 13. 权重加载验证

正式解释器通过 `YOLO(...)` 加载，任务确认为 detect；使用 640×640 合成公开测试输入在 RTX 5060 Laptop GPU 上完成 CUDA 推理，无架构不兼容、损坏或 fallback。

### 14. Smoke test

`E:\JianZhengData\training\runs\smoke-d02-d03-yolo26n-v0.1` 完成 3/3 epoch，`fraction=0.25`、imgsz 640、请求 batch -1、实际 batch 9；耗时 76.089 秒，peak allocated 4,224,707,584 字节。数据读取、有限 loss、CUDA/AMP、checkpoint、validation 和图表均正常，`results.csv` 无 NaN/Inf，best epoch 为 3。一次宿主 shell 等待超时没有终止训练进程；确认原进程正常完成后只读取结果，没有启动重复 smoke。

### 15. 正式训练参数

100 epoch、patience 25、imgsz 640、batch -1、device 0、workers 4、cache false、seed 42、deterministic true、optimizer auto、pretrained true、AMP true、save true、save_period 10。未手动设置 lr0、momentum、weight_decay、box、cls 或 dfl。

### 16. 正式训练过程

固定目录 `E:\JianZhengData\training\runs\detect-d02-d03-yolo26n-v0.1` 完成训练，未生成 train2/train3。实际 batch 8，实际 100/100 epoch，无 early stop、无 OOM、无 NaN/Inf。2026-08-11 10:49:43+08:00 开始、11:09:23+08:00 结束，总耗时 1,180.176 秒，平均 11.802 秒/epoch，peak allocated GPU memory 4,727,974,912 字节。

### 17. best epoch

按 Ultralytics 一基 epoch 编号解析，best epoch 为 97，last epoch 为 100。`best.pt` 与 `last.pt` 均可加载；正式候选固定为 best.pt。针对一基 epoch 解析已增加回归测试，避免把第 97 轮误报为 96。

### 18. 总体验证指标

best.pt 在 val 上：Precision 0.331108、Recall 0.242798、mAP50 0.193225、mAP50-95 0.083132。last.pt 在 val 上：Precision 0.367590、Recall 0.231518、mAP50 0.192978、mAP50-95 0.080858。以 best.pt 的 mAP50-95 选择正式候选，没有用 test 选模型。

### 19. D02指标

best.pt val 的 D02：Precision 0.292472、Recall 0.192493、AP50 0.131522、AP50-95 0.037191。D02 是当前更弱类别，尤其召回和 AP50-95 较低。

### 20. D03指标

best.pt val 的 D03：Precision 0.369744、Recall 0.293103、AP50 0.254927、AP50-95 0.129074。D03 指标高于 D02，但样本 bbox 数更少，结论仍需扩大真实域验证。

### 21. test指标

存在原始合法独立 test，因此用 best.pt 单独评估：总体 Precision 0.409177、Recall 0.185970、mAP50 0.183131、mAP50-95 0.071481。D02 test 为 0.338012/0.111940/0.113480/0.034279，D03 test 为 0.480342/0.260000/0.252781/0.108682（依次 Precision/Recall/AP50/AP50-95）。没有把 val 称为 test。

### 22. 混淆矩阵

best.pt val 混淆矩阵中正确类别分配 285，D02/D03 跨类混淆 1，背景相关漏检/假阳性 1,989。结论是背景相关错误和漏检占主导，D02/D03 互相混淆不是当前首要问题。

### 23. 预测样例

从独立 test 以 seed 42 确定性抽取 20 张；在 `E:\JianZhengData\training\runs\detect-d02-d03-yolo26n-v0.1\qualitative` 保存 20 张预测图、20 张 GT 可视化和 `qualitative-manifest.csv`。原图未修改，预测没有被描述为人工真值。

### 24. 失败案例分析

`failure-analysis-v0.1.csv` 自动生成 1,065 条记录：low_iou 413、small_target_failure 478、high_confidence_false_positive 33、D02_D03_confusion 16、missed_detection 125；同一对象可对应多个失败类型。实际没有生成 large_target_failure 记录。主要失败方向为小目标、低 IoU 与漏检，未修改标签。

### 25. 模型制品

正式 run 保留 best.pt、last.pt、每 10 epoch checkpoint、results.csv/results.png、BoxF1/PR/P/R 曲线、混淆矩阵、args.yaml、run metadata、val/test 评估和定性结果。外部 release 位于 `E:\JianZhengData\models\releases\d02-d03-yolo26n-baseline-v0.1`，包含 best.pt、model-card.md、metrics.json、dataset-lock.json、experiment-config.json、weight-sha256.txt。模型二进制、图片、runs、数据集和大型日志均未进入普通 Git。

### 26. 模型SHA-256

正式 best.pt 位于 `E:\JianZhengData\training\runs\detect-d02-d03-yolo26n-v0.1\weights\best.pt`，SHA-256 为 `1959fcaf71987e52e5475f7601fc10ca7e40e7b747ddf085705135dccb0ed74f`；last.pt SHA-256 为 `e4e9f4cd6f71efe24bfd85fd571ba931b199f5471e6acfba6e4bf10c1f9ad155`。release 副本哈希与正式 best.pt 一致。

### 27. 自动测试结果

新增 25 项轻量测试：数据构建 18 项、配置/训练元数据 7 项。覆盖 dent/hole 映射、dirt 整图排除、class ID、bbox 归一化与非法范围、缺图、治理状态排除、字节复制与 raw 不变、split/跨 split 重复、YAML、可复现 lock、拒绝覆盖、配置解析、外部模型路径、模型限定、禁止手调 recipe 与一基 epoch。最终总计 117/117 通过，失败 0、错误 0。

### 28. 原92项兼容性

训练前原有测试 92/92 通过；训练后完整回归 117/117 通过，因此原 92 项继续兼容，未通过删除、跳过或放宽旧测试换取通过。

### 29. Ruff和py_compile

正式解释器执行 `ruff check scripts tests` 全部通过；`ruff format --check scripts tests` 报告 24 个 Python 文件已格式化；对 scripts/tests 下 24 个 Python 文件执行 `py_compile` 全部通过。

### 30. 环境复验

训练结束后 `pip check` 再次返回 `No broken requirements found`。Python 3.12.13、PyTorch 2.13.0+cu130、torchvision 0.28.0+cu130、Ultralytics 8.4.102、CUDA=True、RTX 5060 Laptop GPU 均保持不变；复验时 `memory_allocated=0`、`memory_reserved=0`。未修改 PATH、默认 Python、PowerShell 策略、CUDA/cuDNN 或驱动。

### 31. raw不变性

训练前后比较 `E:\JianZhengData\external\raw`：文件数 7,952、总字节 13,339,506,276、最新 mtime、metadata tree SHA-256 均一致；defect-cardboard train/valid/test COCO SHA-256 均一致。`raw-invariance-d02-d03-v0.1.json` 的 5 项检查全为 true，`raw_unchanged=true`。

### 32. Git状态

实现提交为 `504ca5fe5cee7ee554ed0a661dd0fc7ba0c8b3e8`，提交说明 `feat(training): add D02 D03 YOLO26n baseline pipeline`，包含 10 个新增文件、2,399 行。反馈仅追加本章节并采用独立提交；暂存均使用显式路径，未使用 `git add .`。分支为 `experiment/training-d02-d03-yolo26n-baseline-v01`。

### 33. 已知限制

模型只识别 D02 表面凹陷和 D03 纸箱破口。总体与 D02 指标较低，小目标和背景错误明显；类别不平衡且来源为公开数据，与真实快递站拍摄存在域偏差。模型不能识别 D01、D04、D05、NORMAL、二次封装/TAMPAR，不能定位真实物流异常节点或认定责任，输出必须人工复核。

### 34. 未完成事项

本轮目标内事项已完成。范围外仍待后续：成员 C 审核 D04/dirt、真实站点数据采集和独立外部验证、失败样本人工复核、数据增强/不平衡对照、其他任务基线及部署；本轮没有继续执行这些事项。

### 35. 风险

主要风险为公开数据域偏差、D02/D03 类别及框质量噪声、D03 样本相对少、精确重复审计未覆盖视觉近重复、较低召回导致漏检、小目标定位不稳，以及将外观模型结果错误外推为物流节点或责任事实。test 规模仅 33 张，指标置信度有限。

### 36. 回滚方法

Git 实现可用 `git revert 504ca5fe5cee7ee554ed0a661dd0fc7ba0c8b3e8` 回滚；反馈提交形成后单独 revert。外部派生制品可按需显式删除 `E:\JianZhengData\training\detect-d02-d03-v0.1`、两个固定 run 目录、预训练权重目录中的本轮文件及 release 目录后重新构建，但不得删除或修改 `E:\JianZhengData\external\raw`。旧 stash 保持不动。

### 37. 下一轮建议

下一轮只选一个方向并建立对照：优先对 1,065 条自动失败记录做人工归因，针对小目标、背景漏检和 D02 低召回制定单变量增强或类别不平衡实验；也可在冻结同一数据版本上做 YOLO26s 对照。D04 必须先由成员 C 审核后才能训练；TAMPAR、二分类和连续节点应作为独立任务，不能与本基线混在同一轮。不要把当前 test 当作反复调参集。

## D02/D03 YOLO26n 960输入分辨率单变量实验

### 1. 实验假设

在 YOLO26n、官方预训练权重、冻结数据、split、seed 和训练策略完全相同的条件下，只将 `imgsz` 从 640 提高到 960，验证能否改善总体定位质量、D02 Recall 以及小目标/低 IoU 问题。本轮没有训练 YOLO26s、修改增强、扫 confidence、访问 candidate test 或执行第二个实验。

### 2. Git前置验收

开始时工作树干净，无 merge/rebase/cherry-pick，E 盘 Healthy/OK。`origin/main` 为 `a3d19db706e1fdf43a259eecc92f28bb530d985b`；上一轮实现 `504ca5fe5cee7ee554ed0a661dd0fc7ba0c8b3e8` 与反馈 `b1b91213e4a308e35329c5abdeb2e6c179946d71` 均是 origin/main 祖先。main fast-forward 后创建 `experiment/training-d02-d03-yolo26n-imgsz960-v01`。旧 stash 仅查看，未 apply/pop/drop/clear。

### 3. 环境验收

解释器为 `D:\JianzhenApps\Miniconda3\envs\jianzhen-training\python.exe`：Python 3.12.13、PyTorch 2.13.0+cu130、torchvision 0.28.0+cu130、Ultralytics 8.4.102、OpenCV 5.0.0、NumPy 2.4.4、pandas 3.0.3。CUDA=True，GPU=`NVIDIA GeForce RTX 5060 Laptop GPU`，总显存 8,546,484,224 字节。CUDA 正反向验证和 `pip check` 均通过，未安装或升级依赖。

### 4. 原117项测试

实验开始前完整回归为 117/117 PASS、FAIL 0、ERROR 0；任何旧测试均未跳过、删除或放宽。

### 5. dataset-lock复核

只验证现有 `E:\JianZhengData\training\detect-d02-d03-v0.1`，没有重建 v0.1 或创建 v0.2。`dataset-lock.json` SHA-256 仍为 `6d496281ade6486434c0eb85a473b2bd3e8e5574bcc51ca1d371895851ea6e97`；711 张图片与 711 个标签配对，train/val/test=614/64/33，D02/D03 bbox=9,514/1,790，图片树与标签树 SHA-256 仍为 `26e256f...` 与 `8efc3abd...`。

### 6. pretrained权重复核

`E:\JianZhengData\models\pretrained\ultralytics\yolo26n.pt` 大小仍为 5,544,453 字节，SHA-256 仍为 `9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef`。YOLO detect 加载与 640 合成输入 CUDA 推理通过；没有重新下载。960 正式训练从该权重开始，没有从 640 best.pt fine-tune。

### 7. GT目标尺寸分布

共分析 11,304 个 GT bbox，train/val/test bbox 为 8,335/1,981/988。归一化面积 min/Q25/Q50/Q75/max 为 `0.00004395 / 0.00228470 / 0.00456177 / 0.00941772 / 0.16707947`。按整体 Q25/Q50/Q75 划分，四个 quartile 各 2,826 个框，不使用人为绝对小目标阈值。

### 8. D02目标尺寸分布

D02 共 9,514 个 bbox，自身面积 Q25/Q50/Q75 为 `0.00255371 / 0.00479309 / 0.00966171`。按整体 quartile 分布：smallest 2,003、q2 2,583、q3 2,481、largest 2,447。

### 9. D03目标尺寸分布

D03 共 1,790 个 bbox，自身面积 Q25/Q50/Q75 为 `0.00133240 / 0.00260376 / 0.00806259`。按整体 quartile 分布：smallest 823、q2 243、q3 345、largest 379；D03 明显更集中于小目标区间。

### 10. 基线失败与目标尺寸关联

上一轮发布的失败计数来自 test，本轮禁止复用它选择 candidate。本轮重新对同一个 val 运行 640 baseline，并用 `image_relpath + label_index` 将每条主要失败可靠关联到 GT bbox。640 val 各 quartile 失败率从小到大为 79.298%、59.747%、51.570%、40.596%；D02 对应为 80.242%、60.000%、52.182%、40.467%。这证明失败率与目标尺寸存在明显关联，而不是只依据名称猜测。

### 11. 640基线val复现

640 best.pt 在 val、imgsz 640 上复现：Precision 0.331108、Recall 0.242798、mAP50 0.193225、mAP50-95 0.083132；D02 为 0.292472/0.192493/0.131522/0.037191，D03 为 0.369744/0.293103/0.254927/0.129074。全部指标在 1e-6 容差内逐值复现上一轮，因此允许继续训练。

### 12. 640模型在960纯推理结果

同一个 640 best.pt 仅把 val 推理尺寸改为 960 后：Precision 0.301011、Recall 0.234115、mAP50 0.178323、mAP50-95 0.068943；D02 为 0.237314/0.218231/0.117220/0.031462，D03 为 0.364708/0.250000/0.239426/0.106424。inference 为 8.025 ms/image。纯提高推理尺寸整体退化，不能替代 960 重新训练。

### 13. 实验配置差异审计

`experiment-config-diff.json` 通过。主动参数差异只有 `imgsz:640→960`；其他许可差异仅为 experiment_id、正式/smoke 名称以及 baseline/candidate/comparison 外部路径引用。dataset、model、seed、epochs、patience、optimizer、workers、cache、deterministic、AMP、增强默认值均未改变；非许可差异为 0。

### 14. 960 smoke test

3/3 epoch 完成，实际 batch 4，总耗时 72.387 秒，平均 24.129 秒/epoch，best epoch 3。AutoBatch、AMP、有限 loss、checkpoint、validation 和绘图均正常，无 NaN/Inf、无无法恢复 OOM。记录的 PyTorch peak allocation 为 9,487,895,040 字节，包含 AutoBatch 探测。

### 15. 正式960训练配置

YOLO26n、imgsz 960、epochs 100、patience 25、batch -1、device 0、workers 4、cache false、seed 42、deterministic true、optimizer auto、pretrained true、AMP true、save_period 10。没有设置 lr、momentum、weight decay、box/cls/dfl、multi_scale、mosaic 或 close_mosaic 覆盖值。

### 16. 正式训练过程

2026-08-11 11:45:06+08:00 开始，12:30:53+08:00 结束；完成 100/100 epoch，无 early stop、OOM 或 NaN/Inf。实际 batch 3，总耗时 2,747.331 秒（约 45 分 47 秒），平均 27.473 秒/epoch；固定目录没有生成 train2/train3。正式 epoch 日志中训练 GPU memory 约 1.25–1.81 GiB。

### 17. 960 best epoch

按 Ultralytics 一基 epoch 编号，best epoch 为 99，last epoch 为 100。best.pt 与 last.pt 均可加载；本轮 candidate 选用 best.pt，但不自动晋级 release。

### 18. 960总体val指标

best.pt val：Precision 0.358709、Recall 0.261359、mAP50 0.221814、mAP50-95 0.094648。last.pt val：Precision 0.332003、Recall 0.269789、mAP50 0.223085、mAP50-95 0.093839。

### 19. 960 D02指标

D02 best.pt val：Precision 0.289831、Recall 0.203753、AP50 0.138476、AP50-95 0.040010。

### 20. 960 D03指标

D03 best.pt val：Precision 0.427588、Recall 0.318966、AP50 0.305152、AP50-95 0.149285。

### 21. 640 vs 960总体比较

总体 Precision `+0.027601/+8.336%`，Recall `+0.018561/+7.645%`，mAP50 `+0.028589/+14.796%`，mAP50-95 `+0.011516/+13.852%`。四项总体指标均提高。

### 22. 640 vs 960 D02比较

D02 Precision `-0.002642/-0.903%`，Recall `+0.011260/+5.850%`，AP50 `+0.006954/+5.287%`，AP50-95 `+0.002819/+7.581%`。目标中的 D02 Recall 和 AP 有改善，但 Precision 略降。

### 23. 640 vs 960 D03比较

D03 Precision `+0.057844/+15.644%`，Recall `+0.025862/+8.824%`，AP50 `+0.050225/+19.702%`，AP50-95 `+0.020212/+15.659%`。D03 没有明显回退。

### 24. 小目标失败比较

以整体 smallest quartile 定义小目标：640 val 为 226，960 val 仍为 226，变化 0。总体最小四分位失败率均为 79.298%；D02 最小四分位失败率由 80.242% 升至 82.258%。因此提高训练分辨率没有解决最小四分位问题，改善主要来自更大目标。

### 25. 低IoU比较

low IoU 从 842 降至 817，减少 25，变化 -2.969%。存在小幅改善，但幅度明显小于总体 mAP50-95 的相对增益。

### 26. 背景错误比较

best.pt val 混淆矩阵的背景相关错误从 1,989 降至 1,968，减少 21；正确类别分配从 285 增至 287。D02/D03 跨类混淆从 1 增至 5。自动失败分析中的高置信假阳性从 89 降至 52，减少 37。

### 27. 训练时间比较

总训练时间从 1,180.176 秒增至 2,747.331 秒，增加 1,567.155 秒，相对 +132.790%。平均 epoch 从 11.802 秒增至 27.473 秒，同样 +132.790%。

### 28. 推理速度比较

同一 val 正式评估的 inference 从 6.471 ms/image 增至 8.191 ms/image，增加 1.720 ms/image，相对 +26.578%。另有 preprocess 1.408→2.515 ms/image、postprocess 0.346→1.742 ms/image；速度数据会受单次运行和系统调度影响。

### 29. 显存比较

同一 PyTorch `max_memory_allocated` 口径从 4,727,974,912 增至 10,620,080,640 字节，增加 5,892,105,728 字节，+124.622%。该口径包含 AutoBatch 探测；Windows WDDM 可用共享内存支持分配，因此候选数字可高于独立显存，不代表稳定 epoch 的常驻独立显存。物理 batch 从 8 降至 3。

### 30. qualitative对照

从 val 以 seed 42 确定性选择同一批 20 张；每张均保存 GT、640 baseline 和 960 candidate 三份可视化及统一 manifest。没有另抽更好看的 candidate 样本，没有修改原图或标签。

### 31. candidate模型制品

candidate 位于 `E:\JianZhengData\models\experiments\d02-d03-yolo26n-imgsz960-v0.1`，包含 best.pt、last.pt 路径/哈希引用、experiment config、val metrics、comparison、failure summary、experiment model card 和 best SHA 文件。best.pt SHA-256 为 `2dd857412b63df66d1273b326dc51afaed895da1d360c97e184762c882181a97`。正式 release 目录和 640 best.pt 未修改。

### 32. test封存确认

对象尺寸分析只读取 test GT 做数据描述；数据完整性预检只扫描 test 文件/标签。960 candidate 没有在 test 上执行 inference、validation、失败分析或 qualitative，没有 candidate test 指标、test 输出目录或 test payload。最终制品均登记 `candidate_test_accessed=false`。

### 33. 自动测试

新增 20 项：目标尺寸分析 6 项、实验比较 14 项。覆盖分位数复现与顺序不变、D02/D03 统计、640/960 投影、拒绝覆盖、配置单变量审计、dataset-lock/pretrained 哈希漂移、candidate/release 路径隔离、绝对/相对差值、per-class 关联、test 拒绝、qualitative 同样例及 640/960 配置兼容。

### 34. 原117项兼容性

最终 137/137 PASS、FAIL 0、ERROR 0；原 117 项全部继续通过，没有用删除或跳过旧测试换取成功。

### 35. Ruff和py_compile

`ruff check scripts tests` 通过；`ruff format --check scripts tests` 报告 28 个 Python 文件均已格式化；scripts/tests 下 28 个 Python 文件全部通过 py_compile。

### 36. raw不变性

`E:\JianZhengData\external\raw` 前后均为 7,952 个文件、13,339,506,276 字节；metadata tree SHA-256 和三个 defect-cardboard 原始 COCO SHA-256 全部相同，`raw_unchanged=true`。

### 37. 冻结数据不变性

按 dataset-lock 管理的不可变内容排除 Ultralytics 派生 `.cache` 后，前后均为 1,431 个文件、33,795,252 字节，metadata tree、关键文件 SHA-256、image tree 和 label tree 全部一致，`frozen_dataset_unchanged=true`。Smoke 的 fraction 会重建派生 `train.cache`，正式全量训练随后重建完整 cache；原始包含 cache 的前置快照被单独保留，不把 cache 冒充模型数据或纳入 dataset-lock。

### 38. 环境复验

结束后 `pip check` 通过；Python/PyTorch/torchvision/Ultralytics/OpenCV/NumPy/pandas 与开始一致，CUDA=True、GPU 名称一致，`memory_allocated=0`、`memory_reserved=0`。未更新依赖、驱动、CUDA、PATH 或全局策略。

### 39. Git状态

实现提交为 `fc355df458921918029bf135c0c062d3073aa7a5`，提交说明 `experiment(training): evaluate YOLO26n at 960 input size`，包含 9 个文件、2,583 行新增和 5 行删除。反馈仅追加本章节并采用独立提交；暂存使用显式路径，未使用 `git add .`。

### 40. 实验结论

960 重新训练使总体 val mAP50-95 提高 13.852%，D02 Recall 提高 5.850%，D02 AP50-95 提高 7.581%，D03 四项指标均改善；同时漏检减少 18.552%、高置信假阳性减少 41.573%、背景错误减少 21。但最小四分位失败数量完全不变，D02 最小四分位失败率略增；代价是 batch 降至 3、训练时间增加 132.790%、推理时间增加 26.578%。所以“总体/D02指标改善”成立，“最小目标问题得到解决”不成立。

### 41. 推荐：PROMOTE_FOR_TEST / KEEP_BASELINE / INCONCLUSIVE

推荐：`PROMOTE_FOR_TEST`。优先级最高的总体 mAP50-95、D02 AP50-95、D02 Recall 和总体 Recall 均改善，D03 未退化，因此可以由用户批准后对 960 candidate 执行一次正式 test。该推荐没有自动晋级模型，也没有在本轮访问 test；在用户批准前正式 release 仍是 640 baseline。

### 42. 已知限制

val 只有 64 张且 bbox 高度集中，失败匹配是自动 IoU 关联，不等于人工审查；最小四分位失败没有改善；PyTorch 显存峰值包含 AutoBatch/WDDM 共享内存效应；推理速度是单机单次测量。模型仍只识别 D02/D03，不能处理 D01/D04/D05、TAMPAR、连续节点或责任认定。

### 43. 风险

主要风险是 val 上的有限提升未必在封存 test 或真实快递站域复现、反复使用 val 形成间接过拟合、把总体提升误解为小目标问题已解决、把 WDDM 峰值误解为稳定独立显存，以及未经批准提前 test 或替换正式 release。

### 44. 回滚方法

Git 实现可 `git revert fc355df458921918029bf135c0c062d3073aa7a5`；反馈提交形成后单独 revert。外部派生内容可按明确目录删除 `smoke-d02-d03-yolo26n-imgsz960-v0.1`、`detect-d02-d03-yolo26n-imgsz960-v0.1`、640-vs-960 comparison 和 models/experiments candidate；不得删除或覆盖 raw、冻结图片/标签、预训练权重或正式 640 release。

### 45. 下一轮建议

下一轮先由用户决定是否接受 `PROMOTE_FOR_TEST`。若批准，只对当前 SHA-256 固定的 candidate best.pt 在封存 test 上执行一次正式评估并与 640 的既有 test 结果比较，不再训练、不调 confidence、不改数据。若不批准，则保持 640 release，并单独设计 smallest-quartile 数据/标注审查，不在同一轮叠加 YOLO26s 或增强变量。

## 比赛MVP v0.1：端到端异常节点定位系统

### 1. 前置验收

`origin/main` 起点为 `ab9addeab7e6d138c288b204637fcd30d1f4f9e5`。上一轮
`fc355df458921918029bf135c0c062d3073aa7a5` 与
`51e62e16c3b16a494fdc2ea2ab0ceaff374f6965` 均为 `origin/main` 祖先；main 通过
fast-forward 与远端一致后创建 `feat/training-competition-mvp-v01`。工作树起始干净，
无 merge/rebase/cherry-pick，E 盘 `Healthy / OK`，旧 stash 仅列出、未应用或删除。
冻结 lock、candidate 和正式 release 哈希门禁均通过。

### 2. 960 candidate test

只对 SHA-256 为 `2dd857412b63df66d1273b326dc51afaed895da1d360c97e184762c882181a97`
的 candidate 在冻结 33 张 test 上运行一次 `imgsz=960` 正式评估；没有训练、调阈值、
丢图或重跑。结果 P=`0.3586125579`、R=`0.2237734797`、mAP50=`0.1910518297`、
mAP50-95=`0.0755004514`。封存文件为
`E:\JianZhengData\runtime\mvp-v0.1\logs\candidate-test-v0.1.json`，脚本检测到既有
封存或输出目录会拒绝再次执行。

### 3. active detector选择

唯一判定指标为冻结 test mAP50-95。960 的 `0.0755004514` 高于 640 baseline 的
`0.0714805047`，因此活动模型确定为 `d02-d03-yolo26n-imgsz960-v0.1`，imgsz=960，
只支持 D02/D03。注册表写入
`E:\JianZhengData\models\active\detector-v0.1.json`；历史 release 未覆盖。

### 4. ONNX导出

活动 PT 成功导出 batch=1、dynamic=false、FP32、opset 19 的
`E:\JianZhengData\models\runtime\detector-v0.1\detector.onnx`，SHA-256 为
`765394eb1e098932549d7dd59c0599b2899d3d12f9494e1f7fe2c4d95b9caf9d`。ONNX
checker、ONNX Runtime CPU 零输入推理均通过；metadata 记录源哈希、尺寸、类别和
Ultralytics/ONNX/ORT 版本。

### 5. ONNX parity

同一冻结 64 张 val 上 PT 为 P/R/mAP50/mAP50-95=`0.358709/0.261359/0.221814/
0.094648`，ONNX 为 `0.384068/0.232858/0.210638/0.092439`；ONNX-PT 的 mAP50 与
mAP50-95 差分别为 `-0.0111765`、`-0.00220868`。mAP50 绝对差略超 0.01 工程阈值，
因此 ONNX 标为 `experimental`，不阻塞 MVP，运行时回退 PyTorch。报告位于 runtime
model 目录的 `onnx-parity-report-v0.1.json`。

### 6. Runtime detector

`ai/runtime/model_registry.py` 校验活动 PT 路径、SHA、类别边界和 ONNX fallback；
`ai/runtime/detector.py` 提供惰性加载统一接口。业务服务不直接散落 `YOLO(...)` 调用。
响应包含图像尺寸、model version/SHA、runtime、耗时和规范 detection 列表。

### 7. 图像配准

`ImageRegistrar` 实现 ORB、BFMatcher KNN ratio、RANSAC Homography 和
warpPerspective，输出关键点、匹配、内点、重叠率、矩阵、状态与 warnings。合成
identity、translation、rotation、perspective 均通过；无特征图片返回 `FAILED` 和
resize-only fallback，不伪造成功。

### 8. 变化检测

`ChangeDetector` 使用灰度、轻量平滑、absdiff、阈值、形态学开闭和轮廓区域。
合成不变图变化比接近 0；加入小/大凹陷样式、破口样式或胶带样式区域能够产生变化
区域。未知区域只写 `UNKNOWN_VISUAL_CHANGE`；只有与 D02/D03 detection 重叠时才可
关联已支持类别。参数集中配置并明确尚未用大规模真实物流数据校准。

### 9. TAMPAR demo

按 pair_id 排序确定性抽取 20 组 probable pair，生成
`tampar-demo-observation-report-v0.1.json`。只保留配准状态、变化分数、面积比、区域数
和 warnings 的观察记录，醒目标记 `TAMPAR_PAIR_NOT_HUMAN_CONFIRMED`、`DEMO_ONLY`；
不形成任何模型性能评价。

### 10. appearance fingerprint

`appearance_fingerprint_v0.1` 字段为 image SHA-256、width、height、ORB keypoint
count、规范化 descriptor digest 和 D02/D03 known damage summary。文档、API证据和
报告均说明 descriptor digest 只是工程级版本标识，不是稳定跨拍摄视觉身份 hash。

### 11. sequence locator

`ai/runtime/sequence_locator.py` 接受 N1...Nn 节点和相邻 pair 结果，MVP 强制至少
N1/N2/N3。节点状态覆盖 NORMAL、KNOWN_DAMAGE、UNKNOWN_CHANGE、
KNOWN_DAMAGE_AND_CHANGE、INSUFFICIENT_EVIDENCE，输出 first abnormal node/interval、
结论码、解释和警告。

### 12. 首次异常区间规则

规则覆盖 `FIRST_OBSERVED_ABNORMAL_AT_N1`、`N1_TO_N2`、`N2_TO_N3`、
`NO_ABNORMALITY_OBSERVED`、`UNKNOWN_VISUAL_CHANGE_INTERVAL` 和
`MANUAL_REVIEW_REQUIRED`。注册失败优先进入人工复核；绝不自动输出责任方、赔偿、
违规或人为拆封结论。

### 13. evidence level

E1=已知损伤与变化共同支持，E2=仅已知损伤支持，E3=仅未知变化支持，E0=无异常或
证据不足/配准失败。它只叫“技术证据等级”，不叫法律证据等级或责任认定等级。

### 14. HTML evidence report

`ai/runtime/evidence_report.py` 实际生成 UTF-8 JSON 与 HTML，包含 case、节点原图引用、
哈希、模型、detections、pair 变化、首次异常区间、E 级别、限制和固定免责声明。
Demo A 报告图片相对引用已逐一验证存在，可本地打开，也可通过 API 获取。

### 15. SQLite

数据库为 `E:\JianZhengData\runtime\mvp-v0.1\jianzheng.db`，使用标准库 sqlite3 与
外键/WAL；六表为 cases、case_nodes、detections、pair_changes、analysis_results、
reports。真实 E2E 后案例、3 节点、2 pair、analysis 和 report 行均存在；表结构没有
姓名、手机号、地址或真实运单号。

### 16. FastAPI

后端位于 `app/backend`，服务层串接 Detector、fingerprint、registration、change、
sequence、report 与数据库。异常统一返回 `{"error":{"code","message","details"}}`，
浏览器不接收 traceback；服务日志保留内部异常。

### 17. API endpoints

已实现 `GET /api/health`、`GET /api/model/info`、`POST /api/detect`、
`POST /api/change`、`POST /api/cases`、`POST /api/cases/{case_id}/nodes`、
`POST /api/cases/{case_id}/analyze`、`GET /api/cases/{case_id}`、
`GET /api/cases/{case_id}/report`、`GET /api/cases`。上传校验大小、后缀、MIME 和
OpenCV 解码，服务端生成文件名防止 traversal、盘符、UNC、绝对路径和覆盖。

### 18. Python新增依赖

只向 `jianzhen-training` 安装缺失的 FastAPI `0.141.1`、Uvicorn `0.52.1`、
python-multipart `0.0.32`；既有 httpx `0.28.1` 复用并记录。核心训练包未升级，
`python -m pip check` 通过。精确版本写入 `configs/runtime/requirements-mvp-v0.1.txt`。

### 19. Vue/Vite

建立本地 `frontend`，锁定 Vue `3.5.41`、Vite `7.3.6`、plugin-vue `6.0.8`，共安装
35 个本地 package，0 vulnerability。未全局安装 npm 包，`package-lock.json` 已生成；
`node_modules` 和 `dist` 由 `.gitignore` 排除。

### 20. 前端页面

单页三栏展示匿名案例、N1/N2/N3 上传、检测框、节点状态、检测数量/最高置信度、两组
变化指标、首次异常区间、技术证据等级和 HTML 报告链接。D01/D04/D05 明确待扩展，
底部固定免责声明；API基址只由 `frontend/src/api.js` 的 `VITE_API_BASE` 管理。

### 21. Demo cases

Demo A 是 `SYNTHETIC_DEMO`：N1正常、N2加入控制变化、N3保持变化，实际端到端结果
`N1_TO_N2 / E3`。Demo B 使用 TAMPAR probable pair 构造 N1/reference、N2/tampered、
N3/tampered，实际结果同为 `N1_TO_N2 / E3`，并标记 `PUBLIC_DATA_DEMO`、
`SIMULATED_NODE_SEQUENCE`、`NOT_REAL_LOGISTICS_TRACE`、未经人工确认和仅演示。

### 22. 一键启动

`scripts/demo/start-competition-mvp.ps1` 检查活动模型、Python依赖和前端 build；缺少
dist 时只在 frontend 本地执行 npm install/build，然后以前台 Uvicorn 启动并输出
`http://127.0.0.1:8000`。不修改 PowerShell 全局执行策略，现场只需一个终端和地址。

### 23. 端到端测试

实际隐藏启动 Uvicorn 后通过 HTTP 完成 health/model、创建 case、上传 N1/N2/N3、
analyze、获取 case/report 和前端首页，再由 SQLite 直接核验六表与行。Demo A 两组配准
均 SUCCESS，第一组 change ratio=`0.0232914`，第二组=`0`，首次区间正确。12 项 E2E
检查全部 true，报告为 `mvp-e2e-report-v0.1.json`，验证进程随后已停止清理。

### 24. 自动测试

开始时原有 137 项全通过。本轮新增 61 项有意义的 runtime/backend 测试：Detector与
registry 10、fingerprint/sequence 16、registration/change 14、SQLite/API 21，覆盖
题目列出的正常、异常、失败、安全和持久化分支。最终全量为 198 项并保持原 137 项
兼容。

### 25. 前端build

使用固定 `C:\Program Files\nodejs\npm.cmd` 执行 install/build，Vite 生产构建 exit 0，
生成 `frontend/dist/index.html`、CSS 和 JS；FastAPI 首页请求 200 并实际托管构建内容。

### 26. API真实运行

真实 Uvicorn `/api/health` 返回 status=ok、database/model ready=true、runtime=pytorch；
`/api/model/info` 返回 960 active model、D02/D03 和 D01/D04/D05 未支持状态。Demo A
HTTP create/upload/analyze/report/get-case 全部 200，不是仅用 TestClient 模拟。

### 27. ONNX/PT runtime状态

ONNX 可以加载和推理，但 parity mAP50 差略超本轮预设工程阈值，因此注册表为
`runtime_preferred=pytorch`、`onnx_status=experimental`。Detector 自动使用活动 PT；
若未来经确认更新注册表为 validated ONNX，可通过相同抽象切换。

### 28. 系统性能

Demo A 真实 API analyze 为 `2.938s`，客户端完整流程 `3.264s`；分析内部 total
`2919.97ms`，其中 detector `2649.87ms`（首次加载含在内）、registration `70.60ms`、
change detection `4.82ms`。ONNX val 单图 inference `34.45ms`（CPU），PT val 单图
`6.67ms`（GPU）；这些是本机单次工程观测，不宣称通用基准。

### 29. Git状态

分支为 `feat/training-competition-mvp-v01`。模型、ONNX、图片、数据库、cases、reports、
logs、node_modules、dist 未进入 Git；代码、配置、锁文件、测试和文档按 runtime、app、
test/docs 的逻辑提交显式 stage，不使用 `git add .`。推送后通过 compare 入口建 PR。

### 30. 已知限制

活动模型 test mAP50-95 仅 `0.075500`，真实场景可能漏检或假阳性；主动检测只有 D02/
D03；变化阈值尚未做真实物流序列校准；强视角、光照或背景变化可能造成 LOW_CONFIDENCE/
FAILED 或大量未知变化；TAMPAR probable 配对不是人工确认真值。

### 31. 未完成能力

未训练 D01/D04/D05，未做分割、YOLO26s、LLM、快递100真实 API、登录权限、云部署、
Docker、消息队列、PostgreSQL/Redis、移动端、实时摄像头和法律责任判断。Demo C 为可选
项，本轮未实现，避免为展示挑样本继续占用 test。

### 32. 安全边界

只使用合成、公开和脱敏匿名案例；数据库无个人字段；上传防 traversal 并生成随机名；
统一错误不泄漏 traceback。凭据/Token/Cookie/私钥、个人信息、运单号和大文件扫描不应
命中新增 Git 内容。没有访问 F 盘，没有修改 CUDA、驱动、系统 PATH 或执行策略。

### 33. 回滚

Git 代码按本轮逻辑提交逐个 `git revert <commit>`；外部 MVP 只允许在明确确认后删除
`E:\JianZhengData\runtime\mvp-v0.1`、`models/active/detector-v0.1.json` 和
`models/runtime/detector-v0.1`。不得删除或修改 `external/raw`、冻结 dataset、candidate
历史目录或正式 baseline release。运行中的服务按 Ctrl+C 停止，本轮 E2E 进程已清理。

### 34. 下一轮建议

最优先采集并人工确认少量真实同包裹连续 N1/N2/N3 序列，用它们校准配准/变化阈值和
灯光视角拍摄规范，同时做 D02/D03 错误案例人工复核；保持当前 test 封存，不再用 test
调阈值。第二优先级才是审核 D04 污损数据和设计 D05 胶带变化标注，不立即训练
YOLO26s 或堆叠新模型。

## 比赛MVP v0.2：多表面连续外观指纹与人工复核闭环

### 1. 前置验收

`origin/main` 起点为 `e177ec29f0eaaa3d66267dfaf34da35a97fe8b60`，工作树起始干净，
无 merge/rebase/cherry-pick，E 盘 `Healthy / OK`，本地 main 通过 fast-forward 与远端
一致后创建 `feat/training-competition-mvp-v02`。没有应用、删除或清理旧 stash。

### 2. v0.1资产复核

`cab708d...`、`f2c0f9e...`、`5217e91...`、`9dbd76b...` 四个提交均以 exit 0
通过 `git merge-base --is-ancestor ... origin/main`。活动模型仍为
`d02-d03-yolo26n-imgsz960-v0.1`，SHA-256 仍为
`2dd857412b63df66d1273b326dc51afaed895da1d360c97e184762c882181a97`，imgsz=960，
PyTorch active、ONNX experimental。

### 3. 本轮目标

本轮没有训练、下载或重新调 detector，没有访问 detector test；工作集中在多表面证据
结构、同表面跨节点比较、人工复核审计链、工程标定、Demo C/D、Vue 矩阵、预热和现场
稳定化。

### 4. 数据库迁移

v0.2 首次启动用 SQLite backup API 以只读源连接复制 v0.1 数据库，再在独立 v0.2 副本
上迁移。迁移前后 v0.1 与 v0.2 均保留原 2 个 cases、6 个节点；旧表重命名为
`case_nodes_v01_backup` 保留，新的 `case_nodes` 使用三列主键，未执行 DROP 或删除旧案例。

### 5. surface schema

正式枚举为 `front / left / right / top / back / bottom / unknown`；UI 默认前四项。旧
`PACKAGE_EXTERIOR` 或未传 surface 时规范化为 `front`。唯一键为
`(case_id,node_id,surface)`，同节点不同表面允许并存，同节点同表面重复返回 409。

### 6. multi-surface fingerprint

每个 node×surface 独立保存 `image_sha256`、width、height、ORB keypoint count、
descriptor digest 和 D02/D03 known damage summary，版本为 `surface_fingerprint_v0.2`。
不同表面不会交叉拼接或生成虚假统一哈希。

### 7. surface analyzer

新增 `ai/runtime/surface_analyzer.py`，统一单表面的 Detector、fingerprint、
registration、change、可视化与缺失 pair 生成；`services.py` 只负责案例编排和持久化。
analyzer 对跨表面输入直接抛错。

### 8. multi-surface sequence locator

`locate_multisurface_first_abnormality` 按 N1...Nn 和相邻同 surface pair 融合，输出每个
区间的表面状态、区间结论、证据等级、首次异常节点/区间、完整度与 warnings。N1 首次已知
损伤、N1→N2、N2→N3、全正常、仅失败/缺失均有测试。

### 9. trigger surface

分析结果新增 `trigger_surfaces`，每项包含 surface、reason 和 change score。真实 Demo D
只返回 `left / UNKNOWN_VISUAL_CHANGE / 1.0`，没有把 front/right/top 错误加入触发表面。

### 10. evidence聚合

E1=至少一个同表面 pair 由 known detector + reliable change 支持；E2=至少一个表面只由
known detector 支持；E3=无 known detector 但至少一个可靠未知变化；E0=无异常或证据
不足。missing/FAILED 不会单独触发异常。

### 11. review schema

新增 `review_events`：review id、case、node_from/to、surface、machine result、review
class/status、匿名 reviewer、note、created_at、supersedes id 和 payload SHA-256。没有真实
姓名字段。

### 12. review API

新增 `POST /api/cases/{case_id}/reviews` 与 `GET /api/cases/{case_id}/reviews`。
POST 会从已保存的机器 interval/surface 状态派生 `machine_result`，客户端不能覆盖该字段；
复核前未分析、非法区间或未分析表面均被拒绝。

### 13. append-only review

服务层只 INSERT；SQLite 同时建立 BEFORE UPDATE/DELETE trigger，任何修改或删除
`review_events` 都以 integrity error 中止。重复意见会作为新事件追加。

### 14. D01/D04/D05业务闭环

D01、D04、D05 都已通过独立 API 测试：机器先输出 `UNKNOWN_VISUAL_CHANGE`，人工再选择
相应类别并确认/拒绝/不确定。报告同时显示机器与人工字段，从未把人工 D01/D04/D05 改写
成“模型识别”。

### 15. calibration suite

`build_change_calibration_suite.py` 在
`E:\JianZhengData\runtime\calibration\change-v0.1` 生成 10 个固定场景：4 normal、4
change、2 failure；每个场景含 reference/current PNG 与 SHA-256，manifest 标记
`SYNTHETIC_ENGINEERING_CALIBRATION`。

### 16. threshold calibration

只扫描 pixel difference threshold 24/32/40、minimum region area 120/180/260、
significant change ratio 0.004/0.006/0.01，共 27 组；不加载 Detector、不改 confidence、
IoU 或权重。v0.1 参数在合成集为 normal false alarm 0、change missed 1；v0.2 仅将 ratio
从 0.006 调为 0.004，结果为 0 和 0，来源字段为 `synthetic_engineering`。

### 17. TAMPAR observation

确定性观察 20 个 probable pair。v0.1/v0.2 配准状态均为 FAILED 9、LOW_CONFIDENCE 4、
SUCCESS 7；变化分数中位数均 1.0、区域数中位数均 49.5、significant count 均 20。
只报告工程观察，不将 probable pair 当人工真值或真实物流性能。

### 18. Demo C

固定 seed `20260811`，只按 SHA 排序读取冻结 val 中 ground truth 非空样本，首个候选
`0372_jpg...jpg` 即有一项真实活动模型 D02 输出，confidence `0.272988`。图片复制到
v0.2 Demo C；元数据写明 `PUBLIC_DATA_DETECTION_DEMO`、`NOT_REAL_LOGISTICS_TRACE`、
source split=val、预测框未编辑。没有读取 test。

### 19. Demo D

生成 N1/N2/N3 × front/left/right/top 共 12 张程序合成图；只有 left 在 N2 注入受控区域，
N3 保持该变化。元数据标记 `MULTISURFACE_SYNTHETIC_DEMO`，预期区间 N1_TO_N2、表面
left。

### 20. frontend surface matrix

Vue 页面升级为 Node×Surface 矩阵，单元格显示上传预览、真实 detection box、机器状态、
已知损伤数、变化比和最新人工复核状态。缺失单元格可留空，后端显式记录 missing。

### 21. review panel

前端提供区间、表面、七类 review class、三类状态、四个匿名 reviewer、备注与 supersede
提交；复核列表同时展示机器结果、人工结果和 payload SHA 前缀。

### 22. model warmup

Detector 新增安全灰色 dummy inference；FastAPI lifespan 默认主动预热。真实启动返回
loaded=true、runtime=pytorch、GPU=true，首次 warmup `2567.46ms`；失败时仅降级为 lazy
fallback，不阻断服务启动。

### 23. self-check

`self-check-competition-mvp.ps1` 实际检查 Python 路径、依赖、GPU、active model 路径与
SHA、runtime 配置、SQLite 目录、frontend/dist、端口和 API health；实际运行全部 PASS，
仅在服务未启动时将 health 标为 WARN。

### 24. stop script

停止脚本从 v0.2 runtime 的固定 PID 文件读取 PID，再核验进程命令行同时包含 uvicorn 和
`app.backend.main:app` 后停止；真实停止 PID 38952 后，8000 listener=false、PID 文件
不存在。不会按端口模糊杀进程。

### 25. cold/warm performance

独立真实 Uvicorn 进程用环境变量仅为冷测关闭 startup warmup。Demo D cold analyze 为
`3885.56ms`；显式 warmup 后三次为 `1022.54 / 1061.04 / 1002.14ms`，median
`1022.54ms`、min `1002.14ms`、max `1061.04ms`，warm median 明显低于 cold。

### 26. API E2E

真实服务完成 health、model info、warmup、旧 Demo A/B、Demo C detect、Demo D 12 次上传、
analyze、review POST/GET、case/report 和 frontend 静态资源。第一次验收只因测试脚本在
HTML 外壳而不是编译 JS 中搜索 v0.2 文本而失败，失败报告保留；修正验证器后最终 10/10
断言通过，没有改产品结论或硬编码 Demo D 输出。

### 27. SQLite结果

真实 Demo D 行数：case_nodes 12、pair_changes 8、surface_analysis 12、analysis_results
1、reports 1、review_events 1、detections 0。schema version=2；实际表还包括保留的
`case_nodes_v01_backup` 和 `database_migrations`。

### 28. HTML v0.2 report

报告路径按案例隔离，初始为 `report-r000.html/json`，首次 review 后为
`report-r001.html/json`。内容含节点×表面矩阵、触发表面、机器分析、人工复核、每表面
fingerprint、pair registration/change、最终区间和限制。

### 29. old Demo回归

直接读取 v0.1 runtime 原 Demo A/B 图片并通过 v0.2 真实 API 重跑，两者均保持
`N1_TO_N2 / E3`，报告 HTTP 200。没有删除、移动或覆盖 v0.1 Demo。

### 30. 自动测试

本轮新增 57 项：多表面/词汇/fingerprint/locator 22，标定 7，数据库迁移/API/review 28。
覆盖任务要求的 40+ 场景，全部通过。

### 31. 原198项兼容性

开发前 198/198 PASS；完成后全量 255/255 PASS，原 198 项仍通过。v0.1 endpoints、
`PACKAGE_EXTERIOR` 单图上传、旧 report helper 和六表 introspection helper 保持兼容。

### 32. frontend build

`C:\Program Files\nodejs\npm.cmd run build` exit 0，Vite 7.3.6 构建 11 modules，生成
0.51 kB HTML、4.33 kB CSS、75.65 kB JS；真实 FastAPI 首页与编译 JS 均 HTTP 200。

### 33. npm audit

第一次请求 registry 时 TLS 建连中断；等待后按同一命令重试成功，`found 0 vulnerabilities`。
没有为非阻塞问题执行大版本升级。

### 34. Ruff

对 scripts、ai、app、tests 执行 `ruff check` 与 `ruff format --check`；最终均为 0 issue，
61 个 Python 文件格式检查通过。

### 35. py_compile

对仓库全部 61 个 Python 文件执行编译检查；所有文件通过，pyc 只写入外部 v0.2
`logs/pycompile-cache`，没有提交 pyc/cache 制品。

### 36. raw不变性

开始前 raw 为 7,952 个文件、13,339,506,276 字节，metadata SHA-256
`9f273bb050e911aecd9dd9c4ff05ebaa37526eb092680d84fd2530757d170786`；本轮只读使用，
结束比较保持一致。

### 37. frozen dataset不变性

排除派生 cache 后为 1,431 个文件、33,795,252 字节，content tree SHA-256
`9a0b6615187543cffb838bcebc0296d1ef7389a9fa2e6228d55b44d375da78ff`，lock SHA-256
仍为 `6d496281...`。Demo C 只读 val 并复制，未修改图片、标签或 lock。

### 38. model历史不变性

baseline release content tree SHA-256
`eb284208fc36092128edd82afdbcb20f46310c4494faeacdb1e0f824ec4f656a`；candidate history
为 `f5ec149fc5db647ea1d1e67b11979658b608a49a3cf9788a4a75a95c4cdccc10`，结束保持一致。
没有训练、下载、导出或改 active registry。

### 39. Git

实现提交依次为 `12b36ac feat(runtime)`、`b9a64a1 feat(app)`、`7d3b765 feat(demo)`、
`5cfbfdd test(mvp)`；本章、README 与架构文档作为独立 docs 提交。全部显式 stage，未使用
`git add .`；模型、图片、SQLite、runtime report、logs、node_modules 与 dist 未入 Git。

### 40. 当前能力

MVP 已支持多节点多表面上传、同表面比较、surface/node fingerprint、D02/D03 已知异常、
open-set 变化、trigger surface、区间融合、D01/D04/D05 人工确认、append-only 审计链、
SQLite、版本化 HTML 报告、Vue 双模式、Demo A/B/C/D、预热、自检、启动与安全停止。

### 41. 当前限制

D01/D04/D05 不是 AI 自动分类；真实同包裹连续序列仍不足；合成标定不代表真实物流；
活动 D02/D03 detector 的既有测试表现较低；强视角、背景、光照、遮挡和缺面会降低可靠度；
无登录、真实物流 API、移动端、云部署、视频、分割或法律责任自动判定。

### 42. 比赛风险

最大风险仍是现场拍摄与公开/合成域差异，而不是链路缺失。第二风险是首次 GPU 模型加载；
已用 startup warmup 缓解。第三风险是复核者把人工 D01/D04/D05 口径误说成 AI 分类；UI、
报告和文档已统一限制口径。

### 43. 回滚

Git 可按相反顺序 revert 本轮五个逻辑提交。外部 v0.2 可在明确确认后单独删除
`E:\JianZhengData\runtime\mvp-v0.2` 与合成 calibration 目录重新生成；不得删除或修改
v0.1 runtime、raw、冻结 dataset、baseline release、candidate history 或 active registry。

### 44. 下一轮建议

最高优先级是按 front/left/right/top 固定拍摄规范采集少量真实同包裹 N1/N2/N3 序列，
让 MEMBER-C 完成人工 pair/surface 真值，再只用新的 calibration split 检查变化阈值和
配准失败分布；继续封存 detector test，不叠加训练新模型或新类别。

## Competition Release Candidate v1.0

本轮在 `origin/main=809a1493f0c5fb067bef46290fddedf39fe12eba` 上创建
`feat/competition-release-candidate-v10`。第一次 `git pull --ff-only` 遇到临时 TLS
失败；成功 fetch 后，在干净工作树上将 main 安全快进并重建功能分支，没有保留错误基线或丢失修改。

| Goal | 目标指标 | 实际结果 | 证据 | 状态 |
|---|---|---|---|---|
| GOAL-01 | 原 255 项及全部新增测试通过 | 原 255 项保留；全量 331/331，新增 76 | `E:\JianZhengData\runtime\competition-rc-v1.0\evidence\test-summary-v1.0.json` | PASS |
| GOAL-02 | 可解释 0-100 风险规则；≥10 测试；配准失败不 HIGH | 九项分解，18 个确定性测试；总分等于分项和；失败配准 cap=59 | `ai/runtime/risk_engine.py`、全量测试、E2E risk | PASS |
| GOAL-03 | 工单 append-only；OPEN→IN_REVIEW→RESOLVED E2E | schema v3 两张工单表；三事件闭环和报告历史通过 | stability 3/3、workflow tests | PASS |
| GOAL-04 | SQLite 至少 8 项真实指标 | 11 类聚合指标与四组趋势；API/UI 均通过 | Dashboard API、`metrics-v1.0.md` | PASS |
| GOAL-05 | JSON/CSV/错误字段 E2E | TestClient 与真实 Uvicorn 均验证 JSON、CSV；PII 字段拒绝 | `competition-e2e-v1.0.json`、76 新测试 | PASS |
| GOAL-06 | MP4 解码、采样、活动 detector、≥1 关键帧 | 30 帧合成视频；采样 6 帧，异常 4 帧；HTTP keyframe 200 | `competition-demo-assets-v1.0.json`、E2E | PASS |
| GOAL-07 | Demo D 完整 Report v1.0 | JSON/HTML 含指定字段、固定声明、有效本地图像、风险/时间线/工单 | stability 的三个 report path、report tests | PASS |
| GOAL-08 | 离线构建；完整演示 3/3 | 三次独立 Uvicorn start/stop，3/3 PASS，0 crash/corruption/missing asset | `competition-release-stability-v1.0.json` | PASS |
| GOAL-09 | cold + warm×5；median≤1500ms 且退化≤50% | cold 4097.121ms；warm median 940.674ms；分段计时完整 | `performance-v1.0.json` | PASS |
| GOAL-10 | SYSTEM BEHAVIOR VALIDATION ≥16 | 17/17 PASS；明确不是 model accuracy | `competition-validation-summary-v1.0.json` | PASS |
| GOAL-11 | 能力分类与 D01-D05 真实边界 | 指定六类、视频/责任边界全部落实 | `docs/competition/capability-matrix-v1.0.md` | PASS |
| GOAL-12 | 7 份 Release 文档和完整 runbook | 指定 7 份全部新增；runbook 含检查、A-D、主线、fallback、停止 | `docs/competition/` | PASS |
| GOAL-13 | 组件/数据版本、用途、许可证、来源 | 依据 METADATA、package-lock 与 source registry；无猜测 | `open-source-and-data-sources-v1.0.md` | PASS |
| GOAL-14 | 可直接用于材料制作的真实证据包 | 截图清单、录屏步骤、实测指标、版本、Mermaid、风险均完成 | `material-evidence-pack-v1.0.md` | PASS |

### RC 实际能力与边界

- D02/D03：活动 YOLO26n 自动检测 + 人工复核。
- D01/D04/D05：开放集变化发现 + 人工复核，不是模型自动分类。
- 视频：`VIDEO_DAMAGE_KEYFRAME_SCREENING`，不是行为识别。
- 风险：`responsibility-risk-rules-v1.0` 确定性规则，不是责任概率或法律判责。
- 物流：匿名 JSON/CSV 通用适配器，不冒充真实企业 API。
- 真实连续序列：未发现通过权限与隐私审核的同包裹 N1/N2/N3 多表面数据，
  `REAL_WORLD_CALIBRATION = PENDING_EXTERNAL_DATA`；协议见
  `docs/dataset/real-sequence-validation-protocol-v1.0.md`，不阻断 RC。
- Stretch model：未执行；本轮禁止在 MUST GOAL 完成前训练，完成后也没有必要冒险替换 active detector。

### RC 外部证据

- release manifest：`E:\JianZhengData\runtime\competition-rc-v1.0\release\competition-release-manifest-v1.0.json`
- real Uvicorn E2E：`E:\JianZhengData\runtime\competition-rc-v1.0\competition-e2e-v1.0.json`
- stability：`E:\JianZhengData\runtime\competition-rc-v1.0\competition-release-stability-v1.0.json`
- performance：`E:\JianZhengData\runtime\competition-rc-v1.0\performance-v1.0.json`
- demo duration：`E:\JianZhengData\runtime\competition-rc-v1.0\demo-duration-v1.0.json`
- validation：`E:\JianZhengData\runtime\competition-validation-v1.0\competition-validation-summary-v1.0.json`
- start/self-check/stop：`E:\JianZhengData\runtime\competition-rc-v1.0\evidence\start-selfcheck-stop-v1.0.json`
- postflight invariants：`E:\JianZhengData\runtime\competition-rc-v1.0\evidence\postflight-invariants-v1.0.json`

本轮最大剩余风险是现实采集域差异，而不是业务闭环缺失。下一阶段只剩按最小协议采集并审核
真实受控序列、做 real-world calibration；不应把这一待办改写成当前已验证能力。

终验再次确认：正式 start 脚本已在 8030 端口完成 self-check、GPU warmup、health 和安全 stop，
服务停止后无 listener；raw、frozen、baseline/candidate model history、runtime v0.1/v0.2 与 active
registry 的文件数、字节数、metadata/content tree SHA 均与 preflight 精确一致。

## Competition RC v1.1 — Real-World Calibration & Model Hardening

本轮基线为 `origin/main=dd68382a50473cb21453b17ba6f61c7191221538`，分支为
`experiment/competition-rc-v11-hardening`。范围严格限制为真实域校准准备、D02/D03 模型审计、
一个 YOLO26s@640 候选和最终冻结，没有增加新产品模块。

| Goal | 风险 | 目标指标 | 实际结果 | 证据 | 状态 |
|---|---|---|---|---|---|
| GOAL-01 | 两项 | 331/331 且历史不可变 payload 不变 | 开始 331/331，最终 372/372；raw、冻结图片/标签内容、旧模型/runtime/RC v1.0 与 active registry 的 postflight 内容校验通过；派生 `labels/train.cache` 内容相同但 mtime 被 Ultralytics 刷新，已单列披露 | preflight/final tests；invariants | PASS |
| GOAL-02 | Domain gap | ≥3 个合规 N1/N2/N3 包裹，否则生成任务包 | 搜索 `E:\JianZhengData` 未发现；60 行 worklist 与成员 C 一页任务已生成 | real-sequence-discovery、capture-worklist | PENDING_EXTERNAL_DATA |
| GOAL-03 | Domain gap | 真实 registration/change 校准 | 无合规真实数据，指标全部 NOT_AVAILABLE；保留 change v0.2，不强行生成 v0.3 | calibration input、采集包 | PENDING_EXTERNAL_DATA |
| GOAL-04 | Detector accuracy | val failure、50 D02 GT、跨 split near duplicate | 1,299 failure；50 D02 GT；0 exact、3 perceptual near duplicates | detector/near-duplicate audits | PASS |
| GOAL-05 | Detector accuracy | 唯一 YOLO26s@640 smoke/100 epochs/val | 官方权重 SHA `646f8bc3...`；smoke、100 epochs、val 全完成，无 NaN/OOM | yolo26s evidence | PASS |
| GOAL-06 | Detector accuracy | 2/3 ≥10% 且延迟≤1.75× | 0/3 达标；延迟 PASS；KEEP_CURRENT_ACTIVE；candidate test 未执行 | detector-comparison | PASS |
| GOAL-07 | 两项 | 5/5 Demo；median≤1500；P90≤2000 | 5/5，0 crash/corruption/missing；median 914.278ms、P90 981.976ms | stability/performance/validation | PASS |
| GOAL-08 | 两项 | 独立冻结、manifest、工程门禁 | RC v1.1 独立目录、53-file manifest、全部工程门禁 PASS | release/evidence/docs | PASS |

### 模型结论

YOLO26s@640 val 为 P/R/mAP50/mAP50-95 `0.321941/0.299039/0.238414/0.102231`；
D02 AP50-95 `0.039505`、recall `0.218767`，D03 AP50-95 `0.164956`。相对 active n960，
overall AP +8.012%、D02 AP −1.261%、D02 recall +7.368%，没有一项达到 +10%。候选推理
10.177ms/image，虽满足 1.75× 延迟门槛，但提升项为 0/3，故未允许 candidate test，active
仍为 `d02-d03-yolo26n-imgsz960-v0.1`，SHA
`2dd857412b63df66d1273b326dc51afaed895da1d360c97e184762c882181a97`。

### 数据与真实性结论

真实包裹、真实图片、真实 surface 均为 0；五项 real validation 场景全部
`PENDING_EXTERNAL_DATA`，没有用公开或合成数据冒充。冻结数据的 711 张图跨 split DCT 审计
发现 3 组 train↔val perceptual near duplicate，0 exact duplicate；作为疑似 leakage 披露，
没有删除或修改 frozen dataset。D01/D04/D05 仍只允许表述为开放集变化加人工复核。

不可变性终验中，冻结目录文件数、总字节数和包含 cache 的全树内容 SHA 与 preflight 完全一致；
训练工具只重建了内容相同的派生 `labels/train.cache`，造成 mtime/metadata SHA 漂移。图片、标签、
dataset lock 及其他历史资产内容没有改变，该已解释工具副作用不计为 unexpected payload change。

### 最终冻结与后续

本轮完成后不建议继续大规模代码开发。除非出现严重真实场景失败、比赛规则变化或核心 bug，
工作应转向真实校准数据补充、比赛录屏、作品文本、PPT、答辩和彩排。

## Detector Optimization Goal Mode v2.0

### baseline

本轮基于 `origin/main=a33ee7d175e4d856bc46280516a3d7106f2cd83d`，开始回归 `372/372 PASS`。正式 active 为 YOLO26n@960：val P/R/mAP50/mAP50-95 `0.358709/0.261359/0.221814/0.094648`；D02 AP `0.040010`，D03 AP `0.149285`。

### data diagnosis

11,304 个 bbox 中 near-zero 0、短边小于 4px 3、截边 295、异常 aspect ratio 83、重复/越界 0；376 个仅按几何规则标记为 `label_concern`，没有直接改人工标签。D02 数量虽多但细微、低对比和背景相似性强，数量不平衡不是唯一原因。

### D02 audit

审计全部 1,865 个 val D02 GT：SUBTLE 476、SMALL 274、MEDIUM 686、LARGE 374、BACKGROUND_AMBIGUITY 2、LABEL_CONCERN 53。D02 的主要问题是细微程度、像素尺度与纸箱纹理混淆，而不是 bbox 数量不足。

### small-object audit

D02 最小四分位 failure 为 `204/248=82.258%`，中位尺寸约 `27×49.875px@960`；D03 最小四分位为 `22/37=59.459%`，中位尺寸约 `27×36px@960`。这支持 object-centric crop 假设，但后续实验说明仅靠重采样不能解决域和标签难度。

### background audit

active n960 在 val 的 40 个高置信未匹配预测中，确定性外观代理分类为：纸箱纹理 23、折痕 3、阴影 2、胶带 4、其他 8；人工复核仍是必要步骤。

### near duplicates

v0.1 的 711 张图中 exact cross-split duplicate 为 0，perceptual train→val pair 为 3，判为 suspected leakage；没有访问 test prediction。派生 train 排除对应 3 个源后，v0.2 的 cross-split audit 为 0 exact / 0 perceptual。

### derived dataset

建立 `E:\JianZhengData\training\detect-d02-d03-v0.2`：611 个去泄漏基础 train image、79 个 hard-example copy、344 个带 2.5× context 的几何标签 crop，共 1,034 个 train image；active-model hard-negative prediction 103。val/test 内容 SHA 与 v0.1 完全相同。另建立诊断性 v0.3：仅一源一张 D02 crop（103 张），无 hard-example copy，共 714 个 train image；val/test 同样不变。所有 crop 保留 source image、bbox、coordinates 和 SHA。

### EXP-01...EXP-06

1. EXP-01 YOLO26s@640：val AP `0.102231`、D02 `0.039505`、D03 `0.164956`、Recall `0.299039`；最高 overall，但 D02 AP 略降，`TRADEOFF`。
2. EXP-02 YOLO26n@960 + v0.2：AP `0.090926`、D02 `0.036678`；`REJECT`。
3. EXP-03 YOLO26n@960 + conservative v0.3：AP `0.095361`、D02 `0.038139`；`TRADEOFF/REJECT`。
4. EXP-04 YOLO26s@960：97 epochs early-stop；AP `0.084271`、D02 `0.037100`、D03 `0.131442`；`REJECT`。
5. EXP-05 YOLO26n@960、mosaic=0：AP `0.087638`、D02 `0.032116`；`REJECT`。
6. EXP-06 active-init、mosaic=0.5：26 epochs early-stop，best epoch 1；AP `0.085430`、D02 `0.035905`；`REJECT`。

每个新配置均先通过 3-epoch smoke；六个正式 run 预算全部使用，没有超预算或重复相同配置。

### Goal levels

Level-1、Level-2、Level-3 均未达到。最终状态为 `BEST_EFFORT_BUDGET_EXHAUSTED`，不再开启第三轮模型搜索。

### winner selection

预算耗尽后按最高 overall val AP 选择 EXP-01 作为 final val winner。相对 active val：overall AP `+8.012%`、Recall `+14.417%`、D03 AP `+10.498%`，但 D02 AP `-1.261%`。该 tradeoff 在 tracker 和答辩材料中明确披露。

### test lock

候选 SHA `83bf8f7fdc29837af19ef2c9be4f30dd9d5175deaa37142d7ed6c0242378c1ee`、val evidence、dataset lock SHA、选择原因和时间先写入 `E:\JianZhengData\runtime\detector-goal-v2.0\evidence\final-test-lock-v2.0.json`。锁以 exclusive create 建立；再次执行会拒绝。

### final test

test 只访问一次。overall P/R/mAP50/AP `0.335742/0.223156/0.185351/0.075155`；D02 P/R/AP50/AP `0.259568/0.166311/0.121838/0.034843`；D03 `0.411917/0.280000/0.248865/0.115467`。没有根据 test 继续训练或改阈值。

### promotion

overall AP 未达到 `0.095`，D02 AP 未达到 `0.050`；D03 non-catastrophic 与 1.75× latency 检查通过。最终为 `KEEP_CURRENT_ACTIVE`，不是 promotion，也不是 strong promotion。

### active model

正式 active 未替换：`d02-d03-yolo26n-imgsz960-v0.1`，SHA `2dd857412b63df66d1273b326dc51afaed895da1d360c97e184762c882181a97`。没有创建 `d02-d03-detector-v2.0` release 或 `detector-v2.0.json`，也不重复导出 ONNX。

### Competition RC regression

因为 active model 与 registry 均未改变，模型替换触发的 RC 全链路回归不适用；最终全量 unittest 继续覆盖 health、model info、warmup、Demo C/D、risk、report、video、work order 和 dashboard 的既有回归。

### known limitations

最大剩余问题是公开数据到真实驿站的域差异、细微/极小 D02、纹理背景假阳性与 3 个历史 near-duplicate。D01/D04/D05 继续采用 `OPEN_SET_DETECTION + HUMAN_REVIEW`。下一阶段应补充真实同包裹 N1/N2/N3 多表面序列、人工复核 D02/重复组并建立独立 calibration split，而不是无限调参。
