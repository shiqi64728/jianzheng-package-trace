"""Evaluate, visualize, analyze and release the first D02/D03 baseline."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import torch
from ultralytics import YOLO, __version__ as ultralytics_version

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.training.prepare_d02_d03_dataset import (  # noqa: E402
    CLASS_NAMES,
    DatasetPreparationError,
    sha256_file,
    validate_frozen_dataset,
)
from scripts.training.train_d02_d03_baseline import (  # noqa: E402
    TrainingPipelineError,
    load_experiment_config,
)

EVALUATOR_VERSION = "0.1.0"
FAILURE_FIELDS = [
    "image_relpath",
    "ground_truth_class",
    "predicted_class",
    "confidence",
    "failure_type",
    "notes",
]


class EvaluationPipelineError(RuntimeError):
    """Raised when formal evaluation or release creation fails."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationPipelineError(f"无法读取JSON：{path}：{exc}") from exc
    if not isinstance(data, dict):
        raise EvaluationPipelineError(f"JSON根节点必须是对象：{path}")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _metric_payload(metrics: Any) -> dict[str, Any]:
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
    matrix = np.asarray(metrics.confusion_matrix.matrix)
    if not np.isfinite(matrix).all():
        raise EvaluationPipelineError("混淆矩阵包含NaN/Inf。")
    if any(not math.isfinite(value) for value in overall.values()):
        raise EvaluationPipelineError("验证指标包含NaN/Inf。")
    return {
        "overall": overall,
        "per_class": per_class,
        "confusion_matrix": matrix.tolist(),
        "confusion_matrix_classes": [
            "D02_surface_dent",
            "D03_carton_tear",
            "background",
        ],
    }


def _validate_checkpoint(
    checkpoint: Path,
    config: dict[str, Any],
    split: str,
    project: Path,
    name: str,
    plots: bool,
) -> dict[str, Any]:
    if not checkpoint.is_file():
        raise EvaluationPipelineError(f"checkpoint缺失：{checkpoint}")
    output = project / name
    if output.exists():
        raise EvaluationPipelineError(f"验证输出已存在，拒绝覆盖：{output}")
    model = YOLO(checkpoint)
    if model.task != "detect":
        raise EvaluationPipelineError(f"checkpoint task不是detect：{checkpoint}")
    started = time.perf_counter()
    metrics = model.val(
        data=str(config["dataset_yaml"]),
        split=split,
        imgsz=int(config["imgsz"]),
        batch=int(config.get("evaluation_batch", 8)),
        device=int(config["device"]),
        workers=int(config["workers"]),
        project=str(project),
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
            "split": split,
            "duration_seconds": time.perf_counter() - started,
            "output_dir": str(output),
        }
    )
    return payload


def _stable_sample(
    rows: list[dict[str, str]], count: int, seed: int
) -> list[dict[str, str]]:
    ranked = sorted(
        rows,
        key=lambda row: hashlib.sha256(
            f"{seed}\0{row['external_record_id']}\0{row['target_image_relpath']}".encode()
        ).hexdigest(),
    )
    return ranked[: min(count, len(ranked))]


def _read_yolo_labels(path: Path, width: int, height: int) -> list[dict[str, Any]]:
    labels: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        class_id_text, xc_text, yc_text, w_text, h_text = line.split()
        class_id = int(class_id_text)
        xc, yc, box_w, box_h = map(float, (xc_text, yc_text, w_text, h_text))
        labels.append(
            {
                "class_id": class_id,
                "xyxy": np.array(
                    [
                        (xc - box_w / 2) * width,
                        (yc - box_h / 2) * height,
                        (xc + box_w / 2) * width,
                        (yc + box_h / 2) * height,
                    ],
                    dtype=float,
                ),
                "area_ratio": box_w * box_h,
            }
        )
    return labels


