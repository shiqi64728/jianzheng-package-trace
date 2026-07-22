# R9000P 主训练机安全清理报告

## 1. 范围与安全门禁

- 首次审计：2026-07-19
- 接续清理与复验：2026-07-22
- 审计：`D:\下载的应用\_audit`
- 备份：`D:\下载的应用\_backups\r9000p-20260719-210748`
- 隔离：`D:\下载的应用\_quarantine\20260719-210748`

接续执行时，卷标 `Elements` 的外置 `E:` 盘曾短暂没有被 Windows 枚举，正式仓库不可访问。停止条件生效期间只清理可再生缓存、未占用临时文件和崩溃转储；08:38 外置盘自然恢复为 `E:` 后，重新验证仓库、GPU、PyCharm 和 VS Code，才删除本轮已校验的 Miniconda 安装器硬链接。软件、软件目录、空目录候选和旧 Python 均未删除或移动。

## 2. 磁盘空间

| 盘 | 2026-07-19 配置前 | 2026-07-22 清理后 | 总体净变化 |
|---|---:|---:|---:|
| C: | 188.02 GiB free | 190.59 GiB free | +2.57 GiB |
| D: | 223.67 GiB free | 218.38 GiB free | -5.29 GiB |

D: 的总体净减少包含新安装的 Miniconda、Python 3.12 环境、PyTorch CUDA wheels 和训练工具，不能把配置前后差值当作“清理量”。按清理目标前后文件大小直接核算，本次清理恢复 C: 877,925,201 B（837.25 MiB），D: 2,704,504,697 B（2,579.22 MiB），合计 3,582,429,898 B（3.336 GiB）。

## 3. 永久删除内容

| 时间 | 路径 | 内容 | 数量 | 释放空间 | 删除理由 | 可恢复方式 |
|---|---|---|---:|---:|---|---|
| 2026-07-22 | `D:\下载的应用\Caches\pip` | 正式环境 pip 下载缓存 | 880 files | 2,291,760,107 B | 可再生；环境和 GPU 已复验 | pip 按需重新下载 |
| 2026-07-22 | `C:\Users\35001\AppData\Local\pip\cache` | 旧 Python/共享 pip 缓存 | 626 files、480 dirs | 866,123,209 B | 用户明确要求；仅执行 cache purge | pip 按需重新下载 |
| 2026-07-22 | `D:\下载的应用\Caches\conda-pkgs` | 项目指定 Conda 包缓存 | package cache | 196,574,143 B | 可再生 | Conda 按需重新下载 |
| 2026-07-22 | `D:\JianzhenApps\Miniconda3\pkgs` | Miniconda 默认包缓存 | package cache | 85,422,679 B | `conda clean --all` 只清理可清理项 | Conda 按需重新下载 |
| 2026-07-22 | `C:\Users\35001\AppData\Local\Temp` | 未占用临时文件 | 229 deleted、15 skipped | 10,586,059 B | A 类临时文件；逐文件删除 | 不提供备份，可由应用重建 |
| 2026-07-22 | `C:\Users\35001\AppData\Local\CrashDumps` | 崩溃转储 | 1 | 1,215,933 B | A 类诊断残留 | 不提供备份 |
| 2026-07-22 | 三个 Miniconda 安装器硬链接（见下） | 官方安装器 | 3 links / 1 physical file | 130,747,768 B | 安装、环境、GPU 和两个 IDE 均复验成功；哈希/签名一致 | 从 Anaconda 官方地址重新下载并核验 |

`C:\Windows\Temp` 扫描时为 0 个文件。未取得权限、未修改所有权；单个失败项均跳过。

## 4. 官方卸载的软件

无。没有任何软件卸载命令被执行。

## 5. 移入隔离区的内容

无。没有任何目录或文件被移动到隔离区。

## 6. 已删除的安装器

下列三个路径是同一物理文件的硬链接，长度 130,747,768 B，签名有效，SHA-256 均为 `2D4A6CDCAA60F5A3C67BE17CDD8CC53C835EE00B7973D0E3D6AB5E0A8177524E`：

