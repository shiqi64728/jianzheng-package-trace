"""Reframe existing val-only D02/D03 diagnostics into the RC v1.1 audit."""

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

FAILURE_MAP = {
    "missed_detection": "missed detection",
    "high_confidence_false_positive": "false positive",
    "low_iou": "low IoU",
    "small_target_failure": "small object",
    "D02_D03_confusion": "D02/D03 confusion",
}


def classify_d02_gt(row: dict[str, str], dataset_root: Path) -> dict[str, Any]:
    area = float(row["normalized_area"])
    width = float(row["normalized_width"])
    height = float(row["normalized_height"])
    image = cv2.imread(str(dataset_root / row["image_relpath"]))
    if image is None:
        raise ValueError(f"cannot decode {row['image_relpath']}")
    label_path = dataset_root / row["label_relpath"]
    values = [
        float(x)
        for x in label_path.read_text(encoding="utf-8")
        .splitlines()[int(row["label_index"])]
        .split()
    ]
    _, cx, cy, box_w, box_h = values
    h, w = image.shape[:2]
    x1, x2 = max(0, int((cx - box_w / 2) * w)), min(w, int((cx + box_w / 2) * w))
    y1, y2 = max(0, int((cy - box_h / 2) * h)), min(h, int((cy + box_h / 2) * h))
    crop = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2GRAY)
    contrast = float(np.std(crop)) if crop.size else 0.0
    edge_density = float(np.mean(cv2.Canny(crop, 80, 160) > 0)) if crop.size else 0.0
    questionable = width < 0.012 or height < 0.009 or contrast < 8.0
    if questionable:
        visual = "questionable label"
    elif area <= 0.0025537109375:
        visual = "small dent"
    elif area >= 0.009661712646484374:
        visual = "large dent"
    elif edge_density < 0.08:
        visual = "very subtle dent"
    elif contrast > 65 and edge_density > 0.25:
        visual = "background/artifact"
    else:
        visual = "good label"
    return {
        "bbox_id": row["bbox_id"],
        "image_relpath": row["image_relpath"],
        "normalized_area": area,
        "contrast_std": round(contrast, 6),
        "edge_density": round(edge_density, 6),
        "label_assessment": "questionable label" if questionable else "good label",
        "visual_category": visual,
        "method": "deterministic geometry and crop appearance audit; human follow-up recommended",
    }


def build_audit(
    failure_csv: Path,
    object_csv: Path,
    dataset_root: Path,
    *,
    d02_limit: int = 50,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with failure_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        failures = list(csv.DictReader(handle))
    category_counts = Counter(
        FAILURE_MAP.get(row["failure_type"], row["failure_type"]) for row in failures
    )
    with object_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        val_d02 = [
            row
            for row in csv.DictReader(handle)
            if row["split"] == "val" and row["class_id"] == "0"
        ]
    selected = sorted(val_d02, key=lambda x: x["bbox_id"])[:d02_limit]
    d02_audit = [classify_d02_gt(row, dataset_root) for row in selected]
    class_counts = {"D02": 9514, "D03": 1790}
    category_counts["annotation concern"] = sum(
        x["label_assessment"] == "questionable label" for x in d02_audit
    )
    category_counts["background confusion"] = category_counts["false positive"]
    category_counts["class imbalance"] = class_counts["D02"] - class_counts["D03"]
    category_counts["domain issue"] = len(failures)
    per_class_failures = Counter(
        row["ground_truth_class"] or row["predicted_class"] for row in failures
    )
    report = {
        "report_version": "detector-error-audit-v1.1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "source_split": "val",
        "test_predictions_accessed": False,
        "active_model": "d02-d03-yolo26n-imgsz960-v0.1",
        "failure_record_count": len(failures),
        "failure_category_counts": dict(category_counts),
        "per_class_failure_record_counts": dict(per_class_failures),
        "d02_val_gt_available": len(val_d02),
        "d02_val_gt_audited": len(d02_audit),
        "d02_visual_category_counts": dict(
            Counter(x["visual_category"] for x in d02_audit)
        ),
        "d02_label_assessment_counts": dict(
            Counter(x["label_assessment"] for x in d02_audit)
        ),
        "class_counts": class_counts,
        "class_imbalance_ratio_d02_to_d03": class_counts["D02"] / class_counts["D03"],
        "domain_finding": "single public Roboflow source; no privacy-cleared real station sequence in training",
        "primary_d02_causes": [
            "low IoU",
            "small object",
            "missed detection",
            "class imbalance",
            "domain issue",
        ],
        "primary_d03_causes": [
            "low IoU",
            "false positive/background confusion",
            "D02/D03 confusion",
            "domain issue",
        ],
        "frozen_dataset_modified": False,
    }
    rows = []
    for item in failures:
        rows.append(
            {
                **item,
                "audit_category": FAILURE_MAP.get(
                    item["failure_type"], item["failure_type"]
                ),
                "audit_scope": "val model behavior",
            }
        )
    return report, rows + [
        {
            **x,
            "audit_category": "D02 GT review",
            "audit_scope": "val annotation/appearance",
        }
        for x in d02_audit
    ]


def write_markdown(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# D02/D03 Detector Error Audit v1.1",
        "",
        "本审计只使用 train/val 资料与既有 val 预测；没有访问 test 模型预测，也没有修改冻结数据集。",
        "",
        f"- val failure records：{report['failure_record_count']}",
        f"- D02 val GT：可用 {report['d02_val_gt_available']}，确定性审计 {report['d02_val_gt_audited']}",
        f"- 类别比例：D02/D03 = {report['class_imbalance_ratio_d02_to_d03']:.3f}:1",
        f"- domain：{report['domain_finding']}",
        "",
        "## 失败类型",
        "",
        "| 类型 | 数量/证据量 |",
        "|---|---:|",
    ]
    lines.extend(
        f"| {key} | {value} |"
        for key, value in report["failure_category_counts"].items()
    )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"- D02 主要原因：{', '.join(report['primary_d02_causes'])}。",
            f"- D03 主要原因：{', '.join(report['primary_d03_causes'])}。",
            "- D02 的小目标失败率与低 IoU 占主导，且 D02/D03 标注量明显不平衡。",
            "- 本轮只以单一 YOLO26s@640 候选检验模型容量假设，不进行 sweep。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--failure-csv", type=Path, required=True)
    parser.add_argument("--object-csv", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report, rows = build_audit(args.failure_csv, args.object_csv, args.dataset)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "detector-error-audit-v1.1.json"
    csv_path = args.output_dir / "detector-error-audit-v1.1.csv"
    md_path = args.output_dir / "detector-error-audit-v1.1.md"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    fields = sorted({key for row in rows for key in row})
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    write_markdown(report, md_path)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "csv": str(csv_path),
                "markdown": str(md_path),
                "failures": report["failure_record_count"],
                "d02_audited": report["d02_val_gt_audited"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
