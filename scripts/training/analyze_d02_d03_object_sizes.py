"""Describe frozen D02/D03 ground-truth object sizes without model predictions."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

CLASS_NAMES = {0: "D02_surface_dent", 1: "D03_carton_tear"}
QUARTILE_NAMES = (
    "smallest_quartile",
    "q2",
    "q3",
    "largest_quartile",
)
CSV_FIELDS = [
    "bbox_id",
    "image_relpath",
    "label_relpath",
    "split",
    "label_index",
    "class_id",
    "class_name",
    "normalized_width",
    "normalized_height",
    "normalized_area",
    "native_width_px",
    "native_height_px",
    "native_area_px",
    "projected_width_640",
    "projected_height_640",
    "projected_area_640",
    "projected_width_960",
    "projected_height_960",
    "projected_area_960",
    "overall_quartile",
]


class ObjectSizeAnalysisError(RuntimeError):
    """Raised when frozen labels cannot be described safely."""


def _read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise ObjectSizeAnalysisError(f"manifest为空：{path}")
    return rows


def quantile_linear(values: Iterable[float], probability: float) -> float:
    """Return a deterministic linear-interpolated quantile."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        raise ObjectSizeAnalysisError("不能对空序列计算分位数。")
    if not 0 <= probability <= 1:
        raise ObjectSizeAnalysisError("分位概率必须位于[0, 1]。")
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def quartile_thresholds(values: Iterable[float]) -> dict[str, float]:
    values_list = list(values)
    return {
        "q25": quantile_linear(values_list, 0.25),
        "q50": quantile_linear(values_list, 0.50),
        "q75": quantile_linear(values_list, 0.75),
    }


def assign_quartile(area: float, thresholds: dict[str, float]) -> str:
    if area <= thresholds["q25"]:
        return "smallest_quartile"
    if area <= thresholds["q50"]:
        return "q2"
    if area <= thresholds["q75"]:
        return "q3"
    return "largest_quartile"


def projected_dimensions(
    normalized_width: float,
    normalized_height: float,
    native_image_width: int,
    native_image_height: int,
    imgsz: int,
) -> tuple[float, float, float]:
    """Approximate Ultralytics letterbox-scaled bbox dimensions before padding."""
    scale = imgsz / max(native_image_width, native_image_height)
    width = normalized_width * native_image_width * scale
    height = normalized_height * native_image_height * scale
    return width, height, width * height


def collect_bbox_records(dataset_root: Path) -> list[dict[str, Any]]:
    manifest = _read_manifest(dataset_root / "dataset-manifest.csv")
    records: list[dict[str, Any]] = []
    for image_row in sorted(
        manifest,
        key=lambda row: (row["split"], row["target_image_relpath"]),
    ):
        width = int(image_row["width"])
        height = int(image_row["height"])
        label_path = dataset_root / image_row["target_label_relpath"]
        lines = label_path.read_text(encoding="utf-8").splitlines()
        for label_index, line in enumerate(lines):
            parts = line.split()
            if len(parts) != 5:
                raise ObjectSizeAnalysisError(f"YOLO标签列数非法：{label_path}")
            class_id = int(parts[0])
            if class_id not in CLASS_NAMES:
                raise ObjectSizeAnalysisError(f"未知class id：{class_id}")
            _, _, normalized_width, normalized_height = map(float, parts[1:])
            normalized_area = normalized_width * normalized_height
            if not 0 < normalized_area <= 1:
                raise ObjectSizeAnalysisError(f"非法归一化面积：{label_path}")
            native_width = normalized_width * width
            native_height = normalized_height * height
            projected_640 = projected_dimensions(
                normalized_width, normalized_height, width, height, 640
            )
            projected_960 = projected_dimensions(
                normalized_width, normalized_height, width, height, 960
            )
            image_relpath = image_row["target_image_relpath"]
            records.append(
                {
                    "bbox_id": f"{image_relpath}#{label_index}",
                    "image_relpath": image_relpath,
                    "label_relpath": image_row["target_label_relpath"],
                    "split": image_row["split"],
                    "label_index": label_index,
                    "class_id": class_id,
                    "class_name": CLASS_NAMES[class_id],
                    "normalized_width": normalized_width,
                    "normalized_height": normalized_height,
                    "normalized_area": normalized_area,
                    "native_width_px": native_width,
                    "native_height_px": native_height,
                    "native_area_px": native_width * native_height,
                    "projected_width_640": projected_640[0],
                    "projected_height_640": projected_640[1],
                    "projected_area_640": projected_640[2],
                    "projected_width_960": projected_960[0],
                    "projected_height_960": projected_960[1],
                    "projected_area_960": projected_960[2],
                }
            )
    if not records:
        raise ObjectSizeAnalysisError("冻结数据集没有bbox。")
    thresholds = quartile_thresholds(record["normalized_area"] for record in records)
    for record in records:
        record["overall_quartile"] = assign_quartile(
            record["normalized_area"], thresholds
        )
    return records


