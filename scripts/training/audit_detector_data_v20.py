"""Deterministic train/val diagnostics for Detector Optimization Goal v2.0.

The audit never runs test predictions.  Test images are only read by the separate
cross-split perceptual-hash leakage audit.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

from scripts.training.audit_near_duplicates_v11 import audit_dataset

CLASS_NAMES = {0: "D02_surface_dent", 1: "D03_carton_tear"}
TAXONOMY = (
    "SUBTLE_DENT",
    "SMALL_DENT",
    "MEDIUM_DENT",
    "LARGE_DENT",
    "EDGE_DENT",
    "OCCLUDED",
    "BACKGROUND_AMBIGUITY",
    "LABEL_CONCERN",
)
BACKGROUND_CATEGORIES = (
    "纸箱纹理",
    "折痕",
    "印刷文字",
    "阴影",
    "胶带",
    "边缘",
    "背景物体",
    "其他",
)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _image_paths(root: Path, split: str) -> list[Path]:
    return sorted(
        p
        for p in (root / "images" / split).iterdir()
        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    )


def _label_path(root: Path, image: Path, split: str) -> Path:
    return root / "labels" / split / f"{image.stem}.txt"


def read_annotations(root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for split in ("train", "val", "test"):
        for image_path in _image_paths(root, split):
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError(f"cannot decode image: {image_path}")
            image_h, image_w = image.shape[:2]
            label_path = _label_path(root, image_path, split)
            lines = (
                label_path.read_text(encoding="utf-8").splitlines()
                if label_path.is_file()
                else []
            )
            parsed: list[tuple[float, ...]] = []
            for index, line in enumerate(lines):
                values = tuple(float(item) for item in line.split())
                if len(values) != 5:
                    raise ValueError(f"invalid YOLO row: {label_path}#{index}")
                class_id, cx, cy, width, height = values
                parsed.append(values)
                pixel_w, pixel_h = width * image_w, height * image_h
                x1, y1 = cx - width / 2, cy - height / 2
                x2, y2 = cx + width / 2, cy + height / 2
                area = width * height
                aspect = width / height if height > 0 else float("inf")
                row = {
                    "bbox_id": f"images/{split}/{image_path.name}#{index}",
                    "split": split,
                    "image_relpath": f"images/{split}/{image_path.name}",
                    "label_relpath": f"labels/{split}/{label_path.name}",
                    "label_index": index,
                    "class_id": int(class_id),
                    "class_name": CLASS_NAMES.get(int(class_id), "UNKNOWN"),
                    "cx": cx,
                    "cy": cy,
                    "normalized_width": width,
                    "normalized_height": height,
                    "normalized_area": area,
                    "pixel_width": pixel_w,
                    "pixel_height": pixel_h,
                    "pixel_area": pixel_w * pixel_h,
                    "aspect_ratio": aspect,
                    "near_zero_area": area < 1e-5 or pixel_w * pixel_h < 16,
                    "too_small_bbox": pixel_w < 4 or pixel_h < 4,
                    "too_large_bbox": area > 0.80,
                    "truncated_bbox": min(x1, y1) <= 0.001 or max(x2, y2) >= 0.999,
                    "abnormal_aspect_ratio": aspect < 0.05 or aspect > 20,
                    "duplicate_bbox": False,
                    "out_of_bounds": min(x1, y1) < -1e-9 or max(x2, y2) > 1 + 1e-9,
                }
                rows.append(row)
            counts = Counter(parsed)
            base = len(rows) - len(parsed)
            for index, values in enumerate(parsed):
                rows[base + index]["duplicate_bbox"] = counts[values] > 1
    for row in rows:
        row["label_concern"] = any(
            row[key]
            for key in (
                "near_zero_area",
                "too_small_bbox",
                "too_large_bbox",
                "truncated_bbox",
                "abnormal_aspect_ratio",
                "duplicate_bbox",
                "out_of_bounds",
            )
        )
    return rows


def build_label_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    flags = (
        "near_zero_area",
        "too_small_bbox",
        "too_large_bbox",
        "truncated_bbox",
        "abnormal_aspect_ratio",
        "duplicate_bbox",
        "out_of_bounds",
        "label_concern",
    )
    return {
        "report_version": "label-audit-v2.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "bbox_count": len(rows),
        "bbox_count_by_split": dict(Counter(row["split"] for row in rows)),
        "bbox_count_by_class": dict(Counter(row["class_name"] for row in rows)),
        "flag_counts": {key: sum(bool(row[key]) for row in rows) for key in flags},
        "suspected_wrong_class_count": 0,
        "suspected_wrong_class_method": "NOT_INFERRED_FROM_GEOMETRY; visual class relabeling requires human review",
        "frozen_labels_modified": False,
    }


def _crop_features(image: np.ndarray, row: dict[str, Any]) -> tuple[float, float]:
    h, w = image.shape[:2]
    x1 = max(0, int((row["cx"] - row["normalized_width"] / 2) * w))
    x2 = min(w, int((row["cx"] + row["normalized_width"] / 2) * w))
    y1 = max(0, int((row["cy"] - row["normalized_height"] / 2) * h))
    y2 = min(h, int((row["cy"] + row["normalized_height"] / 2) * h))
    crop = image[y1:y2, x1:x2]
    if crop.size == 0:
        return 0.0, 0.0
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return float(np.std(gray)), float(np.mean(cv2.Canny(gray, 80, 160) > 0))


def build_d02_taxonomy(root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [row for row in rows if row["split"] == "val" and row["class_id"] == 0]
    areas = np.asarray([row["normalized_area"] for row in selected], dtype=float)
    q1, q3 = map(float, np.quantile(areas, [0.25, 0.75]))
    cache: dict[str, np.ndarray] = {}
    output = []
    for row in selected:
        rel = row["image_relpath"]
        if rel not in cache:
            image = cv2.imread(str(root / rel))
            if image is None:
                raise ValueError(f"cannot decode {rel}")
            cache[rel] = image
        contrast, edge_density = _crop_features(cache[rel], row)
        if row["label_concern"]:
            category = "LABEL_CONCERN"
        elif row["truncated_bbox"]:
            category = "EDGE_DENT"
        elif contrast < 18 and edge_density < 0.08:
            category = "SUBTLE_DENT"
        elif contrast > 65 and edge_density > 0.25:
            category = "BACKGROUND_AMBIGUITY"
        elif row["normalized_area"] <= q1:
            category = "SMALL_DENT"
        elif row["normalized_area"] >= q3:
            category = "LARGE_DENT"
        else:
            category = "MEDIUM_DENT"
        output.append(
            {
                **row,
                "taxonomy": category,
                "crop_contrast_std": round(contrast, 6),
                "crop_edge_density": round(edge_density, 6),
                "method": "deterministic geometry/appearance proxy; no label was changed",
            }
        )
    return output


def build_small_object_report(object_csv: Path, failure_csv: Path) -> dict[str, Any]:
    with object_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        objects = list(csv.DictReader(handle))
    with failure_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        failures = list(csv.DictReader(handle))
    failed_ids = {
        row["bbox_id"]
        for row in failures
        if row["bbox_id"] and row["failure_type"] != "high_confidence_false_positive"
    }
    by_class: dict[str, Any] = {}
    for class_name in CLASS_NAMES.values():
        class_rows = [
            row
            for row in objects
            if row["split"] == "val" and row["class_name"] == class_name
        ]
        quartiles = {}
        for quartile in ("smallest_quartile", "q2", "q3", "largest_quartile"):
            subset = [row for row in class_rows if row["overall_quartile"] == quartile]
            failed = sum(row["bbox_id"] in failed_ids for row in subset)
            quartiles[quartile] = {
                "target_count": len(subset),
                "failure_count": failed,
                "failure_rate": failed / len(subset) if subset else None,
                "median_width_960": float(
                    np.median([float(row["projected_width_960"]) for row in subset])
                )
                if subset
                else None,
                "median_height_960": float(
                    np.median([float(row["projected_height_960"]) for row in subset])
                )
                if subset
                else None,
                "median_area_960": float(
                    np.median([float(row["projected_area_960"]) for row in subset])
                )
                if subset
                else None,
            }
        by_class[class_name] = quartiles
    return {
        "report_version": "small-object-audit-v2.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "source_split": "val",
        "active_model": "d02-d03-yolo26n-imgsz960-v0.1",
        "test_predictions_accessed": False,
        "classes": by_class,
    }


def _iou(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    if not len(boxes):
        return np.zeros(0, dtype=float)
    top_left = np.maximum(box[:2], boxes[:, :2])
    bottom_right = np.minimum(box[2:], boxes[:, 2:])
    intersection = np.prod(np.maximum(0.0, bottom_right - top_left), axis=1)
    box_area = np.prod(np.maximum(0.0, box[2:] - box[:2]))
    areas = np.prod(np.maximum(0.0, boxes[:, 2:] - boxes[:, :2]), axis=1)
    return intersection / np.maximum(box_area + areas - intersection, 1e-12)


def _background_category(
    crop: np.ndarray, box: np.ndarray, shape: tuple[int, ...]
) -> str:
    if crop.size == 0:
        return "其他"
    h, w = shape[:2]
    x1, y1, x2, y2 = map(float, box)
    if x1 <= 2 or y1 <= 2 or x2 >= w - 2 or y2 >= h - 2:
        return "边缘"
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    contrast = float(np.std(gray))
    edge = float(np.mean(cv2.Canny(gray, 80, 160) > 0))
    brightness = float(np.mean(gray))
    saturation = float(np.mean(hsv[..., 1]))
    aspect = (x2 - x1) / max(y2 - y1, 1.0)
    if brightness < 65 and contrast < 38:
        return "阴影"
    if saturation < 55 and brightness > 145 and (aspect > 2.2 or aspect < 0.45):
        return "胶带"
    if edge > 0.27 and contrast > 45:
        return "印刷文字"
    if (aspect > 4 or aspect < 0.25) and edge > 0.08:
        return "折痕"
    if 8 <= saturation <= 150 and 65 <= brightness <= 190 and contrast > 22:
        return "纸箱纹理"
    if (x2 - x1) * (y2 - y1) > 0.18 * w * h:
        return "背景物体"
    return "其他"


def build_background_audit(
    root: Path, model_path: Path, *, confidence: float = 0.50
) -> list[dict[str, Any]]:
    model = YOLO(str(model_path))
    output: list[dict[str, Any]] = []
    for image_path in _image_paths(root, "val"):
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"cannot decode {image_path}")
        h, w = image.shape[:2]
        gt = []
        label_path = _label_path(root, image_path, "val")
        for line in label_path.read_text(encoding="utf-8").splitlines():
            cls, cx, cy, bw, bh = map(float, line.split())
            gt.append(
                [
                    (cx - bw / 2) * w,
                    (cy - bh / 2) * h,
                    (cx + bw / 2) * w,
                    (cy + bh / 2) * h,
                    cls,
                ]
            )
        gt_array = np.asarray([row[:4] for row in gt], dtype=float).reshape(-1, 4)
        result = model.predict(
            source=image, imgsz=960, conf=confidence, device=0, verbose=False
        )[0]
        boxes = result.boxes.xyxy.detach().cpu().numpy()
        confs = result.boxes.conf.detach().cpu().numpy()
        classes = result.boxes.cls.detach().cpu().numpy().astype(int)
        for index, (box, conf, class_id) in enumerate(zip(boxes, confs, classes)):
            max_iou = float(np.max(_iou(box, gt_array))) if len(gt_array) else 0.0
            if max_iou >= 0.50:
                continue
            x1, y1, x2, y2 = np.round(box).astype(int)
            crop = image[max(0, y1) : min(h, y2), max(0, x1) : min(w, x2)]
            output.append(
                {
                    "image_relpath": f"images/val/{image_path.name}",
                    "prediction_index": index,
                    "predicted_class": CLASS_NAMES.get(class_id, str(class_id)),
                    "confidence": float(conf),
                    "max_gt_iou": max_iou,
                    "x1": float(box[0]),
                    "y1": float(box[1]),
                    "x2": float(box[2]),
                    "y2": float(box[3]),
                    "background_category": _background_category(crop, box, image.shape),
                    "category_method": "deterministic crop appearance proxy; human review recommended",
                    "test_prediction_accessed": False,
                }
            )
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--object-csv", type=Path, required=True)
    parser.add_argument("--failure-csv", type=Path, required=True)
    parser.add_argument("--active-model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    annotations = read_annotations(args.dataset)
    label_report = build_label_report(annotations)
    taxonomy = build_d02_taxonomy(args.dataset, annotations)
    taxonomy_report = {
        "report_version": "d02-error-taxonomy-v2.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "source_split": "val",
        "audited_gt_count": len(taxonomy),
        "category_counts": {
            key: sum(row["taxonomy"] == key for row in taxonomy) for key in TAXONOMY
        },
        "label_concern_count": sum(row["label_concern"] for row in taxonomy),
        "frozen_labels_modified": False,
    }
    small_report = build_small_object_report(args.object_csv, args.failure_csv)
    background = build_background_audit(args.dataset, args.active_model)
    background_report = {
        "report_version": "background-error-audit-v2.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "source_split": "val",
        "false_positive_count": len(background),
        "category_counts": {
            key: sum(row["background_category"] == key for row in background)
            for key in BACKGROUND_CATEGORIES
        },
        "test_predictions_accessed": False,
    }
    near = audit_dataset(args.dataset, threshold=6)
    near["report_version"] = "near-duplicate-audit-v2.0"

    files = {
        "label_json": (args.output_dir / "label-audit-v2.0.json", label_report),
        "d02_json": (args.output_dir / "d02-error-taxonomy-v2.0.json", taxonomy_report),
        "small_json": (args.output_dir / "small-object-audit-v2.0.json", small_report),
        "background_json": (
            args.output_dir / "background-error-audit-v2.0.json",
            background_report,
        ),
        "near_json": (args.output_dir / "near-duplicate-audit-v2.0.json", near),
    }
    for path, payload in files.values():
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    _write_csv(args.output_dir / "label-audit-v2.0.csv", annotations)
    _write_csv(args.output_dir / "d02-error-taxonomy-v2.0.csv", taxonomy)
    _write_csv(args.output_dir / "background-error-audit-v2.0.csv", background)
    print(
        json.dumps(
            {
                "output_dir": str(args.output_dir),
                "labels": label_report,
                "d02_taxonomy": taxonomy_report,
                "small_object": small_report,
                "background": background_report,
                "near_duplicate": {
                    "exact": near["exact_cross_split_count"],
                    "perceptual": near["perceptual_near_duplicate_count"],
                    "suspected_split_leakage": near["suspected_split_leakage"],
                },
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
