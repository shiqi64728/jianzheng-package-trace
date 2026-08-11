"""Seal the one-time candidate test, select active model, export and verify ONNX."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from ultralytics import YOLO

CANDIDATE = Path(
    "E:/JianZhengData/models/experiments/d02-d03-yolo26n-imgsz960-v0.1/best.pt"
)
CANDIDATE_SHA = "2dd857412b63df66d1273b326dc51afaed895da1d360c97e184762c882181a97"
BASELINE = Path(
    "E:/JianZhengData/models/releases/d02-d03-yolo26n-baseline-v0.1/best.pt"
)
BASELINE_METRICS = Path(
    "E:/JianZhengData/models/releases/d02-d03-yolo26n-baseline-v0.1/metrics.json"
)
DATASET_ROOT = Path("E:/JianZhengData/training/detect-d02-d03-v0.1")
DATASET_LOCK_SHA = "6d496281ade6486434c0eb85a473b2bd3e8e5574bcc51ca1d371895851ea6e97"
RUNTIME_ROOT = Path("E:/JianZhengData/runtime/mvp-v0.1")
TEST_JSON = RUNTIME_ROOT / "logs/candidate-test-v0.1.json"
ACTIVE_JSON = Path("E:/JianZhengData/models/active/detector-v0.1.json")
MODEL_RUNTIME = Path("E:/JianZhengData/models/runtime/detector-v0.1")
ONNX_REPORT = MODEL_RUNTIME / "onnx-parity-report-v0.1.json"


class PreparationError(RuntimeError):
    """Raised when an immutable model preparation gate fails."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def metric_payload(metrics: Any) -> dict[str, Any]:
    overall = {
        "precision": float(metrics.box.mp),
        "recall": float(metrics.box.mr),
        "mAP50": float(metrics.box.map50),
        "mAP50-95": float(metrics.box.map),
    }
    per_class: dict[str, dict[str, Any]] = {}
    for item in metrics.summary(normalize=True, decimals=10):
        per_class[str(item["Class"])] = {
            "images": int(item["Images"]),
            "instances": int(item["Instances"]),
            "precision": float(item["Box-P"]),
            "recall": float(item["Box-R"]),
            "mAP50": float(item["mAP50"]),
            "mAP50-95": float(item["mAP50-95"]),
        }
    if any(not math.isfinite(value) for value in overall.values()):
        raise PreparationError("评估产生非有限指标。")
    return {
        "overall": overall,
        "per_class": per_class,
        "speed": {
            f"{key}_ms_per_image": float(value)
            for key, value in (getattr(metrics, "speed", {}) or {}).items()
        },
    }


