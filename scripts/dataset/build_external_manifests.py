"""Build traceable external manifests without copying or modifying source data."""

from __future__ import annotations

import argparse
import json
import re
import sys
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.dataset.external_data_common import (
    GovernanceUsageError,
    IMAGE_SUFFIXES,
    image_metadata,
    load_json,
    load_schema_fields,
    read_csv,
    relative_posix,
    sha256_file,
    source_base_record,
    stable_id,
    utc_now,
    write_csv_bom,
    write_json,
)

EXIT_SUCCESS = 0
EXIT_DATA_ERROR = 1
EXIT_USAGE_ERROR = 2
EXIT_INTERNAL_ERROR = 3
BUILDER_VERSION = "0.1.0"


def _bool(value: bool) -> str:
    return "true" if value else "false"


def _source(mapping: dict[str, Any], source_id: str) -> dict[str, Any]:
    sources = mapping.get("sources")
    if not isinstance(sources, dict) or not isinstance(sources.get(source_id), dict):
        raise GovernanceUsageError(f"类别映射缺少来源：{source_id}")
    return sources[source_id]


def _image_fields(path: Path, external_root: Path) -> dict[str, Any]:
    width, height, channels = image_metadata(path)
    return {
        "original_image_relpath": relative_posix(path, external_root),
        "sha256": sha256_file(path),
        "file_size_bytes": path.stat().st_size,
        "width": width,
        "height": height,
        "channels": channels,
    }


