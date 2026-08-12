"""Run one hypothesis-led Detector Optimization Goal v2.0 experiment."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import torch
import ultralytics
from ultralytics import YOLO

FIXED = {
    "epochs": 100,
    "patience": 25,
    "seed": 42,
    "device": 0,
    "optimizer": "auto",
    "amp": True,
    "cache": False,
}
CLASS_NAMES = ("D02_surface_dent", "D03_carton_tear")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    for key, value in FIXED.items():
        if config.get(key) != value:
            raise ValueError(f"fixed parameter drift: {key}={config.get(key)!r}")
    if config.get("test_access_allowed", False):
        raise ValueError("experiment configs may not allow test access")
    if config["experiment_id"] not in {f"EXP-{index:02d}" for index in range(1, 7)}:
        raise ValueError("experiment_id must be EXP-01..EXP-06")
    if not config.get("hypothesis") or not config.get("main_change"):
        raise ValueError("hypothesis and main_change are required")
    if Path(config["dataset_yaml"]).name != "dataset.yaml":
        raise ValueError("dataset_yaml must name dataset.yaml")
    if Path(config["model"]).name not in {"yolo26n.pt", "yolo26s.pt", "best.pt"}:
        raise ValueError(
            "only authorized n/s or an explicitly selected best.pt is allowed"
        )
    return config


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _assert_finite(rows: list[dict[str, str]]) -> None:
    for row in rows:
        for key, value in row.items():
            if not value or key == "epoch":
                continue
            try:
                number = float(value)
            except ValueError:
                continue
            if not math.isfinite(number):
                raise RuntimeError(f"non-finite training metric: {key}={value}")


def _best_epoch(rows: list[dict[str, str]]) -> tuple[int, float]:
    key = "metrics/mAP50-95(B)"
    best_index, best_value = max(
        enumerate(rows), key=lambda item: float(item[1].get(key) or "-inf")
    )
    return best_index + 1, float(best_value.get(key) or "nan")


def _experiment_root(config: dict[str, Any]) -> Path:
    return Path(config["project_root"]) / config["experiment_id"]


def _training_kwargs(config: dict[str, Any], *, smoke: bool) -> dict[str, Any]:
    kwargs = {
        "data": config["dataset_yaml"],
        "imgsz": config["imgsz"],
        "epochs": 3 if smoke else config["epochs"],
        "patience": config["patience"],
        "batch": config["batch"],
        "device": config["device"],
        "workers": config["workers"],
        "cache": config["cache"],
        "seed": config["seed"],
        "deterministic": True,
        "optimizer": config["optimizer"],
        "pretrained": True,
        "amp": config["amp"],
        "project": str(_experiment_root(config)),
        "name": "smoke" if smoke else "train",
        "save": True,
        "save_period": 10,
        "fraction": 0.25 if smoke else 1.0,
        "exist_ok": False,
        "verbose": True,
    }
    kwargs.update(config.get("train_overrides", {}))
    return kwargs


def run_training(config: dict[str, Any], *, smoke: bool) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable")
    root = _experiment_root(config)
    target = root / ("smoke" if smoke else "train")
    if target.exists():
        raise FileExistsError(f"refusing overwrite: {target}")
    root.mkdir(parents=True, exist_ok=True)
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    result = YOLO(config["model"]).train(**_training_kwargs(config, smoke=smoke))
    duration = time.perf_counter() - started
    actual = Path(result.save_dir)
    rows = _rows(actual / "results.csv")
    _assert_finite(rows)
    expected_epochs = 3 if smoke else config["epochs"]
    best_epoch, training_map = _best_epoch(rows)
    best = actual / "weights/best.pt"
    last = actual / "weights/last.pt"
    payload = {
        "report_version": "detector-goal-training-v2.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "experiment_id": config["experiment_id"],
        "hypothesis": config["hypothesis"],
        "main_change": config["main_change"],
        "expected_effect": config["expected_effect"],
        "mode": "smoke" if smoke else "formal_train",
        "formal_run_budget_consumed": not smoke,
        "dataset_split_usage": ["train", "val"],
        "test_predictions_accessed": False,
        "cuda": True,
        "gpu": torch.cuda.get_device_name(0),
        "amp": config["amp"],
        "epochs_requested": expected_epochs,
        "epochs_completed": len(rows),
        "best_epoch": best_epoch,
        "best_training_map50_95": training_map,
        "validation_completed": bool(rows),
        "nan_detected": False,
        "oom": False,
        "duration_seconds": duration,
        "peak_gpu_memory_bytes": torch.cuda.max_memory_allocated(),
        "resolved_batch": config["batch"],
        "run_dir": str(actual),
        "best_pt": str(best),
        "best_pt_sha256": sha256(best),
        "last_pt": str(last),
        "last_pt_sha256": sha256(last),
        "passed": len(rows) > 0,
    }
    evidence = Path(config["evidence_dir"]) / (
        f"{config['experiment_id'].lower()}-smoke-v2.0.json"
        if smoke
        else f"{config['experiment_id'].lower()}-training-v2.0.json"
    )
    evidence.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"evidence": str(evidence), **payload}, ensure_ascii=False))
    return payload


def metric_values(metrics: Any) -> dict[str, Any]:
    names = [metrics.names[index] for index in sorted(metrics.names)]
    per_class = {}
    for index, name in enumerate(names):
        per_class[name] = {
            "precision": float(metrics.box.p[index]),
            "recall": float(metrics.box.r[index]),
            "mAP50": float(metrics.box.ap50[index]),
            "mAP50-95": float(metrics.box.ap[index]),
        }
    if set(per_class) != set(CLASS_NAMES):
        raise RuntimeError(f"unexpected class mapping: {sorted(per_class)}")
    return {
        "overall": {
            "precision": float(metrics.box.mp),
            "recall": float(metrics.box.mr),
            "mAP50": float(metrics.box.map50),
            "mAP50-95": float(metrics.box.map),
        },
        "per_class": per_class,
    }


def run_val(config: dict[str, Any]) -> dict[str, Any]:
    root = _experiment_root(config)
    best = root / "train/weights/best.pt"
    if not best.is_file():
        raise FileNotFoundError(best)
    val_dir = root / "val"
    if val_dir.exists():
        raise FileExistsError(f"refusing overwrite: {val_dir}")
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    metrics = YOLO(str(best)).val(
        data=config["dataset_yaml"],
        split="val",
        imgsz=config["imgsz"],
        batch=config["evaluation_batch"],
        device=config["device"],
        workers=config["workers"],
        project=str(root),
        name="val",
        exist_ok=False,
        plots=True,
        verbose=True,
    )
    duration = time.perf_counter() - started
    training = json.loads(
        (
            Path(config["evidence_dir"])
            / f"{config['experiment_id'].lower()}-training-v2.0.json"
        ).read_text(encoding="utf-8")
    )
    payload = {
        "report_version": "detector-goal-val-v2.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "experiment_id": config["experiment_id"],
        "hypothesis": config["hypothesis"],
        "main_change": config["main_change"],
        "expected_effect": config["expected_effect"],
        "dataset_version": config["dataset_version"],
        "dataset_yaml": config["dataset_yaml"],
        "dataset_lock": config["dataset_lock"],
        "model": Path(config["model"]).name,
        "imgsz": config["imgsz"],
        "epochs": config["epochs"],
        "best_epoch": training["best_epoch"],
        "batch": training["resolved_batch"],
        "training_time_seconds": training["duration_seconds"],
        "split": "val",
        "test_predictions_accessed": False,
        "checkpoint": str(best),
        "checkpoint_sha256": sha256(best),
        "model_bytes": best.stat().st_size,
        "duration_seconds": duration,
        "speed_ms_per_image": {
            key: float(value) for key, value in metrics.speed.items()
        },
        "peak_validation_gpu_memory_bytes": torch.cuda.max_memory_allocated(),
        "peak_training_gpu_memory_bytes": training["peak_gpu_memory_bytes"],
        **metric_values(metrics),
        "ultralytics_version": ultralytics.__version__,
        "output_dir": str(metrics.save_dir),
    }
    payload["level_1"] = (
        payload["overall"]["mAP50-95"] >= 0.115
        and payload["per_class"]["D02_surface_dent"]["mAP50-95"] >= 0.050
        and payload["overall"]["recall"] >= 0.300
        and payload["per_class"]["D03_carton_tear"]["mAP50-95"] >= 0.134357
    )
    payload["level_2"] = (
        payload["overall"]["mAP50-95"] >= 0.135
        and payload["per_class"]["D02_surface_dent"]["mAP50-95"] >= 0.060
        and payload["overall"]["recall"] >= 0.320
        and payload["per_class"]["D03_carton_tear"]["mAP50-95"] >= 0.140
    )
    payload["level_3"] = (
        payload["overall"]["mAP50-95"] >= 0.150
        and payload["per_class"]["D02_surface_dent"]["mAP50-95"] >= 0.070
        and payload["overall"]["recall"] >= 0.350
        and payload["per_class"]["D03_carton_tear"]["mAP50-95"] >= 0.150
    )
    evidence = (
        Path(config["evidence_dir"])
        / f"{config['experiment_id'].lower()}-val-v2.0.json"
    )
    evidence.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    history = Path(config["candidate_history_dir"])
    history.mkdir(parents=True, exist_ok=False)
    (history / "best-pt-reference.txt").write_text(str(best) + "\n", encoding="utf-8")
    (history / "best-pt-sha256.txt").write_text(
        payload["checkpoint_sha256"] + "\n", encoding="utf-8"
    )
    (history / "experiment-config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (history / "metrics-val.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"evidence": str(evidence), **payload}, ensure_ascii=False))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("smoke", "train", "val"))
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    config = load_config(args.config)
    if args.mode == "smoke":
        run_training(config, smoke=True)
    elif args.mode == "train":
        run_training(config, smoke=False)
    else:
        run_val(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
