"""Prepare the official YOLO26n weight and run smoke/formal D02/D03 training."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from ultralytics import YOLO, __version__ as ultralytics_version
from ultralytics.data.dataset import YOLODataset
from ultralytics.data.utils import check_det_dataset
from ultralytics.utils.downloads import attempt_download_asset

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.training.prepare_d02_d03_dataset import (  # noqa: E402
    DatasetPreparationError,
    sha256_file,
    validate_frozen_dataset,
)

TRAINER_VERSION = "0.1.0"
OFFICIAL_ASSET_REPOSITORY = "ultralytics/assets"
OFFICIAL_ASSET_RELEASE = "v8.4.0"
FORBIDDEN_TUNING_KEYS = {"lr0", "momentum", "weight_decay", "box", "cls", "dfl"}


class TrainingPipelineError(RuntimeError):
    """Raised when a training gate or run fails."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TrainingPipelineError(f"无法读取JSON：{path}：{exc}") from exc
    if not isinstance(data, dict):
        raise TrainingPipelineError(f"JSON根节点必须是对象：{path}")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def validate_experiment_config(config: dict[str, Any]) -> dict[str, Any]:
    """Validate the fixed first-baseline experiment contract."""
    required = {
        "experiment_id",
        "dataset_version",
        "dataset_yaml",
        "dataset_lock",
        "model",
        "model_metadata",
        "external_model_root",
        "task",
        "imgsz",
        "epochs",
        "patience",
        "batch",
        "device",
        "workers",
        "cache",
        "seed",
        "deterministic",
        "optimizer",
        "pretrained",
        "amp",
        "project",
        "name",
        "save",
        "save_period",
        "smoke",
    }
    missing = sorted(required - set(config))
    if missing:
        raise TrainingPipelineError(f"实验配置缺少字段：{', '.join(missing)}")
    forbidden = sorted(FORBIDDEN_TUNING_KEYS & set(config))
    if forbidden:
        raise TrainingPipelineError(
            f"首版配置不得手动覆盖官方recipe：{', '.join(forbidden)}"
        )
    expected = {
        "experiment_id": "d02-d03-yolo26n-baseline-v0.1",
        "dataset_version": "detect-d02-d03-v0.1",
        "task": "detect",
        "imgsz": 640,
        "epochs": 100,
        "patience": 25,
        "batch": -1,
        "device": 0,
        "workers": 4,
        "cache": False,
        "seed": 42,
        "deterministic": True,
        "optimizer": "auto",
        "pretrained": True,
        "amp": True,
        "save": True,
        "save_period": 10,
    }
    mismatches = [key for key, value in expected.items() if config.get(key) != value]
    if mismatches:
        raise TrainingPipelineError(f"实验配置偏离首版固定值：{', '.join(mismatches)}")
    smoke = config["smoke"]
    if not isinstance(smoke, dict) or smoke.get("epochs") != 3:
        raise TrainingPipelineError("Smoke test必须固定为3 epoch。")
    fraction = smoke.get("fraction")
    if not isinstance(fraction, (int, float)) or not 0 < float(fraction) <= 1:
        raise TrainingPipelineError("Smoke fraction必须位于(0, 1]。")
    model_path = Path(str(config["model"]))
    model_root = Path(str(config["external_model_root"]))
    if not _is_within(model_path, model_root):
        raise TrainingPipelineError("model path必须位于外部模型区。")
    if model_path.name != "yolo26n.pt":
        raise TrainingPipelineError("本轮只允许yolo26n.pt。")
    if Path(str(config["model_metadata"])).name != "yolo26n.metadata.json":
        raise TrainingPipelineError("权重metadata文件名不正确。")
    return config


def load_experiment_config(path: Path) -> dict[str, Any]:
    return validate_experiment_config(_load_json(path))


def _cuda_gate() -> None:
    if not torch.cuda.is_available():
        raise TrainingPipelineError("CUDA不可用。")
    if torch.cuda.get_device_name(0) != "NVIDIA GeForce RTX 5060 Laptop GPU":
        raise TrainingPipelineError(
            f"训练GPU不符合预期：{torch.cuda.get_device_name(0)}"
        )


