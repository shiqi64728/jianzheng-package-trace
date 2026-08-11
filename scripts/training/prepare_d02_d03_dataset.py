"""Freeze the governed defect-cardboard D02/D03 detection dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

BUILDER_VERSION = "0.1.0"
DATASET_VERSION = "detect-d02-d03-v0.1"
SOURCE_ID = "roboflow-defect-cardboard-h0kjy-v1"
CLASS_IDS = {"dent": 0, "hole": 1}
CLASS_NAMES = {0: "D02_surface_dent", 1: "D03_carton_tear"}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
MANIFEST_FIELDS = [
    "external_record_id",
    "source_id",
    "source_image_relpath",
    "target_image_relpath",
    "target_label_relpath",
    "split",
    "source_sha256",
    "copy_sha256",
    "label_sha256",
    "width",
    "height",
    "d02_bbox_count",
    "d03_bbox_count",
]
EXCLUSION_FIELDS = [
    "external_record_id",
    "source_image_relpath",
    "original_split",
    "original_class",
    "quarantine_status",
    "reason_code",
    "reason_description",
]


class DatasetPreparationError(RuntimeError):
    """Raised when a governed input cannot be frozen safely."""


def sha256_file(path: Path) -> str:
    """Return the streaming SHA-256 of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetPreparationError(f"无法读取JSON：{path}：{exc}") from exc
    if not isinstance(value, dict):
        raise DatasetPreparationError(f"JSON根节点必须是对象：{path}")
    return value