- `D:\下载的应用\Installers\Miniconda3-latest-Windows-x86_64.exe`
- `D:\下载的应用\Installers\_temporary-ascii-hardlink.exe`
- `D:\Miniconda3-latest-Windows-x86_64.exe`

08:38 外置仓库恢复后重新验证 Git 工作区、Conda、GPU、PyCharm Terminal 与 VS Code Terminal。三个链接于 08:43:50–08:43:52 逐个删除；由于它们指向同一物理文件，实际释放 130,747,768 B。删除记录位于 `D:\下载的应用\_audit\installer-cleanup.csv`。

## 7. 旧 Python 与重复工具

### 必须保留：`D:\Python`

- Python 3.9.5，64-bit。
- 39,013 个文件，约 1,170.41 MiB；39,013 个 SHA-256 全部计算成功。
- 多个现存个人项目的 `.idea\misc.xml` 使用 `Python 3.9` SDK。
- `D:\A_所有资料集\APython学习\Python代码\重连\.venv\pyvenv.cfg` 明确依赖 `D:\python\python.exe`。
- 开始菜单快捷方式和 PyCharm 全局 SDK 表仍引用。

未卸载、未隔离、未删除 SDK 节点或快捷方式。恢复不适用，因为没有更改。

### 其他工具

Git、Git LFS、Node.js、Visual Studio/Windows SDK、DevEco/Android 相关运行时、PyCharm/VS Code 内嵌运行时、Lenovo 私有 Python、NVIDIA 组件和系统运行时全部保留。未发现同时满足全部卸载条件的重复独立主安装。

## 8. 孤儿候选与无法判断项

`D:\下载的应用\_audit\orphan-candidates.csv` 共记录 76 个限定范围顶层项，并检查浅层 EXE/数字签名、注册卸载信息、快捷方式、运行进程、PATH、应用文件关联以及项目/文档标记。

- 7 项：任务规则明确排除或属于本轮已知审计/安装器基础目录。
- 6 项：存在注册安装证据，保留。
- 17 项：存在代码、Notebook、文档或项目标记，保留。
- 16 项：用途仍不明确，保留。
- 25 项：来源或回滚用途不明确的历史 EXE/MSI，保留。
- 1 项：`D:\Python` 有直接项目引用，保留。
- 4 项空目录候选：`.accelerate`、`goofish`、`typora`、`新建文件夹`；无法证明全部是“明确失效软件”的残留，按保守规则保留。

所有非空未知目录均未永久删除，也未在证据不足时擅自隔离。

## 9. 清理后复验

- Git 2.54.0.windows.1：PASS
- Git LFS 3.7.1：PASS
- Python 3.12.13 / pip 25.0：PASS
- `pip check`：PASS
- 核心包导入：PASS
- torch 2.13.0+cu130 / torchvision 0.28.0+cu130：PASS
- RTX 5060 Laptop、compute capability `(12, 0)`、`sm_120`：PASS
- GPU 正反向传播：PASS
- ONNX opset 18 + ONNX Runtime CPU：PASS，最大绝对误差 2.9802322387695312e-08
- ONNX 临时目录清理：PASS
- VS Code 可执行文件、签名和 Python/Pylance/Jupyter 扩展：PASS
- PyCharm 可执行文件和签名：PASS
- VS Code Terminal：PASS（正式解释器、Python 3.12.13、torch 2.13.0+cu130、CUDA True）
- PyCharm Terminal：PASS（正式解释器、Python 3.12.13、torch 2.13.0+cu130、CUDA True）
- 仓库、origin、分支、工作树和忽略规则：PASS

## 10. 未解决风险与下一动作

外置 `Elements` 盘曾短暂掉线，后续训练前应确认 `E:` 稳定并避免在写入期间拔盘。本轮没有强行分配盘符、初始化磁盘或复制正式仓库来绕过门禁。剩余动作仅为限定范围提交、推送分支和创建 Draft PR。