def prepare_official_weight(config: dict[str, Any]) -> dict[str, Any]:
    """Download only through the installed Ultralytics official asset resolver."""
    _cuda_gate()
    model_path = Path(str(config["model"]))
    metadata_path = Path(str(config["model_metadata"]))
    if metadata_path.exists():
        raise TrainingPipelineError(f"权重登记已存在，拒绝覆盖：{metadata_path}")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    existed_before = model_path.exists()
    if not existed_before:
        result = Path(
            attempt_download_asset(
                model_path,
                repo=OFFICIAL_ASSET_REPOSITORY,
                release=OFFICIAL_ASSET_RELEASE,
            )
        )
        if result.resolve() != model_path.resolve() or not model_path.is_file():
            raise TrainingPipelineError(f"官方权重解析没有写入预期路径：{result}")
    if not model_path.is_file():
        raise TrainingPipelineError(f"权重文件不存在：{model_path}")
    try:
        model = YOLO(model_path)
        if model.task != "detect":
            raise TrainingPipelineError(f"权重task不是detect：{model.task}")
        synthetic = np.zeros((640, 640, 3), dtype=np.uint8)
        predictions = model.predict(synthetic, imgsz=640, device=0, verbose=False)
        if len(predictions) != 1:
            raise TrainingPipelineError("合成图片CUDA推理没有产生单个结果。")
    except (OSError, RuntimeError, ValueError) as exc:
        raise TrainingPipelineError(
            f"现有或下载权重无法验证，停止且不覆盖：{exc}"
        ) from exc
    stat = model_path.stat()
    digest = sha256_file(model_path)
    source_url = (
        f"https://github.com/{OFFICIAL_ASSET_REPOSITORY}/releases/download/"
        f"{OFFICIAL_ASSET_RELEASE}/{model_path.name}"
    )
    metadata = {
        "model_name": model_path.name,
        "model_family": "Ultralytics YOLO26",
        "task": "detect",
        "source_provider": "Ultralytics",
        "source_type": "installed_ultralytics_official_asset_resolver",
        "source_reference": source_url,
        "downloaded_at": datetime.now().astimezone().isoformat(),
        "download_performed": not existed_before,
        "file_size_bytes": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "sha256": digest,
        "ultralytics_version": ultralytics_version,
        "torch_version": torch.__version__,
        "cuda_runtime": torch.version.cuda,
        "verified_load": True,
        "verified_task": model.task,
        "verified_cuda_inference": True,
        "notes": "仅通过当前已安装Ultralytics包的官方ultralytics/assets解析机制获取；未使用认证信息或第三方镜像。",
    }
    _write_json(metadata_path, metadata)
    return metadata


def _verify_weight(config: dict[str, Any]) -> dict[str, Any]:
    model_path = Path(str(config["model"]))
    metadata_path = Path(str(config["model_metadata"]))
    if not model_path.is_file() or not metadata_path.is_file():
        raise TrainingPipelineError("权重或权重metadata缺失。")
    metadata = _load_json(metadata_path)
    actual = sha256_file(model_path)
    if metadata.get("sha256") != actual:
        raise TrainingPipelineError("yolo26n.pt SHA-256与来源登记不一致。")
    if not metadata.get("verified_load") or metadata.get("verified_task") != "detect":
        raise TrainingPipelineError("权重来源登记没有通过detect加载验证。")
    return metadata