def _read_manifest(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
    except OSError as exc:
        raise DatasetPreparationError(f"无法读取治理manifest：{path}：{exc}") from exc
    if not rows:
        raise DatasetPreparationError("治理manifest为空。")
    return rows


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _safe_external_path(external_root: Path, relative: str) -> Path:
    rel = Path(relative.replace("/", "\\"))
    if rel.is_absolute() or ".." in rel.parts:
        raise DatasetPreparationError(f"外部路径必须是安全相对路径：{relative}")
    root = external_root.resolve()
    path = (root / rel).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise DatasetPreparationError(f"外部路径越界：{relative}") from exc
    return path


def _decode_image(path: Path) -> tuple[int, int, int]:
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise DatasetPreparationError(f"图片不可解码：{path}")
    height, width = image.shape[:2]
    channels = 1 if image.ndim == 2 else int(image.shape[2])
    return width, height, channels


def _parse_annotations(row: dict[str, str]) -> list[dict[str, Any]]:
    try:
        annotations = json.loads(row.get("annotation_records_json", ""))
    except json.JSONDecodeError as exc:
        raise DatasetPreparationError(
            f"标注引用JSON无效：{row.get('external_record_id', '')}"
        ) from exc
    if not isinstance(annotations, list):
        raise DatasetPreparationError("annotation_records_json必须是数组。")
    return annotations


def _classes(annotations: list[dict[str, Any]]) -> set[str]:
    return {
        str(annotation.get("original_class", "")).strip() for annotation in annotations
    }


def _validate_bbox(
    bbox: Any, width: int, height: int, record_id: str, annotation_id: Any
) -> tuple[float, float, float, float]:
    if not isinstance(bbox, list) or len(bbox) != 4:
        raise DatasetPreparationError(
            f"bbox格式非法：record={record_id} annotation={annotation_id}"
        )
    try:
        x_min, y_min, box_width, box_height = (float(value) for value in bbox)
    except (TypeError, ValueError) as exc:
        raise DatasetPreparationError(
            f"bbox包含非数值：record={record_id} annotation={annotation_id}"
        ) from exc
    tolerance = 1e-6
    if x_min < -tolerance or y_min < -tolerance or box_width <= 0 or box_height <= 0:
        raise DatasetPreparationError(
            f"bbox坐标或宽高非法：record={record_id} annotation={annotation_id} bbox={bbox}"
        )
    if x_min + box_width > width + tolerance or y_min + box_height > height + tolerance:
        raise DatasetPreparationError(
            f"bbox超出图片：record={record_id} annotation={annotation_id} bbox={bbox} image={width}x{height}"
        )
    return x_min, y_min, box_width, box_height


def coco_to_yolo(
    bbox: Any, width: int, height: int, record_id: str = "", annotation_id: Any = ""
) -> tuple[float, float, float, float]:
    """Strictly convert COCO xywh pixels to normalized YOLO xywh."""
    x_min, y_min, box_width, box_height = _validate_bbox(
        bbox, width, height, record_id, annotation_id
    )
    values = (
        (x_min + box_width / 2) / width,
        (y_min + box_height / 2) / height,
        box_width / width,
        box_height / height,
    )
    if not (
        0 <= values[0] <= 1
        and 0 <= values[1] <= 1
        and 0 < values[2] <= 1
        and 0 < values[3] <= 1
    ):
        raise DatasetPreparationError(f"YOLO归一化结果非法：{values}")
    return values


def _source_identity(path: str) -> str:
    stem = Path(path).stem
    return re.sub(r"\.rf\.[^.]+$", "", stem, flags=re.IGNORECASE).casefold()


def _content_tree_sha256(root: Path, paths: list[Path]) -> str:
    records = [
        f"{path.relative_to(root).as_posix()}\t{sha256_file(path)}"
        for path in sorted(
            paths, key=lambda item: item.relative_to(root).as_posix().casefold()
        )
    ]
    return hashlib.sha256("\n".join(records).encode("utf-8")).hexdigest()


def _validate_license(license_report: Path) -> None:
    report = _load_json(license_report)
    matches = [
        item
        for item in report.get("sources", [])
        if isinstance(item, dict) and item.get("source_id") == SOURCE_ID
    ]
    if len(matches) != 1 or matches[0].get("audit_status") != "passed":
        raise DatasetPreparationError(
            "defect-cardboard许可证审计不是passed，停止构建。"
        )
    if matches[0].get("blocking_issue"):
        raise DatasetPreparationError("defect-cardboard许可证审计存在blocking issue。")


def _write_dataset_yaml(path: Path, final_root: Path, has_test: bool) -> None:
    lines = [
        f"path: {final_root.as_posix()}",
        "train: images/train",
        "val: images/val",
    ]
    if has_test:
        lines.append("test: images/test")
    lines.extend(
        [
            "names:",
            "  0: D02_surface_dent",
            "  1: D03_carton_tear",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def _exclusion(
    row: dict[str, str], reason_code: str, reason_description: str
) -> dict[str, str]:
    return {
        "external_record_id": row.get("external_record_id", ""),
        "source_image_relpath": row.get("original_image_relpath", ""),
        "original_split": row.get("original_split", ""),
        "original_class": row.get("original_class", ""),
        "quarantine_status": row.get("quarantine_status", ""),
        "reason_code": reason_code,
        "reason_description": reason_description,
    }


def build_dataset(
    external_root: Path,
    manifest_path: Path,
    license_report: Path,
    class_mapping_path: Path,
    output_dir: Path,
    source_commit: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build an immutable dataset directory without modifying external raw data."""
    if output_dir.exists():
        raise DatasetPreparationError(f"冻结数据集目录已存在，拒绝覆盖：{output_dir}")
    _validate_license(license_report)
    mapping = _load_json(class_mapping_path)
    mapping_source = mapping.get("sources", {}).get(SOURCE_ID, {})
    if (
        mapping_source.get("classes", {}).get("dent", {}).get("mapped_project_class")
        != "D02"
    ):
        raise DatasetPreparationError("类别映射中dent不是D02。")
    if (
        mapping_source.get("classes", {}).get("hole", {}).get("mapped_project_class")
        != "D03"
    ):
        raise DatasetPreparationError("类别映射中hole不是D03。")

    rows = _read_manifest(manifest_path)
    temp_dir = output_dir.with_name(f".{output_dir.name}.building-{uuid.uuid4().hex}")
    if temp_dir.exists():
        raise DatasetPreparationError(f"临时构建目录异常存在：{temp_dir}")
    included: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    split_images: Counter[str] = Counter()
    class_counts: Counter[str] = Counter()
    seen_sha: dict[str, str] = {}
    seen_identity: dict[str, str] = {}
    split_alias = {"train": "train", "valid": "val", "val": "val", "test": "test"}
    renamed_to_output = False

    try:
        for split in ("train", "val", "test"):
            (temp_dir / "images" / split).mkdir(parents=True, exist_ok=True)
            (temp_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

        for row in rows:
            if row.get("source_id") != SOURCE_ID:
                raise DatasetPreparationError(
                    "治理manifest混入了非defect-cardboard来源。"
                )
            annotations = _parse_annotations(row)
            annotation_classes = _classes(annotations)
            if "dirt" in annotation_classes:
                excluded.append(
                    _exclusion(
                        row,
                        "DIRT_PRESENT",
                        "图片包含未批准dirt标注；整张图片从D02/D03 baseline排除。",
                    )
                )
                continue
            if row.get("quarantine_status") != "accepted":
                excluded.append(
                    _exclusion(
                        row,
                        "QUARANTINE_NOT_ACCEPTED",
                        f"治理状态为{row.get('quarantine_status', '') or 'empty'}。",
                    )
                )
                continue
            if row.get("mapped_project_status") != "direct":
                excluded.append(
                    _exclusion(row, "MAPPING_NOT_DIRECT", "项目类别映射不是direct。")
                )
                continue
            if (
                not annotations
                or not annotation_classes
                or not annotation_classes <= set(CLASS_IDS)
            ):
                excluded.append(
                    _exclusion(
                        row,
                        "NO_DIRECT_D02_D03_ANNOTATION",
                        "没有可用于D02/D03的直接bbox标注或存在未知类别。",
                    )
                )
                continue

            original_split = row.get("original_split", "")
            if original_split not in split_alias:
                raise DatasetPreparationError(f"未知split：{original_split}")
            split = split_alias[original_split]
            source_relative = row.get("original_image_relpath", "")
            source = _safe_external_path(external_root, source_relative)
            if not source.is_file():
                raise DatasetPreparationError(f"源图片缺失：{source_relative}")
            actual_sha = sha256_file(source)
            governed_sha = row.get("sha256", "").lower()
            if governed_sha and actual_sha != governed_sha:
                raise DatasetPreparationError(
                    f"源图片哈希与治理manifest不一致：{source_relative}"
                )
            if actual_sha in seen_sha:
                raise DatasetPreparationError(
                    f"发现精确重复图片：{source_relative} 与 {seen_sha[actual_sha]}"
                )
            source_identity = _source_identity(source_relative)
            previous_split = seen_identity.get(source_identity)
            if previous_split and previous_split != split:
                raise DatasetPreparationError(
                    f"发现相同源图片跨split：{source_identity}：{previous_split}/{split}"
                )

            width, height, _channels = _decode_image(source)
            governed_width = int(row.get("width", 0) or 0)
            governed_height = int(row.get("height", 0) or 0)
            if (width, height) != (governed_width, governed_height):
                raise DatasetPreparationError(
                    f"图片尺寸与治理manifest不一致：{source_relative} actual={width}x{height} governed={governed_width}x{governed_height}"
                )
            label_lines: list[str] = []
            per_image: Counter[str] = Counter()
            for annotation in annotations:
                original_class = str(annotation.get("original_class", ""))
                if original_class not in CLASS_IDS:
                    raise DatasetPreparationError(
                        f"accepted记录包含未知类别：{original_class}：{source_relative}"
                    )
                normalized = coco_to_yolo(
                    annotation.get("bbox"),
                    width,
                    height,
                    row.get("external_record_id", ""),
                    annotation.get("original_annotation_id", ""),
                )
                label_lines.append(
                    f"{CLASS_IDS[original_class]} "
                    + " ".join(f"{value:.10f}" for value in normalized)
                )
                per_image[original_class] += 1
                class_counts[original_class] += 1

            target_image = temp_dir / "images" / split / source.name
            target_label = temp_dir / "labels" / split / f"{source.stem}.txt"
            if target_image.exists() or target_label.exists():
                raise DatasetPreparationError(f"目标文件名冲突：{source.name}")
            shutil.copyfile(source, target_image)
            copy_sha = sha256_file(target_image)
            if copy_sha != actual_sha:
                raise DatasetPreparationError(f"复制后SHA-256不一致：{source_relative}")
            target_label.write_text("\n".join(label_lines) + "\n", encoding="utf-8")
            label_sha = sha256_file(target_label)
            seen_sha[actual_sha] = source_relative
            seen_identity[source_identity] = split
            split_images[split] += 1
            included.append(
                {
                    "external_record_id": row.get("external_record_id", ""),
                    "source_id": SOURCE_ID,
                    "source_image_relpath": source_relative.replace("\\", "/"),
                    "target_image_relpath": target_image.relative_to(
                        temp_dir
                    ).as_posix(),
                    "target_label_relpath": target_label.relative_to(
                        temp_dir
                    ).as_posix(),
                    "split": split,
                    "source_sha256": actual_sha,
                    "copy_sha256": copy_sha,
                    "label_sha256": label_sha,
                    "width": width,
                    "height": height,
                    "d02_bbox_count": per_image["dent"],
                    "d03_bbox_count": per_image["hole"],
                }
            )

        if not included or not split_images["train"] or not split_images["val"]:
            raise DatasetPreparationError("冻结数据集缺少train或val样本。")
        _write_dataset_yaml(
            temp_dir / "dataset.yaml", output_dir, bool(split_images["test"])
        )
        _write_csv(temp_dir / "dataset-manifest.csv", MANIFEST_FIELDS, included)
        _write_csv(temp_dir / "exclusion-report.csv", EXCLUSION_FIELDS, excluded)
        distribution_rows = []
        for split in ("train", "val", "test"):
            split_rows = [item for item in included if item["split"] == split]
            distribution_rows.append(
                {
                    "split": split,
                    "image_count": len(split_rows),
                    "d02_bbox_count": sum(
                        int(item["d02_bbox_count"]) for item in split_rows
                    ),
                    "d03_bbox_count": sum(
                        int(item["d03_bbox_count"]) for item in split_rows
                    ),
                }
            )
        _write_csv(
            temp_dir / "class-distribution.csv",
            ["split", "image_count", "d02_bbox_count", "d03_bbox_count"],
            distribution_rows,
        )
        image_paths = [
            path
            for path in (temp_dir / "images").rglob("*")
            if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
        ]
        label_paths = list((temp_dir / "labels").rglob("*.txt"))
        created = created_at or datetime.now().astimezone().isoformat()
        source_manifest_sha = sha256_file(manifest_path)
        lock = {
            "dataset_version": DATASET_VERSION,
            "created_at": created,
            "source_id": SOURCE_ID,
            "source_dataset": "defect-cardboard",
            "source_manifest_sha256": source_manifest_sha,
            "class_mapping_version": mapping.get("mapping_version", ""),
            "included_image_count": len(included),
            "excluded_image_count": len(excluded),
            "included_annotation_count": sum(class_counts.values()),
            "train_image_count": split_images["train"],
            "val_image_count": split_images["val"],
            "test_image_count": split_images["test"],
            "class_counts": {
                "D02_surface_dent": class_counts["dent"],
                "D03_carton_tear": class_counts["hole"],
            },
            "image_tree_sha256": _content_tree_sha256(temp_dir, image_paths),
            "label_tree_sha256": _content_tree_sha256(temp_dir, label_paths),
            "split_policy": "preserve_source_train_valid_test; valid renamed val; no random reassignment",
            "exclusion_rules": [
                "exclude entire image when any dirt annotation is present",
                "require quarantine_status=accepted",
                "require mapped_project_status=direct",
                "allow only dent/hole bbox annotations",
                "reject invalid/out-of-bounds bbox",
                "reject exact duplicates and cross-split source identity",
            ],
            "license_status": "passed",
            "source_commit": source_commit,
            "builder_version": BUILDER_VERSION,
        }
        (temp_dir / "dataset-lock.json").write_text(
            json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        reason_counts = Counter(item["reason_code"] for item in excluded)
        report = {
            "builder_version": BUILDER_VERSION,
            "dataset_version": DATASET_VERSION,
            "source_manifest": str(manifest_path),
            "source_manifest_sha256": source_manifest_sha,
            "original_candidate_image_count": len(rows),
            "included_image_count": len(included),
            "excluded_image_count": len(excluded),
            "excluded_reason_counts": dict(sorted(reason_counts.items())),
            "included_annotation_count": sum(class_counts.values()),
            "split_image_counts": dict(split_images),
            "class_counts": dict(class_counts),
            "copy_sha256_mismatch_count": 0,
        }
        (temp_dir / "conversion-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        readme = f"""# {DATASET_VERSION}

由 `{SOURCE_ID}` 的治理 manifest 冻结得到，只包含 D02 表面凹陷和 D03 纸箱破口。

- 图片：{len(included)}
- 排除：{len(excluded)}
- D02 bbox：{class_counts["dent"]}
- D03 bbox：{class_counts["hole"]}
- split：train={split_images["train"]}，val={split_images["val"]}，test={split_images["test"]}
- split策略：保留原 train/valid/test，仅将 valid 目录名规范为 val。
- 所有含 dirt 的图片整图排除；图片按原始字节复制并逐文件验证 SHA-256。
- 本目录是冻结训练派生数据，不是 raw；禁止覆盖，修改样本必须创建新版本。
"""
        (temp_dir / "README.md").write_text(readme, encoding="utf-8")
        temp_dir.replace(output_dir)
        renamed_to_output = True
        validation = validate_frozen_dataset(output_dir)
        (output_dir / "dataset-validation-report.json").write_text(
            json.dumps(validation, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {"lock": lock, "report": report, "validation": validation}
    except (OSError, ValueError, DatasetPreparationError):
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        if renamed_to_output and output_dir.exists():
            shutil.rmtree(output_dir)
        raise


def _read_dataset_manifest(dataset_root: Path) -> list[dict[str, str]]:
    with (dataset_root / "dataset-manifest.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream:
        return list(csv.DictReader(stream))


def validate_frozen_dataset(dataset_root: Path) -> dict[str, Any]:
    """Validate image/label pairing, hashes, classes, coordinates and split isolation."""
    lock = _load_json(dataset_root / "dataset-lock.json")
    rows = _read_dataset_manifest(dataset_root)
    if len(rows) != int(lock.get("included_image_count", -1)):
        raise DatasetPreparationError("dataset-manifest行数与dataset-lock不一致。")
    hashes: dict[str, tuple[str, str]] = {}
    identities: dict[str, str] = {}
    class_counts: Counter[int] = Counter()
    split_counts: Counter[str] = Counter()
    image_paths: list[Path] = []
    label_paths: list[Path] = []
    for row in rows:
        split = row["split"]
        image_path = dataset_root / Path(row["target_image_relpath"])
        label_path = dataset_root / Path(row["target_label_relpath"])
        if not image_path.is_file() or not label_path.is_file():
            raise DatasetPreparationError(
                f"images和labels不对应：{image_path} / {label_path}"
            )
        if image_path.is_symlink() or label_path.is_symlink():
            raise DatasetPreparationError("冻结数据集不得包含符号链接。")
        width, height, _channels = _decode_image(image_path)
        if (width, height) != (int(row["width"]), int(row["height"])):
            raise DatasetPreparationError(f"冻结图片尺寸不一致：{image_path}")
        image_sha = sha256_file(image_path)
        if image_sha != row["source_sha256"] or image_sha != row["copy_sha256"]:
            raise DatasetPreparationError(f"冻结图片SHA-256不一致：{image_path}")
        if sha256_file(label_path) != row["label_sha256"]:
            raise DatasetPreparationError(f"标签SHA-256不一致：{label_path}")
        previous = hashes.get(image_sha)
        if previous:
            raise DatasetPreparationError(
                f"冻结数据集存在重复图片：{image_path} / {previous[0]}"
            )
        hashes[image_sha] = (str(image_path), split)
        identity = _source_identity(row["source_image_relpath"])
        previous_split = identities.get(identity)
        if previous_split and previous_split != split:
            raise DatasetPreparationError(f"相同源图片跨split：{identity}")
        identities[identity] = split
        lines = [
            line.strip() for line in label_path.read_text(encoding="utf-8").splitlines()
        ]
        if not lines or any(not line for line in lines):
            raise DatasetPreparationError(f"标签为空或包含空行：{label_path}")
        for line in lines:
            parts = line.split()
            if len(parts) != 5:
                raise DatasetPreparationError(f"YOLO标签列数非法：{label_path}：{line}")
            try:
                class_id = int(parts[0])
                x_center, y_center, box_width, box_height = map(float, parts[1:])
            except ValueError as exc:
                raise DatasetPreparationError(
                    f"YOLO标签包含非数值：{label_path}"
                ) from exc
            if class_id not in CLASS_NAMES:
                raise DatasetPreparationError(f"YOLO class id非法：{class_id}")
            if not (
                0 <= x_center <= 1
                and 0 <= y_center <= 1
                and 0 < box_width <= 1
                and 0 < box_height <= 1
            ):
                raise DatasetPreparationError(f"YOLO坐标范围非法：{label_path}：{line}")
            class_counts[class_id] += 1
        split_counts[split] += 1
        image_paths.append(image_path)
        label_paths.append(label_path)
    actual_image_tree = _content_tree_sha256(dataset_root, image_paths)
    actual_label_tree = _content_tree_sha256(dataset_root, label_paths)
    if actual_image_tree != lock.get("image_tree_sha256"):
        raise DatasetPreparationError("image tree SHA-256与dataset-lock不一致。")
    if actual_label_tree != lock.get("label_tree_sha256"):
        raise DatasetPreparationError("label tree SHA-256与dataset-lock不一致。")
    yaml_text = (dataset_root / "dataset.yaml").read_text(encoding="utf-8")
    for expected in (
        f"path: {dataset_root.as_posix()}",
        "train: images/train",
        "val: images/val",
        "0: D02_surface_dent",
        "1: D03_carton_tear",
    ):
        if expected not in yaml_text:
            raise DatasetPreparationError(f"dataset.yaml缺少：{expected}")
    if split_counts["test"] and "test: images/test" not in yaml_text:
        raise DatasetPreparationError("存在test图片但dataset.yaml未声明test。")
    return {
        "valid": True,
        "dataset_version": lock.get("dataset_version"),
        "checked_images": len(rows),
        "checked_labels": len(rows),
        "empty_label_files": 0,
        "missing_pairs": 0,
        "duplicate_images": 0,
        "cross_split_duplicates": 0,
        "split_image_counts": dict(split_counts),
        "class_counts": {
            "D02_surface_dent": class_counts[0],
            "D03_carton_tear": class_counts[1],
        },
        "image_tree_sha256": actual_image_tree,
        "label_tree_sha256": actual_label_tree,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="冻结D02/D03 YOLO Detect数据集")
    parser.add_argument("--external-root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--license-report", type=Path)
    parser.add_argument("--class-mapping", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--source-commit")
    parser.add_argument("--created-at")
    parser.add_argument("--validate-only", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        if args.validate_only:
            result = validate_frozen_dataset(args.validate_only)
        else:
            required = {
                "--external-root": args.external_root,
                "--manifest": args.manifest,
                "--license-report": args.license_report,
                "--class-mapping": args.class_mapping,
                "--output-dir": args.output_dir,
                "--source-commit": args.source_commit,
            }
            missing = [name for name, value in required.items() if not value]
            if missing:
                raise DatasetPreparationError(f"缺少参数：{', '.join(missing)}")
            result = build_dataset(
                args.external_root,
                args.manifest,
                args.license_report,
                args.class_mapping,
                args.output_dir,
                args.source_commit,
                args.created_at,
            )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except DatasetPreparationError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"[internal-error] {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