def build_defect_cardboard(
    external_root: Path,
    fields: list[str],
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build one image row with stable nested references for every COCO annotation."""

    source_id = "roboflow-defect-cardboard-h0kjy-v1"
    extracted = external_root / source["local_path"] / "extracted"
    rows: list[dict[str, Any]] = []
    classes = source.get("classes", {})
    for split in ("train", "valid", "test"):
        annotation_path = extracted / split / "_annotations.coco.json"
        document = load_json(annotation_path)
        images = document.get("images")
        annotations = document.get("annotations")
        categories = document.get("categories")
        if (
            not isinstance(images, list)
            or not isinstance(annotations, list)
            or not isinstance(categories, list)
        ):
            raise GovernanceUsageError(f"COCO结构无效：{annotation_path}")
        category_names = {
            item.get("id"): item.get("name", "")
            for item in categories
            if isinstance(item, dict)
        }
        by_image: dict[Any, list[dict[str, Any]]] = defaultdict(list)
        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue
            name = category_names.get(annotation.get("category_id"), "")
            bbox = annotation.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4:
                raise GovernanceUsageError(
                    f"COCO bbox无效：{annotation_path} annotation={annotation.get('id')}"
                )
            by_image[annotation.get("image_id")].append(
                {
                    "annotation_ref": f"{source_id}:{split}:annotation:{annotation.get('id')}",
                    "original_annotation_id": annotation.get("id"),
                    "original_image_id": annotation.get("image_id"),
                    "original_class": name,
                    "bbox": bbox,
                    "iscrowd": annotation.get("iscrowd", 0),
                }
            )
        for image in sorted(images, key=lambda item: str(item.get("file_name", ""))):
            image_path = extracted / split / str(image.get("file_name", ""))
            if not image_path.is_file():
                raise FileNotFoundError(f"COCO引用图片缺失：{image_path}")
            nested = sorted(
                by_image.get(image.get("id"), []),
                key=lambda item: str(item["original_annotation_id"]),
            )
            original_classes = sorted(
                {item["original_class"] for item in nested if item["original_class"]}
            )
            mappings = [classes[name] for name in original_classes if name in classes]
            unknown = sorted(set(original_classes) - set(classes))
            candidate = any(
                item.get("mapped_project_status") == "candidate" for item in mappings
            )
            manual = candidate or bool(unknown) or not nested
            status = "candidate" if candidate else "direct"
            if unknown or not nested:
                status = "unmapped"
            mapped_classes = sorted(
                {
                    item.get("mapped_project_class", "")
                    for item in mappings
                    if item.get("mapped_project_class")
                }
            )
            row = source_base_record(fields, source_id, source)
            row.update(_image_fields(image_path, external_root))
            row.update(
                {
                    "external_record_id": stable_id(
                        "EXT", source_id, relative_posix(image_path, external_root)
                    ),
                    "original_split": split,
                    "original_annotation_relpath": relative_posix(
                        annotation_path, external_root
                    ),
                    "original_annotation_type": "bbox",
                    "original_class": "|".join(original_classes),
                    "mapped_project_status": status,
                    "mapped_project_class": "|".join(mapped_classes),
                    "project_task": "damage_detection",
                    "requires_manual_review": _bool(manual),
                    "quarantine_status": "review_required" if manual else "accepted",
                    "quarantine_reason": "AMBIGUOUS_D04_DIRT"
                    if candidate
                    else ("UNKNOWN_DAMAGE_CLASS" if unknown or not nested else ""),
                    "original_image_id": image.get("id", ""),
                    "annotation_records_json": json.dumps(
                        nested, ensure_ascii=False, separators=(",", ":")
                    ),
                    "notes": "保留原始bbox；未生成polygon。",
                }
            )
            rows.append(row)
    return rows


def build_damaged_box(
    external_root: Path,
    fields: list[str],
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build classification records and exact duplicate groups without deleting files."""

    source_id = "roboflow-damaged-box-detection-v1"
    extracted = external_root / source["local_path"] / "extracted"
    candidates: list[tuple[str, str, Path, dict[str, Any]]] = []
    hashes: dict[str, list[tuple[str, str, Path]]] = defaultdict(list)
    for split in ("train", "valid", "test"):
        split_root = extracted / split
        if not split_root.is_dir():
            raise FileNotFoundError(f"分类split目录缺失：{split_root}")
        for class_dir in sorted(path for path in split_root.iterdir() if path.is_dir()):
            class_name = class_dir.name
            mapping = source.get("classes", {}).get(class_name)
            if not isinstance(mapping, dict):
                raise GovernanceUsageError(f"二分类映射缺少类别：{class_name}")
            for image_path in sorted(
                path
                for path in class_dir.rglob("*")
                if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
            ):
                metadata = _image_fields(image_path, external_root)
                candidates.append((split, class_name, image_path, metadata))
                hashes[str(metadata["sha256"])].append((split, class_name, image_path))
    duplicate_ids = {
        digest: stable_id("DUP", digest, length=16)
        for digest, members in hashes.items()
        if len(members) > 1
    }
    rows: list[dict[str, Any]] = []
    for split, class_name, image_path, metadata in candidates:
        mapping = source["classes"][class_name]
        row = source_base_record(fields, source_id, source)
        row.update(metadata)
        row.update(
            {
                "external_record_id": stable_id(
                    "EXT", source_id, relative_posix(image_path, external_root)
                ),
                "original_split": split,
                "original_annotation_type": "classification",
                "original_class": class_name,
                "mapped_project_status": mapping["mapped_project_status"],
                "mapped_project_class": mapping["mapped_project_class"],
                "project_task": mapping["project_task"],
                "requires_manual_review": _bool(
                    bool(mapping.get("requires_manual_review", False))
                ),
                "quarantine_status": "accepted",
                "duplicate_group_id": duplicate_ids.get(str(metadata["sha256"]), ""),
                "parent_or_augmented_from": "",
                "notes": "README确认旋转增强，但缺少可靠父图映射；不得当作独立物理包裹。",
            }
        )
        rows.append(row)
    return rows


def _tampar_split(parts: tuple[str, ...]) -> str:
    if not parts:
        return ""
    if parts[0] in {"test", "validation"}:
        return parts[0]
    if (
        parts[0] == "unlabeled"
        and len(parts) > 1
        and parts[1] in {"test", "validation"}
    ):
        return parts[1]
    return "shared"


def _tampar_operation(parts: tuple[str, ...], name: str) -> str:
    if name.endswith("_uvmap_gt.png"):
        return "uvmap_gt"
    if name.endswith("_uvmap_pred.png"):
        return "uvmap_pred"
    if parts and parts[0] == "uvmaps":
        return "canonical_uvmap"
    if "base" in parts:
        return "base"
    if parts and parts[0] == "unlabeled":
        return parts[2] if len(parts) > 3 else "unlabeled"
    return parts[1] if len(parts) > 1 else "unknown"


def _parcel_key(name: str) -> str:
    match = re.match(r"^(id_\d+)_", name)
    return match.group(1) if match else ""


def _capture_number(name: str) -> int:
    match = re.search(r"_(\d{8})_(\d{6})", name)
    return int("".join(match.groups())) if match else 0


def build_tampar(
    external_root: Path,
    fields: list[str],
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build conservative TAMPAR records with probable/unresolved pairing only."""

    source_id = "zenodo-tampar-10057090"
    root = external_root / source["local_path"] / "extracted" / "tampar"
    coco_annotations: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for coco_name in ("tampar_test.json", "tampar_validation.json"):
        coco_path = root / coco_name
        document = load_json(coco_path)
        images = {
            item.get("id"): str(item.get("file_name", "")).replace("\\", "/")
            for item in document.get("images", [])
            if isinstance(item, dict)
        }
        categories = {
            item.get("id"): item.get("name", "")
            for item in document.get("categories", [])
            if isinstance(item, dict)
        }
        for annotation in document.get("annotations", []):
            if (
                not isinstance(annotation, dict)
                or annotation.get("image_id") not in images
            ):
                continue
            coco_annotations[images[annotation["image_id"]]].append(
                {
                    "annotation_ref": f"{source_id}:{coco_name}:annotation:{annotation.get('id')}",
                    "original_annotation_id": annotation.get("id"),
                    "original_image_id": annotation.get("image_id"),
                    "original_class": categories.get(annotation.get("category_id"), ""),
                    "bbox": annotation.get("bbox"),
                    "segmentation": annotation.get("segmentation"),
                    "keypoints": annotation.get("keypoints"),
                }
            )

    image_paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    bases: dict[tuple[str, str], list[Path]] = defaultdict(list)
    for path in image_paths:
        rel = path.relative_to(root)
        parts = rel.parts
        if path.suffix.lower() in {".jpg", ".jpeg"} and "base" in parts:
            bases[(_tampar_split(parts), _parcel_key(path.name))].append(path)
    for values in bases.values():
        values.sort(key=lambda path: (_capture_number(path.name), path.name))

    rows: list[dict[str, Any]] = []
    for image_path in image_paths:
        rel = image_path.relative_to(root)
        rel_value = rel.as_posix()
        parts = rel.parts
        split = _tampar_split(parts)
        operation = _tampar_operation(parts, image_path.name)
        parcel = _parcel_key(image_path.name)
        nested = sorted(
            coco_annotations.get(rel_value, []),
            key=lambda item: str(item["original_annotation_id"]),
        )
        is_photo = image_path.suffix.lower() in {".jpg", ".jpeg"}
        is_base = is_photo and operation == "base"
        is_tampered = is_photo and not is_base
        reference = ""
        pairing = ""
        pair_id = ""
        quarantine = "accepted"
        reason = ""
        if is_tampered:
            references = bases.get((split, parcel), [])
            if references:
                target_number = _capture_number(image_path.name)
                selected = min(
                    references,
                    key=lambda path: (
                        abs(_capture_number(path.name) - target_number),
                        path.name,
                    ),
                )
                reference = relative_posix(selected, external_root)
                pairing = "probable"
                quarantine = "review_required"
                reason = "TAMPAR_PAIR_PROBABLE"
            else:
                pairing = "unresolved"
                quarantine = "review_required"
                reason = "TAMPAR_PAIR_UNRESOLVED"
            pair_id = stable_id(
                "PAIR", source_id, relative_posix(image_path, external_root), reference
            )

        parent = ""
        if operation in {"uvmap_gt", "uvmap_pred"}:
            suffix = "_uvmap_gt.png" if operation == "uvmap_gt" else "_uvmap_pred.png"
            candidate = image_path.with_name(
                image_path.name.removesuffix(suffix) + ".jpg"
            )
            if candidate.is_file():
                parent = relative_posix(candidate, external_root)

        mapping = source["default_mapping"]
        project_task = (
            "surface_normalization" if not is_photo else mapping["project_task"]
        )
        annotation_type = "polygon" if nested else ("pair" if is_tampered else "none")
        original_classes = sorted(
            {item["original_class"] for item in nested if item["original_class"]}
        )
        row = source_base_record(fields, source_id, source)
        row.update(_image_fields(image_path, external_root))
        row.update(
            {
                "external_record_id": stable_id(
                    "EXT", source_id, relative_posix(image_path, external_root)
                ),
                "original_split": split,
                "original_annotation_relpath": relative_posix(
                    root
                    / (
                        "tampar_test.json"
                        if split == "test"
                        else "tampar_validation.json"
                    ),
                    external_root,
                )
                if nested and split in {"test", "validation"}
                else "",
                "original_annotation_type": annotation_type,
                "original_class": "|".join(original_classes)
                if original_classes
                else operation,
                "mapped_project_status": mapping["mapped_project_status"],
                "mapped_project_class": "",
                "project_task": project_task,
                "requires_manual_review": _bool(is_tampered),
                "quarantine_status": quarantine,
                "quarantine_reason": reason,
                "annotation_records_json": json.dumps(
                    nested, ensure_ascii=False, separators=(",", ":")
                )
                if nested
                else "",
                "pair_id": pair_id,
                "reference_image_relpath": reference,
                "tampered_image_relpath": relative_posix(image_path, external_root)
                if is_tampered
                else "",
                "original_operation_type": operation,
                "pairing_confidence": pairing,
                "parent_or_augmented_from": parent,
                "notes": "配对仅依据目录、parcel id和时间邻近规则；未伪造N1/N2或物流节点。"
                if is_tampered
                else "TAMPAR原始几何/归一化资产。",
            }
        )
        rows.append(row)
    return rows


def build_public_stats(
    external_root: Path,
    fields: list[str],
    source: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build a non-image statistics source manifest from retained public evidence."""

    source_id = "spb-public-statistics"
    csv_root = external_root / source["local_path"] / "parsed-csv"
    _, articles = read_csv(csv_root / "spb-articles-2024-2026.csv")
    _, indicators = read_csv(csv_root / "spb-indicators-2024-2026.csv")
    article_by_url = {row.get("source_url", ""): row for row in articles}
    rows: list[dict[str, Any]] = []
    for item in indicators:
        article = article_by_url.get(item.get("source_url", ""), {})
        raw_file = article.get("raw_html_file", "")
        raw_path = (
            external_root / source["local_path"] / "raw-html" / raw_file
            if raw_file
            else None
        )
        row = source_base_record(fields, source_id, source)
        row.update(
            {
                "external_record_id": stable_id(
                    "STAT",
                    source_id,
                    item.get("source_url", ""),
                    item.get("stat_period", ""),
                    item.get("indicator", ""),
                    item.get("value", ""),
                ),
                "source_url": item.get("source_url", source.get("source_url", "")),
                "original_split": "not_applicable",
                "original_annotation_relpath": relative_posix(raw_path, external_root)
                if raw_path and raw_path.is_file()
                else "",
                "original_annotation_type": "statistics",
                "original_class": "indicator",
                "mapped_project_status": "unmapped",
                "mapped_project_class": "",
                "project_task": "industry_statistics",
                "requires_manual_review": "true",
                "quarantine_status": "blocked",
                "quarantine_reason": "LICENSE_MISSING",
                "file_size_bytes": raw_path.stat().st_size
                if raw_path and raw_path.is_file()
                else "",
                "article_title": item.get("article_title", ""),
                "publication_date": item.get("publication_date", ""),
                "stat_period": item.get("stat_period", ""),
                "indicator": item.get("indicator", ""),
                "value": item.get("value", ""),
                "unit": item.get("unit", ""),
                "year_on_year": " ".join(
                    part
                    for part in (
                        item.get("year_on_year_direction", ""),
                        item.get("year_on_year_percent", ""),
                    )
                    if part
                ),
                "retrieved_at": item.get("retrieved_at", ""),
                "raw_html_sha256": item.get("raw_html_sha256", ""),
                "sha256": item.get("raw_html_sha256", ""),
                "notes": "公开统计仅用于行业背景；本地未保存独立使用许可，禁止进入图像训练。",
            }
        )
        rows.append(row)
    return rows


def ensure_output_boundary(path: Path, external_root: Path, allowed_top: str) -> None:
    resolved = path.resolve()
    allowed = (external_root / allowed_top).resolve()
    try:
        resolved.relative_to(allowed)
    except ValueError as exc:
        raise GovernanceUsageError(f"输出必须位于{allowed_top}目录：{path}") from exc


def build_all(
    external_root: Path,
    external_schema: Path,
    class_mapping: Path,
    output_dir: Path,
    report_path: Path,
) -> dict[str, Any]:
    """Build all four manifests and an image-level annotation-preservation report."""

    fields = load_schema_fields(external_schema)
    mapping = load_json(class_mapping)
    ensure_output_boundary(output_dir, external_root, "converted")
    ensure_output_boundary(report_path, external_root, "reports")
    outputs: dict[str, list[dict[str, Any]]] = {
        "defect-cardboard-v0.1.csv": build_defect_cardboard(
            external_root,
            fields,
            _source(mapping, "roboflow-defect-cardboard-h0kjy-v1"),
        ),
        "damaged-box-detection-v0.1.csv": build_damaged_box(
            external_root, fields, _source(mapping, "roboflow-damaged-box-detection-v1")
        ),
        "tampar-pairs-v0.1.csv": build_tampar(
            external_root, fields, _source(mapping, "zenodo-tampar-10057090")
        ),
        "public-stats-v0.1.csv": build_public_stats(
            external_root, fields, _source(mapping, "spb-public-statistics")
        ),
    }
    summaries: dict[str, Any] = {}
    for name, rows in outputs.items():
        destination = output_dir / name
        write_csv_bom(destination, fields, rows)
        annotation_count = 0
        for row in rows:
            raw = row.get("annotation_records_json")
            if raw:
                annotation_count += len(json.loads(str(raw)))
        summaries[name] = {
            "records": len(rows),
            "annotation_records": annotation_count,
            "output": relative_posix(destination, external_root),
            "quarantine_status": dict(
                Counter(str(row.get("quarantine_status", "")) for row in rows)
            ),
            "pairing_confidence": dict(
                Counter(
                    str(row.get("pairing_confidence", ""))
                    for row in rows
                    if row.get("pairing_confidence")
                )
            ),
        }
    report = {
        "builder_version": BUILDER_VERSION,
        "generated_at": utc_now(),
        "external_root": str(external_root),
        "raw_modified": False,
        "manifests": summaries,
    }
    write_json(report_path, report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="构建只读外部数据统一清单")
    parser.add_argument("--external-root", type=Path, required=True)
    parser.add_argument(
        "--source-registry",
        type=Path,
        required=True,
        help="保留CLI兼容和来源路径记录；构建前必须由validator验证",
    )
    parser.add_argument("--external-schema", type=Path, required=True)
    parser.add_argument("--class-mapping", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        if not args.source_registry.is_file():
            raise GovernanceUsageError(f"来源登记不存在：{args.source_registry}")
        report = build_all(
            args.external_root.resolve(),
            args.external_schema.resolve(),
            args.class_mapping.resolve(),
            args.output_dir.resolve(),
            args.report.resolve(),
        )
        print(json.dumps(report["manifests"], ensure_ascii=False))
        return EXIT_SUCCESS
    except (GovernanceUsageError, FileNotFoundError, ValueError) as exc:
        print(f"数据或配置错误：{exc}", file=sys.stderr)
        return (
            EXIT_DATA_ERROR
            if not isinstance(exc, GovernanceUsageError)
            else EXIT_USAGE_ERROR
        )
    except Exception as exc:  # noqa: BLE001
        print(f"内部错误：{exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