def _draw_ground_truth(image: np.ndarray, labels: list[dict[str, Any]]) -> np.ndarray:
    canvas = image.copy()
    colors = {0: (0, 210, 255), 1: (255, 80, 80)}
    for label in labels:
        x1, y1, x2, y2 = (int(round(value)) for value in label["xyxy"])
        color = colors[label["class_id"]]
        cv2.rectangle(canvas, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            canvas,
            f"GT {CLASS_NAMES[label['class_id']]}",
            (max(0, x1), max(18, y1 - 4)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )
    return canvas


def _iou(first: np.ndarray, second: np.ndarray) -> float:
    x1 = max(float(first[0]), float(second[0]))
    y1 = max(float(first[1]), float(second[1]))
    x2 = min(float(first[2]), float(second[2]))
    y2 = min(float(first[3]), float(second[3]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    first_area = max(0.0, float(first[2] - first[0])) * max(
        0.0, float(first[3] - first[1])
    )
    second_area = max(0.0, float(second[2] - second[0])) * max(
        0.0, float(second[3] - second[1])
    )
    union = first_area + second_area - intersection
    return intersection / union if union > 0 else 0.0


def _failure_rows(
    image_relpath: str,
    labels: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    matched_predictions: set[int] = set()
    failed_gt: list[tuple[dict[str, Any], str]] = []
    for ground_truth in labels:
        candidates = [
            (index, _iou(ground_truth["xyxy"], prediction["xyxy"]))
            for index, prediction in enumerate(predictions)
            if index not in matched_predictions
        ]
        best_index, best_iou = max(
            candidates, key=lambda item: item[1], default=(-1, 0.0)
        )
        gt_name = CLASS_NAMES[ground_truth["class_id"]]
        if best_index >= 0 and best_iou >= 0.5:
            prediction = predictions[best_index]
            matched_predictions.add(best_index)
            if prediction["class_id"] != ground_truth["class_id"]:
                failures.append(
                    {
                        "image_relpath": image_relpath,
                        "ground_truth_class": gt_name,
                        "predicted_class": CLASS_NAMES.get(
                            prediction["class_id"], str(prediction["class_id"])
                        ),
                        "confidence": f"{prediction['confidence']:.8f}",
                        "failure_type": "D02_D03_confusion",
                        "notes": f"IoU={best_iou:.6f}",
                    }
                )
                failed_gt.append((ground_truth, "D02_D03_confusion"))
        elif best_index >= 0 and best_iou >= 0.1:
            prediction = predictions[best_index]
            matched_predictions.add(best_index)
            failures.append(
                {
                    "image_relpath": image_relpath,
                    "ground_truth_class": gt_name,
                    "predicted_class": CLASS_NAMES.get(
                        prediction["class_id"], str(prediction["class_id"])
                    ),
                    "confidence": f"{prediction['confidence']:.8f}",
                    "failure_type": "low_iou",
                    "notes": f"IoU={best_iou:.6f}",
                }
            )
            failed_gt.append((ground_truth, "low_iou"))
        else:
            failures.append(
                {
                    "image_relpath": image_relpath,
                    "ground_truth_class": gt_name,
                    "predicted_class": "",
                    "confidence": "",
                    "failure_type": "missed_detection",
                    "notes": f"best_IoU={best_iou:.6f}",
                }
            )
            failed_gt.append((ground_truth, "missed_detection"))
    for index, prediction in enumerate(predictions):
        if index not in matched_predictions and prediction["confidence"] >= 0.5:
            failures.append(
                {
                    "image_relpath": image_relpath,
                    "ground_truth_class": "",
                    "predicted_class": CLASS_NAMES.get(
                        prediction["class_id"], str(prediction["class_id"])
                    ),
                    "confidence": f"{prediction['confidence']:.8f}",
                    "failure_type": "high_confidence_false_positive",
                    "notes": "confidence>=0.5且未匹配IoU>=0.5真值框",
                }
            )
    for ground_truth, source_failure in failed_gt:
        area = float(ground_truth["area_ratio"])
        size_failure = "small_target_failure" if area < 0.01 else None
        if area > 0.25:
            size_failure = "large_target_failure"
        if size_failure:
            failures.append(
                {
                    "image_relpath": image_relpath,
                    "ground_truth_class": CLASS_NAMES[ground_truth["class_id"]],
                    "predicted_class": "",
                    "confidence": "",
                    "failure_type": size_failure,
                    "notes": f"area_ratio={area:.8f};source_failure={source_failure}",
                }
            )
    return failures


def _qualitative_and_failures(
    model: YOLO,
    dataset_root: Path,
    run_dir: Path,
    split: str,
    imgsz: int,
    device: int,
    seed: int,
    count: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    rows = [
        row
        for row in _read_manifest(dataset_root / "dataset-manifest.csv")
        if row["split"] == split
    ]
    if not rows:
        raise EvaluationPipelineError(f"定性评估split为空：{split}")
    qualitative_root = run_dir / "qualitative"
    if qualitative_root.exists():
        raise EvaluationPipelineError(f"定性目录已存在，拒绝覆盖：{qualitative_root}")
    prediction_dir = qualitative_root / "predictions"
    ground_truth_dir = qualitative_root / "ground-truth"
    prediction_dir.mkdir(parents=True)
    ground_truth_dir.mkdir(parents=True)
    selected = _stable_sample(rows, count, seed)
    selected_paths = [dataset_root / row["target_image_relpath"] for row in selected]
    results = model.predict(
        source=[str(path) for path in selected_paths],
        imgsz=imgsz,
        batch=8,
        device=device,
        conf=0.25,
        iou=0.7,
        verbose=False,
    )
    manifest_rows: list[dict[str, Any]] = []
    for row, image_path, result in zip(selected, selected_paths, results, strict=True):
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise EvaluationPipelineError(f"定性图片无法读取：{image_path}")
        labels = _read_yolo_labels(
            dataset_root / row["target_label_relpath"], image.shape[1], image.shape[0]
        )
        predicted_output = prediction_dir / image_path.name
        gt_output = ground_truth_dir / image_path.name
        if not cv2.imwrite(str(predicted_output), result.plot()):
            raise EvaluationPipelineError(f"无法写入预测图：{predicted_output}")
        if not cv2.imwrite(str(gt_output), _draw_ground_truth(image, labels)):
            raise EvaluationPipelineError(f"无法写入GT图：{gt_output}")
        manifest_rows.append(
            {
                "external_record_id": row["external_record_id"],
                "split": split,
                "image_relpath": row["target_image_relpath"],
                "prediction_relpath": predicted_output.relative_to(run_dir).as_posix(),
                "ground_truth_visualization_relpath": gt_output.relative_to(
                    run_dir
                ).as_posix(),
            }
        )
    _write_csv(
        qualitative_root / "qualitative-manifest.csv",
        [
            "external_record_id",
            "split",
            "image_relpath",
            "prediction_relpath",
            "ground_truth_visualization_relpath",
        ],
        manifest_rows,
    )

    all_paths = [dataset_root / row["target_image_relpath"] for row in rows]
    all_results = model.predict(
        source=[str(path) for path in all_paths],
        imgsz=imgsz,
        batch=8,
        device=device,
        conf=0.001,
        iou=0.7,
        verbose=False,
    )
    failures: list[dict[str, Any]] = []
    for row, image_path, result in zip(rows, all_paths, all_results, strict=True):
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise EvaluationPipelineError(f"失败分析图片无法读取：{image_path}")
        labels = _read_yolo_labels(
            dataset_root / row["target_label_relpath"], image.shape[1], image.shape[0]
        )
        boxes = result.boxes
        predictions = []
        if boxes is not None and len(boxes):
            xyxy = boxes.xyxy.detach().cpu().numpy()
            classes = boxes.cls.detach().cpu().numpy().astype(int)
            confidences = boxes.conf.detach().cpu().numpy()
            predictions = [
                {
                    "xyxy": box,
                    "class_id": int(class_id),
                    "confidence": float(confidence),
                }
                for box, class_id, confidence in zip(
                    xyxy, classes, confidences, strict=True
                )
            ]
        failures.extend(_failure_rows(row["target_image_relpath"], labels, predictions))
    _write_csv(run_dir / "failure-analysis-v0.1.csv", FAILURE_FIELDS, failures)
    return (
        {
            "split": split,
            "seed": seed,
            "requested_count": count,
            "actual_count": len(selected),
            "prediction_images": len(selected),
            "ground_truth_visualizations": len(selected),
        },
        failures,
    )


def _confusion_conclusion(payload: dict[str, Any]) -> dict[str, Any]:
    matrix = np.asarray(payload["confusion_matrix"], dtype=float)
    diagonal = float(np.trace(matrix[:2, :2])) if matrix.shape[0] >= 2 else 0.0
    class_confusion = (
        float(matrix[0, 1] + matrix[1, 0]) if matrix.shape[0] >= 2 else 0.0
    )
    background_errors = (
        float(matrix[2, :2].sum() + matrix[:2, 2].sum())
        if matrix.shape == (3, 3)
        else 0.0
    )
    return {
        "correct_class_assignments": diagonal,
        "d02_d03_cross_confusions": class_confusion,
        "background_related_errors": background_errors,
        "conclusion": (
            "背景相关漏检/假阳性多于D02/D03互相混淆。"
            if background_errors > class_confusion
            else "D02/D03互相混淆不低于背景相关错误。"
        ),
    }


def _create_release(
    config_path: Path,
    config: dict[str, Any],
    run_dir: Path,
    metrics: dict[str, Any],
    release_dir: Path,
) -> dict[str, Any]:
    if release_dir.exists():
        raise EvaluationPipelineError(f"正式release目录已存在，拒绝覆盖：{release_dir}")
    best = run_dir / "weights" / "best.pt"
    lock_path = Path(str(config["dataset_lock"]))
    lock = _load_json(lock_path)
    training = _load_json(run_dir / "run-metadata.json")
    release_dir.mkdir(parents=True)
    shutil.copyfile(best, release_dir / "best.pt")
    shutil.copyfile(lock_path, release_dir / "dataset-lock.json")
    shutil.copyfile(config_path, release_dir / "experiment-config.json")
    best_sha = sha256_file(release_dir / "best.pt")
    if best_sha != sha256_file(best):
        raise EvaluationPipelineError("release best.pt复制后SHA-256不一致。")
    metrics_payload = {
        "model_version": "d02-d03-yolo26n-baseline-v0.1",
        "generated_at": datetime.now().astimezone().isoformat(),
        **metrics,
    }
    _write_json(release_dir / "metrics.json", metrics_payload)
    (release_dir / "weight-sha256.txt").write_text(
        f"{best_sha}  best.pt\n", encoding="utf-8"
    )
    best_val = metrics["validation"]["best"]
    d02 = best_val["per_class"].get("D02_surface_dent", {})
    d03 = best_val["per_class"].get("D03_carton_tear", {})
    test_text = (
        json.dumps(metrics.get("test", {}).get("overall", {}), ensure_ascii=False)
        if metrics.get("test")
        else "本版本没有独立test，当前正式结果仅为validation指标。"
    )
    model_card = f"""# D02/D03 YOLO26n Baseline v0.1

- 模型名称：件证 D02/D03 目标检测基线
- 模型版本：d02-d03-yolo26n-baseline-v0.1
- 基础模型：Ultralytics YOLO26n Detection (`yolo26n.pt`)
- Ultralytics：{ultralytics_version}
- PyTorch：{torch.__version__}
- 训练GPU：{torch.cuda.get_device_name(0)}
- 训练数据版本：{lock["dataset_version"]}
- train/val/test图片：{lock["train_image_count"]}/{lock["val_image_count"]}/{lock["test_image_count"]}
- 类别：0=D02_surface_dent（表面凹陷），1=D03_carton_tear（纸箱破口）
- 训练参数：imgsz={config["imgsz"]}，epochs={config["epochs"]}，batch={training["actual_batch"]}，seed={config["seed"]}，optimizer={config["optimizer"]}，AMP={config["amp"]}
- best epoch：{training["best_epoch"]}
- Precision：{best_val["overall"]["precision"]:.10f}
- Recall：{best_val["overall"]["recall"]:.10f}
- mAP50：{best_val["overall"]["mAP50"]:.10f}
- mAP50-95：{best_val["overall"]["mAP50-95"]:.10f}
- D02指标：{json.dumps(d02, ensure_ascii=False)}
- D03指标：{json.dumps(d03, ensure_ascii=False)}
- test：{test_text}
- 模型SHA-256：`{best_sha}`

## 许可证和来源

训练数据来自 defect-cardboard，治理记录为 CC BY 4.0，使用范围为带署名的非商业竞赛/研究；来源和引用证据保存在外部数据 registry。预训练权重通过已安装 Ultralytics 的官方 `ultralytics/assets` 解析机制取得。

## 已知限制与禁止用途

模型只识别 D02 表面凹陷和 D03 纸箱破口。它不识别 D01、D04、D05、二次封装，不定位真实物流责任节点，也不认定物流责任。公开图片分布、类别不平衡、小目标、背景偏差和未覆盖场景会限制泛化；指标不能替代人工复核。
"""
    (release_dir / "model-card.md").write_text(model_card, encoding="utf-8")
    return {
        "release_dir": str(release_dir),
        "best_pt": str(release_dir / "best.pt"),
        "best_pt_sha256": best_sha,
        "release_files": sorted(path.name for path in release_dir.iterdir()),
    }


def evaluate_and_release(config_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise EvaluationPipelineError("CUDA不可用。")
    dataset_root = Path(str(config["dataset_yaml"])).parent
    validate_frozen_dataset(dataset_root)
    lock = _load_json(Path(str(config["dataset_lock"])))
    run_dir = Path(str(config["project"])) / str(config["name"])
    training = _load_json(run_dir / "run-metadata.json")
    if training.get("status") != "success":
        raise EvaluationPipelineError("正式训练没有success记录。")
    evaluation_root = run_dir / "evaluation"
    release_dir = Path(str(config["release_dir"]))
    if evaluation_root.exists():
        raise EvaluationPipelineError(
            f"正式评估目录已存在，拒绝覆盖：{evaluation_root}"
        )
    if release_dir.exists():
        raise EvaluationPipelineError(f"正式release目录已存在，拒绝覆盖：{release_dir}")
    best = run_dir / "weights" / "best.pt"
    last = run_dir / "weights" / "last.pt"
    best_val = _validate_checkpoint(
        best, config, "val", evaluation_root, "val-best", True
    )
    last_val = _validate_checkpoint(
        last, config, "val", evaluation_root, "val-last", False
    )
    test_metrics = None
    if int(lock.get("test_image_count", 0)) > 0:
        test_metrics = _validate_checkpoint(
            best, config, "test", evaluation_root, "test-best", True
        )
    qualitative_split = "test" if int(lock.get("test_image_count", 0)) > 0 else "val"
    model = YOLO(best)
    qualitative, failures = _qualitative_and_failures(
        model,
        dataset_root,
        run_dir,
        qualitative_split,
        int(config["imgsz"]),
        int(config["device"]),
        int(config["seed"]),
        20,
    )
    failure_counts = dict(Counter(row["failure_type"] for row in failures))
    metrics = {
        "evaluator_version": EVALUATOR_VERSION,
        "validation": {"best": best_val, "last": last_val},
        "test": test_metrics,
        "confusion_conclusion": _confusion_conclusion(best_val),
        "qualitative": qualitative,
        "failure_analysis": {
            "split": qualitative_split,
            "record_count": len(failures),
            "failure_type_counts": failure_counts,
            "csv": str(run_dir / "failure-analysis-v0.1.csv"),
        },
    }
    _write_json(run_dir / "metrics-summary.json", metrics)
    release = _create_release(config_path, config, run_dir, metrics, release_dir)
    result = {**metrics, "release": release}
    _write_json(run_dir / "evaluation-summary.json", result)
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="评估并登记D02/D03 YOLO26n正式基线")
    parser.add_argument("--config", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        config = load_experiment_config(args.config)
        result = evaluate_and_release(args.config, config)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (
        EvaluationPipelineError,
        TrainingPipelineError,
        DatasetPreparationError,
    ) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"[internal-error] {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
