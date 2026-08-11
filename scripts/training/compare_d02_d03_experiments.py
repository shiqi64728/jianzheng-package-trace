"""Run val-only diagnostics and compare the D02/D03 640 and 960 experiments."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import torch
from ultralytics import YOLO, __version__ as ultralytics_version

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.training.analyze_d02_d03_object_sizes import (  # noqa: E402
    CLASS_NAMES,
    QUARTILE_NAMES,
)
from scripts.training.evaluate_d02_d03_baseline import (  # noqa: E402
    _draw_ground_truth,
    _iou,
    _metric_payload,
    _read_manifest,
    _read_yolo_labels,
    _stable_sample,
)
from scripts.training.prepare_d02_d03_dataset import (  # noqa: E402
    sha256_file,
    validate_frozen_dataset,
)
from scripts.training.train_d02_d03_baseline import (  # noqa: E402
    load_experiment_config,
)

EXPECTED_DATASET_LOCK_SHA256 = (
    "6d496281ade6486434c0eb85a473b2bd3e8e5574bcc51ca1d371895851ea6e97"
)
EXPECTED_PRETRAINED_SHA256 = (
    "9b09cc8bf347f0fc8a5f7657480587f25db09b34bf33b0652110fb03a8ad4fef"
)
EXPECTED_BASELINE_BEST_SHA256 = (
    "1959fcaf71987e52e5475f7601fc10ca7e40e7b747ddf085705135dccb0ed74f"
)
BASELINE_VAL_EXPECTED = {
    "overall": {
        "precision": 0.3311082243171223,
        "recall": 0.2427983729314967,
        "mAP50": 0.19322484099724105,
        "mAP50-95": 0.08313219083320952,
    },
    "per_class": {
        "D02_surface_dent": {
            "precision": 0.2924720829,
            "recall": 0.1924932976,
            "mAP50": 0.1315223695,
            "mAP50-95": 0.0371907602,
        },
        "D03_carton_tear": {
            "precision": 0.3697443657,
            "recall": 0.2931034483,
            "mAP50": 0.2549273125,
            "mAP50-95": 0.1290736214,
        },
    },
}
ALLOWED_CONFIG_DIFFERENCES = {
    "experiment_id",
    "imgsz",
    "name",
    "smoke.name",
    "candidate_dir",
    "comparison_dir",
    "baseline_config",
    "baseline_best",
    "baseline_run",
}
METRIC_KEYS = ("precision", "recall", "mAP50", "mAP50-95")
FAILURE_FIELDS = [
    "image_relpath",
    "bbox_id",
    "ground_truth_class",
    "predicted_class",
    "confidence",
    "failure_type",
    "overall_quartile",
    "normalized_area",
    "notes",
]


class ExperimentComparisonError(RuntimeError):
    """Raised when the single-variable experiment contract is violated."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExperimentComparisonError(f"无法读取JSON：{path}：{exc}") from exc
    if not isinstance(data, dict):
        raise ExperimentComparisonError(f"JSON根节点必须是对象：{path}")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def verify_hash_contract(
    dataset_lock: Path,
    pretrained_weight: Path,
    baseline_best: Path,
    expected_dataset_lock: str = EXPECTED_DATASET_LOCK_SHA256,
    expected_pretrained: str = EXPECTED_PRETRAINED_SHA256,
    expected_baseline_best: str = EXPECTED_BASELINE_BEST_SHA256,
) -> dict[str, str]:
    actual = {
        "dataset_lock_sha256": sha256_file(dataset_lock),
        "pretrained_weight_sha256": sha256_file(pretrained_weight),
        "baseline_best_sha256": sha256_file(baseline_best),
    }
    expected = {
        "dataset_lock_sha256": expected_dataset_lock,
        "pretrained_weight_sha256": expected_pretrained,
        "baseline_best_sha256": expected_baseline_best,
    }
    mismatches = [key for key in actual if actual[key] != expected[key]]
    if mismatches:
        raise ExperimentComparisonError(
            f"冻结哈希合同发生变化：{', '.join(mismatches)}"
        )
    return actual


def validate_candidate_path(candidate_dir: Path, external_model_root: Path) -> None:
    experiments_root = external_model_root / "experiments"
    releases_root = external_model_root / "releases"
    if not _is_within(candidate_dir, experiments_root):
        raise ExperimentComparisonError("candidate目录必须位于models/experiments。")
    if _is_within(candidate_dir, releases_root):
        raise ExperimentComparisonError("candidate不得覆盖models/releases。")


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            flattened.update(_flatten(value, full_key))
        else:
            flattened[full_key] = value
    return flattened