def ultralytics_dataset_preflight(config: dict[str, Any]) -> dict[str, Any]:
    """Make Ultralytics parse and index every declared dataset split without training."""
    dataset_yaml = Path(str(config["dataset_yaml"]))
    custom = validate_frozen_dataset(dataset_yaml.parent)
    data = check_det_dataset(str(dataset_yaml))
    split_counts: dict[str, int] = {}
    for split in ("train", "val", "test"):
        image_path = data.get(split)
        if not image_path:
            continue
        dataset = YOLODataset(
            img_path=image_path,
            imgsz=int(config["imgsz"]),
            cache=False,
            augment=False,
            data=data,
            task="detect",
            batch_size=1,
            prefix=f"preflight-{split}: ",
        )
        if len(dataset) == 0:
            raise TrainingPipelineError(f"Ultralytics读取到空split：{split}")
        sample = dataset[0]
        if "img" not in sample or "cls" not in sample or "bboxes" not in sample:
            raise TrainingPipelineError(f"Ultralytics样本结构异常：{split}")
        split_counts[split] = len(dataset)
    report = {
        "valid": True,
        "checked_at": datetime.now().astimezone().isoformat(),
        "custom_validation": custom,
        "ultralytics_version": ultralytics_version,
        "ultralytics_split_counts": split_counts,
        "dataset_yaml": str(dataset_yaml),
    }
    _write_json(dataset_yaml.parent / "ultralytics-preflight.json", report)
    return report