def _metric_summary(records: list[dict[str, Any]], field: str) -> dict[str, float]:
    values = [float(record[field]) for record in records]
    thresholds = quartile_thresholds(values)
    return {
        "min": min(values),
        "q25": thresholds["q25"],
        "q50": thresholds["q50"],
        "q75": thresholds["q75"],
        "max": max(values),
        "mean": sum(values) / len(values),
    }


def _quartile_summary(records: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for quartile in QUARTILE_NAMES:
        selected = [
            record for record in records if record["overall_quartile"] == quartile
        ]
        class_counts = Counter(record["class_name"] for record in selected)
        count = len(selected)
        result[quartile] = {
            "bbox_count": count,
            "class_counts": dict(class_counts),
            "class_proportions": {
                class_name: class_counts.get(class_name, 0) / count if count else 0.0
                for class_name in CLASS_NAMES.values()
            },
            "projected_640": {
                "mean_width": sum(r["projected_width_640"] for r in selected) / count
                if count
                else 0.0,
                "mean_height": sum(r["projected_height_640"] for r in selected) / count
                if count
                else 0.0,
                "mean_area": sum(r["projected_area_640"] for r in selected) / count
                if count
                else 0.0,
            },
            "projected_960": {
                "mean_width": sum(r["projected_width_960"] for r in selected) / count
                if count
                else 0.0,
                "mean_height": sum(r["projected_height_960"] for r in selected) / count
                if count
                else 0.0,
                "mean_area": sum(r["projected_area_960"] for r in selected) / count
                if count
                else 0.0,
            },
        }
    return result


def build_distribution(records: list[dict[str, Any]]) -> dict[str, Any]:
    overall_thresholds = quartile_thresholds(
        record["normalized_area"] for record in records
    )
    split_counts = Counter(record["split"] for record in records)
    result: dict[str, Any] = {
        "bbox_count": len(records),
        "split_bbox_counts": dict(split_counts),
        "overall": {
            "normalized_width": _metric_summary(records, "normalized_width"),
            "normalized_height": _metric_summary(records, "normalized_height"),
            "normalized_area": _metric_summary(records, "normalized_area"),
            "quartile_thresholds_normalized_area": overall_thresholds,
            "quartiles": _quartile_summary(records),
        },
        "classes": {},
        "notes": (
            "Quartile assignment uses overall normalized-area Q25/Q50/Q75; "
            "projected sizes approximate letterbox scaling before padding."
        ),
    }
    for class_id, class_name in CLASS_NAMES.items():
        selected = [record for record in records if record["class_id"] == class_id]
        result["classes"][class_name] = {
            "bbox_count": len(selected),
            "normalized_width": _metric_summary(selected, "normalized_width"),
            "normalized_height": _metric_summary(selected, "normalized_height"),
            "normalized_area": _metric_summary(selected, "normalized_area"),
            "own_quartile_thresholds_normalized_area": quartile_thresholds(
                record["normalized_area"] for record in selected
            ),
            "counts_by_overall_quartile": dict(
                Counter(record["overall_quartile"] for record in selected)
            ),
        }
    return result


def write_analysis(dataset_root: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "object-size-distribution-v0.1.json"
    csv_path = output_dir / "object-size-distribution-v0.1.csv"
    if json_path.exists() or csv_path.exists():
        raise ObjectSizeAnalysisError("目标尺寸分析输出已存在，拒绝覆盖。")
    records = collect_bbox_records(dataset_root)
    distribution = build_distribution(records)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(records)
    json_path.write_text(
        json.dumps(distribution, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return distribution


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="分析D02/D03冻结GT目标尺寸")
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        result = write_analysis(args.dataset_root, args.output_dir)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ObjectSizeAnalysisError, OSError, ValueError) as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