def audit_experiment_configs(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    """Require imgsz to be the only active hyperparameter difference."""
    baseline_flat = _flatten(baseline)
    candidate_flat = _flatten(candidate)
    keys = sorted(set(baseline_flat) | set(candidate_flat))
    differences = []
    unexpected = []
    for key in keys:
        baseline_value = baseline_flat.get(key, "<MISSING>")
        candidate_value = candidate_flat.get(key, "<MISSING>")
        if baseline_value == candidate_value:
            continue
        row = {
            "key": key,
            "baseline": baseline_value,
            "candidate": candidate_value,
            "allowed": key in ALLOWED_CONFIG_DIFFERENCES,
        }
        differences.append(row)
        if not row["allowed"]:
            unexpected.append(key)
    if unexpected:
        raise ExperimentComparisonError(
            f"配置存在非单变量差异：{', '.join(unexpected)}"
        )
    required_differences = {"experiment_id", "imgsz", "name", "smoke.name"}
    changed = {row["key"] for row in differences}
    missing = sorted(required_differences - changed)
    if missing:
        raise ExperimentComparisonError(f"960配置缺少预期差异：{', '.join(missing)}")
    if baseline.get("imgsz") != 640 or candidate.get("imgsz") != 960:
        raise ExperimentComparisonError("imgsz差异必须严格为640→960。")
    return {
        "valid": True,
        "active_variable": "imgsz",
        "active_change": {"baseline": 640, "candidate": 960},
        "allowed_difference_keys": sorted(ALLOWED_CONFIG_DIFFERENCES),
        "differences": differences,
        "unexpected_differences": [],
    }


def ensure_validation_only(payload: Any) -> None:
    """Reject candidate artifacts that contain test evaluation data."""
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key.lower() == "test" and value not in (None, {}, [], ""):
                raise ExperimentComparisonError("candidate制品不得包含test结果。")
            if key.lower() == "split" and str(value).lower() == "test":
                raise ExperimentComparisonError("candidate不得访问split=test。")
            ensure_validation_only(value)
    elif isinstance(payload, list):
        for value in payload:
            ensure_validation_only(value)


def _contract_gate(config_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate = load_experiment_config(config_path)
    if candidate["experiment_id"] != "d02-d03-yolo26n-imgsz960-v0.1":
        raise ExperimentComparisonError("当前工具只允许960单变量candidate。")
    baseline_path = Path(str(candidate["baseline_config"]))
    baseline = load_experiment_config(baseline_path)
    diff = audit_experiment_configs(baseline, candidate)
    dataset_root = Path(str(candidate["dataset_yaml"])).parent
    validate_frozen_dataset(dataset_root)
    verify_hash_contract(
        Path(str(candidate["dataset_lock"])),
        Path(str(candidate["model"])),
        Path(str(candidate["baseline_best"])),
    )
    candidate_dir = Path(str(candidate["candidate_dir"]))
    validate_candidate_path(candidate_dir, Path(str(candidate["external_model_root"])))
    if candidate_dir.resolve() == Path(str(candidate["release_dir"])).resolve():
        raise ExperimentComparisonError("candidate不得覆盖models/releases。")
    return candidate, diff


def _speed(metrics: Any) -> dict[str, float]:
    values = getattr(metrics, "speed", {}) or {}
    return {
        "preprocess_ms_per_image": float(values.get("preprocess", 0.0)),
        "inference_ms_per_image": float(values.get("inference", 0.0)),
        "postprocess_ms_per_image": float(values.get("postprocess", 0.0)),
    }


def validate_val(
    checkpoint: Path,
    config: dict[str, Any],
    imgsz: int,
    output_root: Path,
    name: str,
    plots: bool,
) -> dict[str, Any]:
    """Validate one checkpoint on val only; split is intentionally not configurable."""
    output = output_root / name
    if output.exists():
        raise ExperimentComparisonError(f"val输出已存在，拒绝覆盖：{output}")
    model = YOLO(checkpoint)
    if model.task != "detect":
        raise ExperimentComparisonError(f"checkpoint task不是detect：{checkpoint}")
    started = time.perf_counter()
    metrics = model.val(
        data=str(config["dataset_yaml"]),
        split="val",
        imgsz=imgsz,
        batch=int(config.get("evaluation_batch", 8)),
        device=int(config["device"]),
        workers=int(config["workers"]),
        project=str(output_root),
        name=name,
        exist_ok=False,
        plots=plots,
        verbose=True,
    )
    payload = _metric_payload(metrics)
    payload.update(
        {
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": sha256_file(checkpoint),
            "split": "val",
            "imgsz": imgsz,
            "duration_seconds": time.perf_counter() - started,
            "speed": _speed(metrics),
            "output_dir": str(output),
        }
    )
    ensure_validation_only(payload)
    return payload


def _assert_baseline_reproduced(actual: dict[str, Any]) -> None:
    tolerance = 1e-6
    for key in METRIC_KEYS:
        if (
            abs(actual["overall"][key] - BASELINE_VAL_EXPECTED["overall"][key])
            > tolerance
        ):
            raise ExperimentComparisonError(f"640 val复现指标异常偏差：overall.{key}")
    for class_name in CLASS_NAMES.values():
        for key in METRIC_KEYS:
            if (
                abs(
                    actual["per_class"][class_name][key]
                    - BASELINE_VAL_EXPECTED["per_class"][class_name][key]
                )
                > tolerance
            ):
                raise ExperimentComparisonError(
                    f"640 val复现指标异常偏差：{class_name}.{key}"
                )


def run_diagnostics(config_path: Path) -> dict[str, Any]:
    config, diff = _contract_gate(config_path)
    comparison_dir = Path(str(config["comparison_dir"]))
    comparison_dir.mkdir(parents=True, exist_ok=True)
    diff_path = comparison_dir / "experiment-config-diff.json"
    baseline_640_path = comparison_dir / "baseline-640-val.json"
    baseline_960_path = comparison_dir / "baseline-960-inference-val.json"
    if any(path.exists() for path in (diff_path, baseline_640_path, baseline_960_path)):
        raise ExperimentComparisonError("诊断输出已存在，拒绝覆盖。")
    _write_json(diff_path, diff)
    diagnostics_root = comparison_dir / "diagnostics"
    checkpoint = Path(str(config["baseline_best"]))
    baseline_640 = validate_val(
        checkpoint, config, 640, diagnostics_root, "baseline-640-val", True
    )
    _assert_baseline_reproduced(baseline_640)
    _write_json(baseline_640_path, baseline_640)
    baseline_960 = validate_val(
        checkpoint, config, 960, diagnostics_root, "baseline-960-inference-val", True
    )
    _write_json(baseline_960_path, baseline_960)
    return {
        "config_diff": diff,
        "baseline_640_val": baseline_640,
        "baseline_960_inference_val": baseline_960,
        "candidate_test_accessed": False,
    }


def _load_size_index(comparison_dir: Path) -> dict[str, dict[str, str]]:
    path = comparison_dir / "object-size-distribution-v0.1.csv"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    return {row["bbox_id"]: row for row in rows}


def _prediction_rows(result: Any) -> list[dict[str, Any]]:
    boxes = result.boxes
    if boxes is None or not len(boxes):
        return []
    xyxy = boxes.xyxy.detach().cpu().numpy()
    classes = boxes.cls.detach().cpu().numpy().astype(int)
    confidences = boxes.conf.detach().cpu().numpy()
    return [
        {"xyxy": box, "class_id": int(class_id), "confidence": float(confidence)}
        for box, class_id, confidence in zip(xyxy, classes, confidences, strict=True)
    ]


def _image_failures(
    image_relpath: str,
    labels: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    size_index: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    matched_predictions: set[int] = set()
    for label_index, ground_truth in enumerate(labels):
        bbox_id = f"{image_relpath}#{label_index}"
        size = size_index.get(bbox_id)
        if size is None:
            raise ExperimentComparisonError(f"目标尺寸索引缺失：{bbox_id}")
        candidates = [
            (index, _iou(ground_truth["xyxy"], prediction["xyxy"]))
            for index, prediction in enumerate(predictions)
            if index not in matched_predictions
        ]
        best_index, best_iou = max(
            candidates, key=lambda item: item[1], default=(-1, 0.0)
        )
        gt_name = CLASS_NAMES[ground_truth["class_id"]]
        primary_failure = ""
        predicted_class = ""
        confidence = ""
        if best_index >= 0 and best_iou >= 0.5:
            prediction = predictions[best_index]
            matched_predictions.add(best_index)
            predicted_class = CLASS_NAMES.get(
                prediction["class_id"], str(prediction["class_id"])
            )
            confidence = f"{prediction['confidence']:.8f}"
            if prediction["class_id"] != ground_truth["class_id"]:
                primary_failure = "D02_D03_confusion"
        elif best_index >= 0 and best_iou >= 0.1:
            prediction = predictions[best_index]
            matched_predictions.add(best_index)
            predicted_class = CLASS_NAMES.get(
                prediction["class_id"], str(prediction["class_id"])
            )
            confidence = f"{prediction['confidence']:.8f}"
            primary_failure = "low_iou"
        else:
            primary_failure = "missed_detection"
        if primary_failure:
            common = {
                "image_relpath": image_relpath,
                "bbox_id": bbox_id,
                "ground_truth_class": gt_name,
                "predicted_class": predicted_class,
                "confidence": confidence,
                "overall_quartile": size["overall_quartile"],
                "normalized_area": size["normalized_area"],
            }
            failures.append(
                {
                    **common,
                    "failure_type": primary_failure,
                    "notes": f"best_IoU={best_iou:.6f}",
                }
            )
            if size["overall_quartile"] == "smallest_quartile":
                failures.append(
                    {
                        **common,
                        "failure_type": "small_target_failure",
                        "notes": f"overall_area_quartile=smallest;source_failure={primary_failure}",
                    }
                )
    for index, prediction in enumerate(predictions):
        if index not in matched_predictions and prediction["confidence"] >= 0.5:
            failures.append(
                {
                    "image_relpath": image_relpath,
                    "bbox_id": "",
                    "ground_truth_class": "",
                    "predicted_class": CLASS_NAMES.get(
                        prediction["class_id"], str(prediction["class_id"])
                    ),
                    "confidence": f"{prediction['confidence']:.8f}",
                    "failure_type": "high_confidence_false_positive",
                    "overall_quartile": "",
                    "normalized_area": "",
                    "notes": "confidence>=0.5且未匹配IoU>=0.5真值框",
                }
            )
    return failures


def analyze_val_failures(
    model: YOLO,
    dataset_root: Path,
    imgsz: int,
    config: dict[str, Any],
    size_index: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows = [
        row
        for row in _read_manifest(dataset_root / "dataset-manifest.csv")
        if row["split"] == "val"
    ]
    paths = [dataset_root / row["target_image_relpath"] for row in rows]
    results = model.predict(
        source=[str(path) for path in paths],
        imgsz=imgsz,
        batch=int(config.get("evaluation_batch", 8)),
        device=int(config["device"]),
        conf=0.001,
        iou=0.7,
        verbose=False,
    )
    failures: list[dict[str, Any]] = []
    for row, image_path, result in zip(rows, paths, results, strict=True):
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ExperimentComparisonError(f"val图片无法读取：{image_path}")
        labels = _read_yolo_labels(
            dataset_root / row["target_label_relpath"], image.shape[1], image.shape[0]
        )
        failures.extend(
            _image_failures(
                row["target_image_relpath"],
                labels,
                _prediction_rows(result),
                size_index,
            )
        )
    return failures


def _failure_summary(
    failures: list[dict[str, Any]], size_index: dict[str, dict[str, str]]
) -> dict[str, Any]:
    counts = Counter(row["failure_type"] for row in failures)
    primary_types = {"low_iou", "missed_detection", "D02_D03_confusion"}
    failed_bbox_ids = {
        row["bbox_id"]
        for row in failures
        if row["failure_type"] in primary_types and row["bbox_id"]
    }
    denominators: Counter[str] = Counter()
    d02_denominators: Counter[str] = Counter()
    for row in size_index.values():
        if row["split"] != "val":
            continue
        quartile = row["overall_quartile"]
        denominators[quartile] += 1
        if row["class_name"] == "D02_surface_dent":
            d02_denominators[quartile] += 1
    failed_by_quartile: Counter[str] = Counter()
    d02_failed_by_quartile: Counter[str] = Counter()
    for bbox_id in failed_bbox_ids:
        size = size_index[bbox_id]
        quartile = size["overall_quartile"]
        failed_by_quartile[quartile] += 1
        if size["class_name"] == "D02_surface_dent":
            d02_failed_by_quartile[quartile] += 1
    quartiles = {}
    for quartile in QUARTILE_NAMES:
        denominator = denominators[quartile]
        d02_denominator = d02_denominators[quartile]
        quartiles[quartile] = {
            "gt_bbox_count": denominator,
            "failed_gt_bbox_count": failed_by_quartile[quartile],
            "failure_rate": failed_by_quartile[quartile] / denominator
            if denominator
            else 0.0,
            "d02_gt_bbox_count": d02_denominator,
            "d02_failed_gt_bbox_count": d02_failed_by_quartile[quartile],
            "d02_failure_rate": d02_failed_by_quartile[quartile] / d02_denominator
            if d02_denominator
            else 0.0,
        }
    return {
        "record_count": len(failures),
        "failure_type_counts": dict(counts),
        "unique_failed_gt_bbox_count": len(failed_bbox_ids),
        "quartile_failure_rates": quartiles,
        "bbox_level_association": "reliable_via_image_relpath_and_label_index",
    }


def _qualitative_comparison(
    baseline_model: YOLO,
    candidate_model: YOLO,
    dataset_root: Path,
    output_dir: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    if output_dir.exists():
        raise ExperimentComparisonError(f"qualitative输出已存在：{output_dir}")
    rows = [
        row
        for row in _read_manifest(dataset_root / "dataset-manifest.csv")
        if row["split"] == "val"
    ]
    selected = _stable_sample(rows, 20, int(config["seed"]))
    paths = [dataset_root / row["target_image_relpath"] for row in selected]
    baseline_results = baseline_model.predict(
        source=[str(path) for path in paths],
        imgsz=640,
        batch=int(config.get("evaluation_batch", 8)),
        device=int(config["device"]),
        conf=0.25,
        iou=0.7,
        verbose=False,
    )
    candidate_results = candidate_model.predict(
        source=[str(path) for path in paths],
        imgsz=960,
        batch=int(config.get("evaluation_batch", 8)),
        device=int(config["device"]),
        conf=0.25,
        iou=0.7,
        verbose=False,
    )
    gt_dir = output_dir / "ground-truth"
    baseline_dir = output_dir / "baseline-640"
    candidate_dir = output_dir / "candidate-960"
    gt_dir.mkdir(parents=True)
    baseline_dir.mkdir()
    candidate_dir.mkdir()
    manifest_rows = []
    for row, image_path, baseline_result, candidate_result in zip(
        selected, paths, baseline_results, candidate_results, strict=True
    ):
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise ExperimentComparisonError(f"qualitative图片无法读取：{image_path}")
        labels = _read_yolo_labels(
            dataset_root / row["target_label_relpath"], image.shape[1], image.shape[0]
        )
        outputs = {
            "ground_truth": gt_dir / image_path.name,
            "baseline_640": baseline_dir / image_path.name,
            "candidate_960": candidate_dir / image_path.name,
        }
        canvases = {
            "ground_truth": _draw_ground_truth(image, labels),
            "baseline_640": baseline_result.plot(),
            "candidate_960": candidate_result.plot(),
        }
        for key, output in outputs.items():
            if not cv2.imwrite(str(output), canvases[key]):
                raise ExperimentComparisonError(f"无法写入qualitative图片：{output}")
        manifest_rows.append(
            {
                "external_record_id": row["external_record_id"],
                "split": "val",
                "image_relpath": row["target_image_relpath"],
                "ground_truth_relpath": outputs["ground_truth"]
                .relative_to(output_dir)
                .as_posix(),
                "baseline_640_relpath": outputs["baseline_640"]
                .relative_to(output_dir)
                .as_posix(),
                "candidate_960_relpath": outputs["candidate_960"]
                .relative_to(output_dir)
                .as_posix(),
            }
        )
    _write_csv(
        output_dir / "qualitative-comparison-manifest.csv",
        [
            "external_record_id",
            "split",
            "image_relpath",
            "ground_truth_relpath",
            "baseline_640_relpath",
            "candidate_960_relpath",
        ],
        manifest_rows,
    )
    return {
        "split": "val",
        "seed": int(config["seed"]),
        "sample_count": len(manifest_rows),
        "same_sample_list_for_both_models": True,
        "manifest": str(output_dir / "qualitative-comparison-manifest.csv"),
    }


def metric_change(baseline: float, candidate: float) -> dict[str, float | None]:
    absolute = candidate - baseline
    relative = absolute / abs(baseline) * 100 if baseline != 0 else None
    return {
        "baseline": baseline,
        "candidate": candidate,
        "absolute_change": absolute,
        "relative_change_percent": relative,
    }


def _comparison_rows(
    baseline_val: dict[str, Any],
    candidate_val: dict[str, Any],
    baseline_training: dict[str, Any],
    candidate_training: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in METRIC_KEYS:
        rows.append(
            {
                "metric": f"overall.{key}",
                **metric_change(
                    baseline_val["overall"][key], candidate_val["overall"][key]
                ),
            }
        )
    for class_name in CLASS_NAMES.values():
        for key in METRIC_KEYS:
            rows.append(
                {
                    "metric": f"{class_name}.{key}",
                    **metric_change(
                        baseline_val["per_class"][class_name][key],
                        candidate_val["per_class"][class_name][key],
                    ),
                }
            )
    scalar_pairs = {
        "actual_batch": (
            baseline_training["actual_batch"],
            candidate_training["actual_batch"],
        ),
        "best_epoch": (
            baseline_training["best_epoch"],
            candidate_training["best_epoch"],
        ),
        "training_duration_seconds": (
            baseline_training["duration_seconds"],
            candidate_training["duration_seconds"],
        ),
        "average_epoch_seconds": (
            baseline_training["average_epoch_seconds"],
            candidate_training["average_epoch_seconds"],
        ),
        "peak_gpu_memory_bytes": (
            baseline_training["peak_gpu_memory_bytes"],
            candidate_training["peak_gpu_memory_bytes"],
        ),
        "inference_ms_per_image": (
            baseline_val["speed"]["inference_ms_per_image"],
            candidate_val["speed"]["inference_ms_per_image"],
        ),
        "weight_size_bytes": (
            baseline_training["best_pt_size_bytes"],
            candidate_training["best_pt_size_bytes"],
        ),
    }
    for key, (baseline_value, candidate_value) in scalar_pairs.items():
        rows.append(
            {
                "metric": key,
                **metric_change(float(baseline_value), float(candidate_value)),
            }
        )
    return rows


def _recommendation(
    baseline_val: dict[str, Any], candidate_val: dict[str, Any]
) -> tuple[str, str]:
    overall_delta = (
        candidate_val["overall"]["mAP50-95"] - baseline_val["overall"]["mAP50-95"]
    )
    d02_ap_delta = (
        candidate_val["per_class"]["D02_surface_dent"]["mAP50-95"]
        - baseline_val["per_class"]["D02_surface_dent"]["mAP50-95"]
    )
    d02_recall_delta = (
        candidate_val["per_class"]["D02_surface_dent"]["recall"]
        - baseline_val["per_class"]["D02_surface_dent"]["recall"]
    )
    d03_ap_delta = (
        candidate_val["per_class"]["D03_carton_tear"]["mAP50-95"]
        - baseline_val["per_class"]["D03_carton_tear"]["mAP50-95"]
    )
    if (
        overall_delta > 0
        and d02_ap_delta > 0
        and d02_recall_delta > 0
        and d03_ap_delta > -0.01
    ):
        return (
            "PROMOTE_FOR_TEST",
            "总体mAP50-95、D02 AP50-95与D02 Recall均提高，且D03 AP50-95未明显回退。",
        )
    if overall_delta < 0 and d02_ap_delta <= 0:
        return "KEEP_BASELINE", "总体mAP50-95下降且D02 AP50-95没有改善。"
    return "INCONCLUSIVE", "关键指标方向不一致，不能仅凭本轮val结果晋级。"


def _write_comparison_markdown(path: Path, payload: dict[str, Any]) -> None:
    rows = payload["metric_changes"]
    lines = [
        "# D02/D03 YOLO26n 640 vs 960",
        "",
        "本比较只使用 validation；960 candidate 未访问 test。",
        "",
        "| 指标 | 640 | 960 | 绝对变化 | 相对变化% |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        relative = row["relative_change_percent"]
        relative_text = "N/A" if relative is None else f"{relative:.6f}"
        lines.append(
            f"| {row['metric']} | {row['baseline']:.10g} | {row['candidate']:.10g} | "
            f"{row['absolute_change']:.10g} | {relative_text} |"
        )
    lines.extend(
        [
            "",
            f"推荐：**{payload['recommendation']}**",
            "",
            payload["recommendation_reason"],
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _create_candidate_artifact(
    config_path: Path,
    config: dict[str, Any],
    candidate_metrics: dict[str, Any],
    comparison: dict[str, Any],
    failure_summary: dict[str, Any],
) -> dict[str, Any]:
    candidate_dir = Path(str(config["candidate_dir"]))
    if candidate_dir.exists():
        raise ExperimentComparisonError(f"candidate目录已存在：{candidate_dir}")
    run_dir = Path(str(config["project"])) / str(config["name"])
    best = run_dir / "weights" / "best.pt"
    last = run_dir / "weights" / "last.pt"
    candidate_dir.mkdir(parents=True)
    shutil.copyfile(best, candidate_dir / "best.pt")
    shutil.copyfile(config_path, candidate_dir / "experiment-config.json")
    _write_json(candidate_dir / "metrics-val.json", candidate_metrics)
    _write_json(candidate_dir / "comparison-vs-baseline.json", comparison)
    _write_json(candidate_dir / "failure-summary.json", failure_summary)
    best_sha = sha256_file(best)
    if sha256_file(candidate_dir / "best.pt") != best_sha:
        raise ExperimentComparisonError("candidate best.pt复制后SHA-256不一致。")
    (candidate_dir / "best-pt-sha256.txt").write_text(
        f"{best_sha}  best.pt\n", encoding="utf-8"
    )
    (candidate_dir / "last-pt-reference.txt").write_text(
        f"path={last}\nsha256={sha256_file(last)}\n", encoding="utf-8"
    )
    best_val = candidate_metrics["validation"]["best"]
    card = f"""# D02/D03 YOLO26n imgsz960 Experiment v0.1

- 状态：candidate experiment，未晋级正式 release
- 基础模型：Ultralytics YOLO26n Detection
- 初始化：官方 yolo26n.pt，而非 640 best.pt
- 数据版本：detect-d02-d03-v0.1
- 主动变量：imgsz 640 → 960
- Ultralytics：{ultralytics_version}
- PyTorch：{torch.__version__}
- GPU：{torch.cuda.get_device_name(0)}
- val Precision：{best_val["overall"]["precision"]:.10f}
- val Recall：{best_val["overall"]["recall"]:.10f}
- val mAP50：{best_val["overall"]["mAP50"]:.10f}
- val mAP50-95：{best_val["overall"]["mAP50-95"]:.10f}
- best.pt SHA-256：`{best_sha}`
- 推荐：{comparison["recommendation"]}

## Test封存

960 candidate 未访问 test。本实验目录不包含 candidate test 指标，只有用户批准晋级后才能执行一次正式 test。

## 限制

模型只识别 D02 表面凹陷和 D03 纸箱破口，不能定位责任节点或认定物流责任。当前结论仅基于冻结 val，不能替代独立 test 和真实站点外部验证。
"""
    (candidate_dir / "model-card-experiment.md").write_text(card, encoding="utf-8")
    return {
        "candidate_dir": str(candidate_dir),
        "best_pt": str(candidate_dir / "best.pt"),
        "best_pt_sha256": best_sha,
        "files": sorted(path.name for path in candidate_dir.iterdir()),
    }


def evaluate_candidate(config_path: Path) -> dict[str, Any]:
    config, _ = _contract_gate(config_path)
    comparison_dir = Path(str(config["comparison_dir"]))
    baseline_640 = _load_json(comparison_dir / "baseline-640-val.json")
    ensure_validation_only(baseline_640)
    run_dir = Path(str(config["project"])) / str(config["name"])
    candidate_training = _load_json(run_dir / "run-metadata.json")
    if candidate_training.get("status") != "success":
        raise ExperimentComparisonError("960正式训练没有success记录。")
    baseline_run = Path(str(config["baseline_run"]))
    baseline_training = _load_json(baseline_run / "run-metadata.json")
    baseline_training["best_pt_size_bytes"] = (
        (baseline_run / "weights" / "best.pt").stat().st_size
    )
    candidate_training["best_pt_size_bytes"] = (
        (run_dir / "weights" / "best.pt").stat().st_size
    )
    evaluation_root = run_dir / "evaluation-val-only"
    if evaluation_root.exists():
        raise ExperimentComparisonError(f"candidate val评估已存在：{evaluation_root}")
    best_val = validate_val(
        run_dir / "weights" / "best.pt",
        config,
        960,
        evaluation_root,
        "val-best",
        True,
    )
    last_val = validate_val(
        run_dir / "weights" / "last.pt",
        config,
        960,
        evaluation_root,
        "val-last",
        False,
    )
    candidate_metrics = {
        "experiment_id": config["experiment_id"],
        "validation": {"best": best_val, "last": last_val},
        "candidate_test_accessed": False,
    }
    ensure_validation_only(candidate_metrics)
    _write_json(run_dir / "metrics-val-only.json", candidate_metrics)

    dataset_root = Path(str(config["dataset_yaml"])).parent
    size_index = _load_size_index(comparison_dir)
    baseline_model = YOLO(Path(str(config["baseline_best"])))
    candidate_model = YOLO(run_dir / "weights" / "best.pt")
    baseline_failures = analyze_val_failures(
        baseline_model, dataset_root, 640, config, size_index
    )
    candidate_failures = analyze_val_failures(
        candidate_model, dataset_root, 960, config, size_index
    )
    baseline_failure_path = comparison_dir / "failure-analysis-imgsz640-val-v0.1.csv"
    candidate_failure_path = run_dir / "failure-analysis-imgsz960-v0.1.csv"
    failure_comparison_path = comparison_dir / "failure-comparison-640-vs-960-v0.1.csv"
    for path in (
        baseline_failure_path,
        candidate_failure_path,
        failure_comparison_path,
    ):
        if path.exists():
            raise ExperimentComparisonError(f"失败分析输出已存在：{path}")
    _write_csv(baseline_failure_path, FAILURE_FIELDS, baseline_failures)
    _write_csv(candidate_failure_path, FAILURE_FIELDS, candidate_failures)
    baseline_failure_summary = _failure_summary(baseline_failures, size_index)
    candidate_failure_summary = _failure_summary(candidate_failures, size_index)
    failure_types = sorted(
        set(baseline_failure_summary["failure_type_counts"])
        | set(candidate_failure_summary["failure_type_counts"])
    )
    failure_comparison_rows = []
    for failure_type in failure_types:
        baseline_count = baseline_failure_summary["failure_type_counts"].get(
            failure_type, 0
        )
        candidate_count = candidate_failure_summary["failure_type_counts"].get(
            failure_type, 0
        )
        failure_comparison_rows.append(
            {
                "failure_type": failure_type,
                **metric_change(float(baseline_count), float(candidate_count)),
            }
        )
    _write_csv(
        failure_comparison_path,
        [
            "failure_type",
            "baseline",
            "candidate",
            "absolute_change",
            "relative_change_percent",
        ],
        failure_comparison_rows,
    )
    qualitative = _qualitative_comparison(
        baseline_model,
        candidate_model,
        dataset_root,
        comparison_dir / "qualitative-comparison",
        config,
    )

    comparison_rows = _comparison_rows(
        baseline_640, best_val, baseline_training, candidate_training
    )
    recommendation, reason = _recommendation(baseline_640, best_val)
    comparison = {
        "experiment": "d02-d03-yolo26n-640-vs-960-v0.1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "active_variable": "imgsz",
        "baseline_imgsz": 640,
        "candidate_imgsz": 960,
        "dataset_lock_sha256": EXPECTED_DATASET_LOCK_SHA256,
        "pretrained_weight_sha256": EXPECTED_PRETRAINED_SHA256,
        "candidate_test_accessed": False,
        "peak_gpu_memory_measurement": (
            "torch.cuda.max_memory_allocated including AutoBatch probes; Windows "
            "WDDM may back part of the allocation with shared memory"
        ),
        "metric_changes": comparison_rows,
        "baseline_failure_summary": baseline_failure_summary,
        "candidate_failure_summary": candidate_failure_summary,
        "failure_comparison": failure_comparison_rows,
        "qualitative": qualitative,
        "recommendation": recommendation,
        "recommendation_reason": reason,
    }
    ensure_validation_only(comparison)
    comparison_json = comparison_dir / "comparison.json"
    comparison_csv = comparison_dir / "comparison.csv"
    comparison_md = comparison_dir / "comparison.md"
    if any(path.exists() for path in (comparison_json, comparison_csv, comparison_md)):
        raise ExperimentComparisonError("正式comparison输出已存在。")
    _write_json(comparison_json, comparison)
    _write_csv(
        comparison_csv,
        [
            "metric",
            "baseline",
            "candidate",
            "absolute_change",
            "relative_change_percent",
        ],
        comparison_rows,
    )
    _write_comparison_markdown(comparison_md, comparison)
    failure_summary = {
        "baseline": baseline_failure_summary,
        "candidate": candidate_failure_summary,
        "comparison": failure_comparison_rows,
        "candidate_test_accessed": False,
    }
    artifact = _create_candidate_artifact(
        config_path, config, candidate_metrics, comparison, failure_summary
    )
    result = {
        "validation": candidate_metrics["validation"],
        "comparison": comparison,
        "candidate_artifact": artifact,
        "candidate_test_accessed": False,
    }
    _write_json(run_dir / "evaluation-summary-val-only.json", result)
    return result


def snapshot_tree(
    root: Path,
    key_files: list[Path],
    excluded_suffixes: tuple[str, ...] = (),
) -> dict[str, Any]:
    files = sorted(
        (
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() not in excluded_suffixes
        ),
        key=lambda path: path.relative_to(root).as_posix().lower(),
    )
    digest = hashlib.sha256()
    total_size = 0
    for path in files:
        stat = path.stat()
        total_size += stat.st_size
        relative = path.relative_to(root).as_posix()
        digest.update(
            f"{relative}\0{stat.st_size}\0{stat.st_mtime_ns}\n".encode("utf-8")
        )
    hashes = {
        path.relative_to(root).as_posix(): sha256_file(path)
        for path in key_files
        if path.is_file()
    }
    return {
        "root": str(root),
        "file_count": len(files),
        "total_size_bytes": total_size,
        "metadata_tree_sha256": digest.hexdigest(),
        "key_file_sha256": hashes,
        "excluded_file_suffixes": list(excluded_suffixes),
    }


def write_integrity_snapshot(config_path: Path, kind: str) -> dict[str, Any]:
    config, _ = _contract_gate(config_path)
    if kind not in {"pre", "post"}:
        raise ExperimentComparisonError("snapshot kind必须是pre或post。")
    comparison_dir = Path(str(config["comparison_dir"]))
    comparison_dir.mkdir(parents=True, exist_ok=True)
    output = comparison_dir / f"integrity-{kind}flight.json"
    if output.exists():
        raise ExperimentComparisonError(f"不变性快照已存在：{output}")
    raw_root = Path("E:/JianZhengData/external/raw")
    dataset_root = Path(str(config["dataset_yaml"])).parent
    raw_keys = list(
        (raw_root / "roboflow" / "defect-cardboard-h0kjy" / "extracted").glob(
            "*/_annotations.coco.json"
        )
    )
    dataset_keys = [
        dataset_root / "dataset-lock.json",
        dataset_root / "dataset.yaml",
        dataset_root / "dataset-manifest.csv",
        dataset_root / "conversion-report.json",
        dataset_root / "class-distribution.csv",
    ]
    payload = {
        "kind": kind,
        "generated_at": datetime.now().astimezone().isoformat(),
        "raw": snapshot_tree(raw_root, raw_keys),
        "frozen_dataset": snapshot_tree(
            dataset_root,
            dataset_keys,
            excluded_suffixes=(".cache",),
        ),
    }
    _write_json(output, payload)
    if kind == "post":
        pre = _load_json(comparison_dir / "integrity-preflight.json")
        checks: dict[str, bool] = {}
        for group in ("raw", "frozen_dataset"):
            for field in (
                "file_count",
                "total_size_bytes",
                "metadata_tree_sha256",
                "key_file_sha256",
            ):
                checks[f"{group}.{field}"] = pre[group][field] == payload[group][field]
        invariance = {
            "generated_at": datetime.now().astimezone().isoformat(),
            "checks": checks,
            "raw_unchanged": all(
                value for key, value in checks.items() if key.startswith("raw.")
            ),
            "frozen_dataset_unchanged": all(
                value
                for key, value in checks.items()
                if key.startswith("frozen_dataset.")
            ),
        }
        _write_json(comparison_dir / "integrity-invariance.json", invariance)
        if not all(checks.values()):
            raise ExperimentComparisonError("raw或冻结数据在实验前后发生变化。")
        payload["invariance"] = invariance
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="比较D02/D03 YOLO26n 640与960")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument(
        "--mode",
        choices=("snapshot-pre", "diagnose", "evaluate", "snapshot-post"),
        required=True,
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.mode == "snapshot-pre":
            result = write_integrity_snapshot(args.config, "pre")
        elif args.mode == "diagnose":
            result = run_diagnostics(args.config)
        elif args.mode == "evaluate":
            result = evaluate_candidate(args.config)
        else:
            result = write_integrity_snapshot(args.config, "post")
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ExperimentComparisonError, OSError, ValueError, RuntimeError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
