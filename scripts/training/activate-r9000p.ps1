$CondaRoot = "D:\JianzhenApps\Miniconda3"
$EnvironmentRoot = "$CondaRoot\envs\jianzhen-training"

$env:PATH = "$EnvironmentRoot;$EnvironmentRoot\Scripts;$CondaRoot\Scripts;$env:PATH"
$env:PIP_CACHE_DIR = "D:\下载的应用\Caches\pip"
$env:CONDA_PKGS_DIRS = "D:\下载的应用\Caches\conda-pkgs"
$env:TORCH_HOME = "D:\下载的应用\Caches\torch"
$env:HF_HOME = "D:\下载的应用\Caches\huggingface"
$env:ULTRALYTICS_CONFIG_DIR = "D:\下载的应用\Caches\ultralytics"

python -c "import sys; print(sys.executable); print(sys.version)"
