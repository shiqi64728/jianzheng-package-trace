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
- 未执行 `conda init`，未加入用户或机器 PATH，未注册默认 Python。

### PyTorch 与训练工具

- 2026-07-19 从 PyTorch 官方来源选择稳定版 Windows pip CUDA 13.0 wheel。
- 安装 `torch==2.13.0+cu130`、`torchvision==0.28.0+cu130`。
- 安装 numpy、scipy、pandas、scikit-learn、OpenCV、Pillow、matplotlib、albumentations、PyYAML、tqdm、rich、psutil、tensorboard、ultralytics、ONNX 工具、pytest、ruff、JupyterLab、ipykernel。
- 未安装系统级 CUDA Toolkit、系统级 cuDNN、nightly PyTorch 或第三方 GPU wheel。
- 已创建 `environment-r9000p.yml` 与 150 行依赖锁文件。

### IDE

- VS Code 1.108.1 安装 Python 2026.4.0、Pylance 2026.2.1、Python Environments 1.20.1、Jupyter 2025.9.1。
- VS Code 工作区配置精确指向正式环境；使用工作区终端的进程级 `-ExecutionPolicy Bypass` 解决 Conda hook 限制，未修改全局执行策略。
- 2026-07-19 与 2026-07-22 VS Code 新终端实测：正式 Python 路径、Python 3.12.13、torch 2.13.0+cu130、CUDA True。
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
- 可核算总清理量：3,582,429,898 B（3.336 GiB）。
- 未卸载任何软件，未移动任何软件目录，未删除任何用途不明项。

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

## 测试结果

| 测试 | 结果 | 证据摘要 |
|---|---|---|
| Conda/Python | PASS | Conda 26.5.3；Python 3.12.13；64-bit |
| 全局隔离 | PASS | Miniconda/环境不在用户或机器 PATH；无 PYTHONHOME/PYTHONPATH |
| pip 依赖 | PASS | `No broken requirements found` |
| 核心导入 | PASS | OpenCV、NumPy、pandas、sklearn、albumentations、ultralytics、ONNX/ORT 等 |
| CUDA | PASS | torch 2.13.0+cu130；CUDA 13.0；cuDNN 92000 |
| GPU | PASS | RTX 5060 Laptop；capability `(12, 0)`；`sm_120` |
| 正反向传播 | PASS | CUDA forward/backward 与梯度有限性检查通过 |
| ONNX | PASS | opset 18；CPUExecutionProvider；最大误差 2.9802322387695312e-08 |
| ONNX 临时清理 | PASS | 测试临时目录不存在 |
| VS Code 扩展 | PASS | Python、Pylance、Jupyter 已安装 |
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
- 可核算清理量：`3.336 GiB`

## 遇到的问题

1. GitHub 直连受本机 VPN/代理 DNS 行为影响；仓库级代理后成功。
2. Miniconda 官方 Windows 安装器不能可靠处理中文目标前缀；用户授权改用 `D:\JianzhenApps\Miniconda3`。
3. 一次 libmamba 环境创建结果缺少 pip；改用 classic solver 后成功。
4. 初始大批 pip 下载与 PyTorch 下载出现超时/挂起；只停止由本轮启动的精确进程，分批并用官方 wheel 重试成功。
5. ONNX 首次导出因 Windows PowerShell GBK 无法输出导出器的 `✅` 字符而失败；设置 `PYTHONUTF8=1` 后成功，模型本身无错误。
6. PyCharm Conda 向导报 `lateinit property envs_dirs has not been initialized`；改用精确环境的 System Interpreter，Terminal 实测成功。
7. VS Code 首次 Conda 自动激活被 PowerShell 执行策略阻止；使用工作区终端进程级 Bypass 解决，未修改系统或用户策略。
8. VS Code 尝试更新 Python Environments 1.36.0 时与 Code 1.108.1 不兼容；保留可工作的 1.20.1。
9. 临时文件首轮删除完成后，详细日志因 Windows PowerShell 5.1 将无 BOM UTF-8 脚本中的中文审计路径解码错误而写入失败；实际删除计数和字节数从命令输出写入独立汇总，修正为 ASCII 构造路径后记录剩余跳过项。
10. 2026-07-22 外置 `Elements` 盘曾未出现于 `Get-Disk`、`Get-Volume` 或 `Get-PSDrive`，导致正式仓库短暂不可访问；08:38 自然恢复为 `E:`。没有执行磁盘初始化、盘符强占或仓库替代复制。
11. Computer Use 的 Windows 自动化连接因本地 kernel assets 路径错误不可用；改用 Windows 自带窗口激活和剪贴板粘贴，只在两个 IDE 集成终端执行只读验证并将输出写入审计目录，验证成功。

## 尚未解决的问题

- 环境、GPU、IDE、旧 Python 安全判断与清理均无阻断项。
- 外置 `Elements` 盘曾短暂掉线；后续训练写入期间应保持连接稳定。
- 25 个历史 EXE/MSI 和 16 个用途不明目录因无法证明安全而保留；它们不是本项目环境阻断项。

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