def _parse_results_csv(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise TrainingPipelineError(f"训练结果CSV缺失：{path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise TrainingPipelineError("results.csv为空。")
    numeric_values: list[float] = []
    for row in rows:
        for key, value in row.items():
            if key and key.strip() == "epoch":
                continue
            if value is None or not value.strip():
                continue
            try:
                numeric_values.append(float(value))
            except ValueError:
                continue
    if not numeric_values or any(not math.isfinite(value) for value in numeric_values):
        raise TrainingPipelineError("results.csv包含NaN/Inf或没有有限数值。")
    map_key = next((key for key in rows[0] if "mAP50-95" in key), None)
    best_epoch = None
    if map_key:
        best_index = max(
            range(len(rows)), key=lambda i: float(rows[i][map_key] or "-inf")
        )
        epoch_value = int(float(rows[best_index].get("epoch", best_index)))
        best_epoch = epoch_value if epoch_value >= 1 else epoch_value + 1
    return {"rows": len(rows), "best_epoch": best_epoch}


def _actual_batch(trainer: Any) -> int | None:
    train_loader = getattr(trainer, "train_loader", None)
    value = getattr(train_loader, "batch_size", None)
    if isinstance(value, int) and value > 0:
        return value
    value = getattr(trainer, "batch_size", None)
    return value if isinstance(value, int) and value > 0 else None


def _run_path(config: dict[str, Any], mode: str) -> Path:
    if mode == "smoke":
        smoke = config["smoke"]
        return Path(str(smoke["project"])) / str(smoke["name"])
    return Path(str(config["project"])) / str(config["name"])


def run_training(config: dict[str, Any], mode: str) -> dict[str, Any]:
    """Run smoke or formal training without silent hyperparameter fallback."""
    if mode not in {"smoke", "train"}:
        raise TrainingPipelineError(f"未知训练模式：{mode}")
    _cuda_gate()
    _verify_weight(config)
    dataset_lock = _load_json(Path(str(config["dataset_lock"])))
    if dataset_lock.get("dataset_version") != config["dataset_version"]:
        raise TrainingPipelineError("dataset-lock版本与实验配置不一致。")
    preflight = ultralytics_dataset_preflight(config)
    run_dir = _run_path(config, mode)
    if run_dir.exists():
        raise TrainingPipelineError(f"运行目录已存在，拒绝生成train2/train3：{run_dir}")
    if mode == "train":
        smoke_dir = _run_path(config, "smoke")
        smoke_metadata = smoke_dir / "run-metadata.json"
        if (
            not smoke_metadata.is_file()
            or _load_json(smoke_metadata).get("status") != "success"
        ):
            raise TrainingPipelineError("Smoke test没有成功记录，禁止正式训练。")

    smoke = config["smoke"]
    requested_epochs = int(smoke["epochs"] if mode == "smoke" else config["epochs"])
    project = str(smoke["project"] if mode == "smoke" else config["project"])
    name = str(smoke["name"] if mode == "smoke" else config["name"])
    fraction = float(smoke["fraction"] if mode == "smoke" else 1.0)
    arguments = {
        "data": str(config["dataset_yaml"]),
        "imgsz": int(config["imgsz"]),
        "epochs": requested_epochs,
        "patience": int(config["patience"]),
        "batch": int(config["batch"]),
        "device": int(config["device"]),
        "workers": int(config["workers"]),
        "cache": bool(config["cache"]),
        "seed": int(config["seed"]),
        "deterministic": bool(config["deterministic"]),
        "optimizer": str(config["optimizer"]),
        "pretrained": bool(config["pretrained"]),
        "amp": bool(config["amp"]),
        "project": project,
        "name": name,
        "save": bool(config["save"]),
        "save_period": -1 if mode == "smoke" else int(config["save_period"]),
        "fraction": fraction,
        "exist_ok": False,
        "val": True,
        "plots": True,
        "verbose": True,
    }
    started = datetime.now().astimezone()
    started_perf = time.perf_counter()
    torch.cuda.reset_peak_memory_stats(0)
    try:
        model = YOLO(str(config["model"]))
        if model.task != "detect":
            raise TrainingPipelineError(f"加载模型task不是detect：{model.task}")
        model.train(**arguments)
        trainer = model.trainer
    except RuntimeError as exc:
        failure = {
            "status": "failed",
            "mode": mode,
            "failed_at": datetime.now().astimezone().isoformat(),
            "cuda_oom": "out of memory" in str(exc).lower(),
            "error": str(exc),
            "requested_arguments": arguments,
        }
        _write_json(run_dir.with_name(f"{run_dir.name}-failure.json"), failure)
        if failure["cuda_oom"]:
            raise TrainingPipelineError(
                "训练发生无法恢复的CUDA OOM，未静默调整参数。"
            ) from exc
        raise TrainingPipelineError(f"训练运行失败：{exc}") from exc
    elapsed = time.perf_counter() - started_perf
    actual_save_dir = Path(str(trainer.save_dir)).resolve()
    if actual_save_dir != run_dir.resolve():
        raise TrainingPipelineError(
            f"Ultralytics输出目录偏离固定路径：actual={actual_save_dir} expected={run_dir}"
        )
    best = run_dir / "weights" / "best.pt"
    last = run_dir / "weights" / "last.pt"
    if not best.is_file() or not last.is_file():
        raise TrainingPipelineError("训练完成但best.pt或last.pt缺失。")
    csv_summary = _parse_results_csv(run_dir / "results.csv")
    actual_epochs = csv_summary["rows"]
    metadata = {
        "trainer_version": TRAINER_VERSION,
        "status": "success",
        "mode": mode,
        "started_at": started.isoformat(),
        "ended_at": datetime.now().astimezone().isoformat(),
        "duration_seconds": elapsed,
        "requested_epochs": requested_epochs,
        "actual_epochs": actual_epochs,
        "early_stopped": actual_epochs < requested_epochs,
        "best_epoch": csv_summary["best_epoch"],
        "requested_batch": config["batch"],
        "actual_batch": _actual_batch(trainer),
        "peak_gpu_memory_bytes": torch.cuda.max_memory_allocated(0),
        "average_epoch_seconds": elapsed / actual_epochs,
        "dataset_lock_sha256": sha256_file(Path(str(config["dataset_lock"]))),
        "pretrained_weight_sha256": sha256_file(Path(str(config["model"]))),
        "best_pt_sha256": sha256_file(best),
        "last_pt_sha256": sha256_file(last),
        "arguments": arguments,
        "dataset_preflight": preflight,
    }
    _write_json(run_dir / "run-metadata.json", metadata)
    return metadata


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="D02/D03 YOLO26n首个基线训练")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("prepare-weight", "preflight", "smoke", "train"),
        required=True,
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        config = load_experiment_config(args.config)
        if args.mode == "prepare-weight":
            result = prepare_official_weight(config)
        elif args.mode == "preflight":
            result = ultralytics_dataset_preflight(config)
        else:
            result = run_training(config, args.mode)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (TrainingPipelineError, DatasetPreparationError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"[internal-error] {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    if os.name == "nt":
        import multiprocessing

        multiprocessing.freeze_support()
    raise SystemExit(main())