def verify_contract() -> int:
    if sha256_file(CANDIDATE) != CANDIDATE_SHA:
        raise PreparationError("960 candidate SHA-256不一致。")
    lock = DATASET_ROOT / "dataset-lock.json"
    if sha256_file(lock) != DATASET_LOCK_SHA:
        raise PreparationError("冻结dataset-lock SHA-256不一致。")
    with (DATASET_ROOT / "dataset-manifest.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        test_count = sum(1 for row in csv.DictReader(stream) if row["split"] == "test")
    if test_count != 33:
        raise PreparationError(f"冻结test图片数不是33：{test_count}")
    return test_count


def seal_candidate_test() -> dict[str, Any]:
    """Run exactly one formal 960 test and refuse all subsequent attempts."""
    test_count = verify_contract()
    evaluation = RUNTIME_ROOT / "logs/candidate-test-evaluation"
    if TEST_JSON.exists() or evaluation.exists():
        raise PreparationError("candidate test已封存或存在输出，拒绝再次运行。")
    started = time.perf_counter()
    metrics = YOLO(CANDIDATE).val(
        data=str(DATASET_ROOT / "dataset.yaml"),
        split="test",
        imgsz=960,
        batch=8,
        device=0,
        workers=4,
        project=str(evaluation.parent),
        name=evaluation.name,
        exist_ok=False,
        plots=True,
        verbose=True,
    )
    payload = {
        "schema_version": "candidate-test-v0.1",
        "sealed": True,
        "one_time_formal_test": True,
        "generated_at": datetime.now().astimezone().isoformat(),
        "checkpoint": str(CANDIDATE),
        "checkpoint_sha256": CANDIDATE_SHA,
        "dataset": str(DATASET_ROOT / "dataset.yaml"),
        "dataset_lock_sha256": DATASET_LOCK_SHA,
        "split": "test",
        "test_image_count": test_count,
        "imgsz": 960,
        "batch": 8,
        "device": 0,
        "workers": 4,
        "threshold_tuning_performed": False,
        **metric_payload(metrics),
        "duration_seconds": time.perf_counter() - started,
        "output_dir": str(evaluation),
    }
    write_json(TEST_JSON, payload)
    return payload


def select_active() -> dict[str, Any]:
    verify_contract()
    if not TEST_JSON.is_file():
        raise PreparationError("candidate test尚未封存。")
    if ACTIVE_JSON.exists():
        raise PreparationError("活动模型注册表已存在，拒绝覆盖。")
    candidate = json.loads(TEST_JSON.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE_METRICS.read_text(encoding="utf-8"))["test"]
    candidate_map = float(candidate["overall"]["mAP50-95"])
    baseline_map = float(baseline["overall"]["mAP50-95"])
    promoted = candidate_map > baseline_map
    source = CANDIDATE if promoted else BASELINE
    payload = {
        "registry_version": "detector-v0.1",
        "active_model": "960_candidate" if promoted else "640_baseline",
        "model_version": (
            "d02-d03-yolo26n-imgsz960-v0.1"
            if promoted
            else "d02-d03-yolo26n-baseline-v0.1"
        ),
        "source_pt": str(source),
        "sha256": sha256_file(source),
        "imgsz": 960 if promoted else 640,
        "classes": ["D02", "D03"],
        "unsupported_classes": {
            "D01": "detector_not_supported_yet",
            "D04": "detector_not_supported_yet",
            "D05": "detector_not_supported_yet",
        },
        "selection_basis": "higher frozen test mAP50-95; no threshold tuning",
        "baseline_test_metrics": baseline,
        "candidate_test_metrics": candidate,
        "selected_at": datetime.now().astimezone().isoformat(),
        "runtime_preferred": "pytorch",
        "onnx_status": "not_exported",
    }
    write_json(ACTIVE_JSON, payload)
    return payload


def export_onnx() -> dict[str, Any]:
    import onnx
    import onnxruntime
    import ultralytics

    registry = json.loads(ACTIVE_JSON.read_text(encoding="utf-8"))
    MODEL_RUNTIME.mkdir(parents=True, exist_ok=True)
    onnx_path = MODEL_RUNTIME / "detector.onnx"
    metadata_path = MODEL_RUNTIME / "detector.metadata.json"
    source_copy = MODEL_RUNTIME / "detector-source.pt"
    if onnx_path.exists() or metadata_path.exists() or source_copy.exists():
        raise PreparationError("ONNX运行时输出已存在，拒绝覆盖。")
    shutil.copy2(registry["source_pt"], source_copy)
    try:
        exported = Path(
            YOLO(source_copy).export(
                format="onnx",
                imgsz=int(registry["imgsz"]),
                batch=1,
                dynamic=False,
                half=False,
                simplify=False,
                opset=19,
                device="cpu",
            )
        )
        if exported.resolve() != onnx_path.resolve():
            shutil.move(str(exported), onnx_path)
        model = onnx.load(str(onnx_path))
        onnx.checker.check_model(model)
        session = onnxruntime.InferenceSession(
            str(onnx_path), providers=["CPUExecutionProvider"]
        )
        input_meta = session.get_inputs()[0]
        shape = [1, 3, int(registry["imgsz"]), int(registry["imgsz"])]
        outputs = session.run(
            None, {input_meta.name: np.zeros(shape, dtype=np.float32)}
        )
        if not outputs:
            raise PreparationError("ONNX Runtime推理没有输出。")
        metadata = {
            "artifact_version": "detector-onnx-v0.1",
            "source_pt": registry["source_pt"],
            "source_pt_sha256": registry["sha256"],
            "onnx_path": str(onnx_path),
            "onnx_sha256": sha256_file(onnx_path),
            "export_time": datetime.now().astimezone().isoformat(),
            "format": "FP32",
            "batch": 1,
            "dynamic": False,
            "imgsz": registry["imgsz"],
            "classes": registry["classes"],
            "ultralytics_version": ultralytics.__version__,
            "onnx_version": onnx.__version__,
            "onnxruntime_version": onnxruntime.__version__,
            "onnx_load_ok": True,
            "onnxruntime_inference_ok": True,
            "onnx_output_shapes": [list(item.shape) for item in outputs],
        }
        write_json(metadata_path, metadata)
        return metadata
    finally:
        source_copy.unlink(missing_ok=True)


def _validate_artifact(
    artifact: Path, runtime_name: str, imgsz: int, output_name: str
) -> dict[str, Any]:
    output_root = MODEL_RUNTIME / "parity"
    output = output_root / output_name
    if output.exists():
        raise PreparationError(f"parity输出已存在：{output}")
    started = time.perf_counter()
    metrics = YOLO(artifact).val(
        data=str(DATASET_ROOT / "dataset.yaml"),
        split="val",
        imgsz=imgsz,
        batch=8,
        device=0 if runtime_name == "pytorch" else "cpu",
        workers=4,
        project=str(output_root),
        name=output_name,
        exist_ok=False,
        plots=False,
        verbose=True,
    )
    return {
        "runtime": runtime_name,
        "artifact": str(artifact),
        **metric_payload(metrics),
        "duration_seconds": time.perf_counter() - started,
        "output_dir": str(output),
    }


def validate_parity() -> dict[str, Any]:
    if ONNX_REPORT.exists():
        raise PreparationError("ONNX parity已存在，拒绝覆盖。")
    registry = json.loads(ACTIVE_JSON.read_text(encoding="utf-8"))
    metadata_path = MODEL_RUNTIME / "detector.metadata.json"
    onnx_path = MODEL_RUNTIME / "detector.onnx"
    if not metadata_path.is_file() or not onnx_path.is_file():
        raise PreparationError("ONNX导出制品不完整。")
    pt = _validate_artifact(
        Path(registry["source_pt"]), "pytorch", int(registry["imgsz"]), "pt-val"
    )
    onnx_result = _validate_artifact(
        onnx_path, "onnx", int(registry["imgsz"]), "onnx-val"
    )
    deltas = {
        key: onnx_result["overall"][key] - pt["overall"][key]
        for key in ("precision", "recall", "mAP50", "mAP50-95")
    }
    parity_ok = abs(deltas["mAP50"]) <= 0.01 and abs(deltas["mAP50-95"]) <= 0.005
    report = {
        "report_version": "onnx-parity-report-v0.1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "validation_image_count": 64,
        "same_frozen_val": True,
        "pytorch": pt,
        "onnx": onnx_result,
        "metric_delta_onnx_minus_pt": deltas,
        "parity_tolerance": {"mAP50": 0.01, "mAP50-95": 0.005},
        "parity_ok": parity_ok,
        "runtime_preferred": "onnx" if parity_ok else "pytorch",
        "onnx_status": "validated" if parity_ok else "experimental",
    }
    write_json(ONNX_REPORT, report)
    registry.update(
        {
            "runtime_preferred": report["runtime_preferred"],
            "onnx_status": report["onnx_status"],
            "onnx_path": str(onnx_path),
            "onnx_sha256": sha256_file(onnx_path),
            "onnx_parity_report": str(ONNX_REPORT),
        }
    )
    write_json(ACTIVE_JSON, registry)
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "phase", choices=("candidate-test", "select", "export-onnx", "parity")
    )
    args = parser.parse_args()
    actions = {
        "candidate-test": seal_candidate_test,
        "select": select_active,
        "export-onnx": export_onnx,
        "parity": validate_parity,
    }
    print(json.dumps(actions[args.phase](), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
