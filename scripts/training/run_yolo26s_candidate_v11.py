"""Run the single authorized YOLO26s@640 smoke, train, and val-only experiment."""

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

REQUIRED_FIXED = {
    "imgsz": 640,
    "epochs": 100,
    "patience": 25,
    "seed": 42,
    "device": 0,
    "optimizer": "auto",
    "amp": True,
    "cache": False,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_config(path: str | Path) -> dict[str, Any]:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if Path(config["model"]).name != "yolo26s.pt":
        raise ValueError("the only authorized candidate is yolo26s.pt")
    for key, expected in REQUIRED_FIXED.items():
        if config.get(key) != expected:
            raise ValueError(f"fixed parameter drift: {key}={config.get(key)!r}")
    return config


def _rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _assert_finite(rows: list[dict[str, str]]) -> None:
    for row in rows:
        for key, value in row.items():
            if value and key != "epoch":
                try:
                    number = float(value)
                except ValueError:
                    continue
                if not math.isfinite(number):
                    raise RuntimeError(f"non-finite training metric: {key}={value}")


def run_training(config: dict[str, Any], *, smoke: bool) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the authorized candidate experiment")
    spec = config["smoke"] if smoke else config
    name = spec["name"]
    run_dir = Path(spec["project"]) / name
    if run_dir.exists():
        raise RuntimeError(
            f"run directory already exists; refusing implicit overwrite: {run_dir}"
        )
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    started = time.perf_counter()
    model = YOLO(config["model"])
    result = model.train(
        data=config["dataset_yaml"],
        imgsz=config["imgsz"],
        epochs=spec["epochs"] if smoke else config["epochs"],
        patience=config["patience"],
        batch=config["batch"],
        device=config["device"],
        workers=config["workers"],
        cache=config["cache"],
        seed=config["seed"],
        deterministic=config["deterministic"],
        optimizer=config["optimizer"],
        pretrained=config["pretrained"],
        amp=config["amp"],
        project=spec["project"] if smoke else config["project"],
        name=name,
        save=config["save"],
        save_period=config["save_period"],
        fraction=spec.get("fraction", 1.0),
        exist_ok=False,
        verbose=True,
    )
    elapsed = time.perf_counter() - started
    actual_dir = Path(result.save_dir)
    rows = _rows(actual_dir / "results.csv")
    _assert_finite(rows)
    best = actual_dir / "weights/best.pt"
    last = actual_dir / "weights/last.pt"
    payload = {
        "report_version": "yolo26s-smoke-v1.1" if smoke else "yolo26s-training-v1.1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "experiment_id": config["experiment_id"],
        "mode": "smoke" if smoke else "train",
        "dataset_split_usage": ["train", "val"],
        "test_accessed": False,
        "cuda": torch.cuda.is_available(),
        "gpu": torch.cuda.get_device_name(0),
        "amp": config["amp"],
        "epochs_requested": spec["epochs"] if smoke else config["epochs"],
        "epochs_completed": len(rows),
        "validation_completed": any("metrics/mAP50-95(B)" in row for row in rows),
        "nan_detected": False,
        "duration_seconds": elapsed,
        "peak_gpu_memory_bytes": torch.cuda.max_memory_allocated(),
        "run_dir": str(actual_dir),
        "best_pt": str(best),
        "best_pt_sha256": sha256(best),
        "last_pt": str(last),
        "last_pt_sha256": sha256(last),
        "passed": len(rows) == (spec["epochs"] if smoke else len(rows)) and bool(rows),
    }
    output = Path("E:/JianZhengData/runtime/competition-rc-v1.1/evidence") / (
        "yolo26s-smoke-v1.1.json" if smoke else "yolo26s-training-v1.1.json"
    )
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(output), **payload}, ensure_ascii=False))
    return payload


def _metric_values(metrics) -> dict[str, Any]:
    names = [metrics.names[index] for index in sorted(metrics.names)]
    precision = list(map(float, metrics.box.p))
    recall = list(map(float, metrics.box.r))
    map50 = list(map(float, metrics.box.ap50))
    map5095 = list(map(float, metrics.box.ap))
    return {
        "overall": {
            "precision": float(metrics.box.mp),
            "recall": float(metrics.box.mr),
            "mAP50": float(metrics.box.map50),
            "mAP50-95": float(metrics.box.map),
        },
        "per_class": {
            name: {
                "precision": precision[index],
                "recall": recall[index],
                "mAP50": map50[index],
                "mAP50-95": map5095[index],
            }
            for index, name in enumerate(names)
        },
    }


def run_val(config: dict[str, Any]) -> dict[str, Any]:
    run_dir = Path(config["project"]) / config["name"]
    best = run_dir / "weights/best.pt"
    if not best.is_file():
        raise RuntimeError(f"candidate best.pt missing: {best}")
    output_dir = run_dir / "evaluation-val-only"
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
        project=str(output_dir),
        name="val-best",
        exist_ok=False,
        plots=True,
        verbose=True,
    )
    elapsed = time.perf_counter() - started
    payload = {
        "report_version": "yolo26s-val-v1.1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "experiment_id": config["experiment_id"],
        "split": "val",
        "test_accessed": False,
        "checkpoint": str(best),
        "checkpoint_sha256": sha256(best),
        "imgsz": config["imgsz"],
        "model_bytes": best.stat().st_size,
        "duration_seconds": elapsed,
        "speed_ms_per_image": {
            key: float(value) for key, value in metrics.speed.items()
        },
        "peak_gpu_memory_bytes": torch.cuda.max_memory_allocated(),
        **_metric_values(metrics),
        "ultralytics_version": ultralytics.__version__,
        "output_dir": str(metrics.save_dir),
    }
    output = Path(
        "E:/JianZhengData/runtime/competition-rc-v1.1/evidence/yolo26s-val-v1.1.json"
    )
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    candidate_dir = Path(config["candidate_dir"])
    candidate_dir.mkdir(parents=True, exist_ok=False)
    (candidate_dir / "best-pt-reference.txt").write_text(
        str(best) + "\n", encoding="utf-8"
    )
    (candidate_dir / "best-pt-sha256.txt").write_text(
        payload["checkpoint_sha256"] + "\n", encoding="utf-8"
    )
    (candidate_dir / "metrics-val.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (candidate_dir / "experiment-config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(output), **payload}, ensure_ascii=False))
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
