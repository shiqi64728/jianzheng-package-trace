"""Audit external manifests, licenses, mappings, duplicates and training readiness."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.dataset.external_data_common import (
    GovernanceUsageError,
    image_metadata,
    load_json,
    read_csv,
    sha256_file,
    utc_now,
    validate_relative_path,
    write_csv_bom,
    write_json,
)

EXIT_SUCCESS = 0
EXIT_AUDIT_BLOCKED = 1
EXIT_USAGE_ERROR = 2
EXIT_INTERNAL_ERROR = 3
AUDITOR_VERSION = "0.1.0"
MANIFEST_NAMES = (
    "defect-cardboard-v0.1.csv",
    "damaged-box-detection-v0.1.csv",
    "tampar-pairs-v0.1.csv",
    "public-stats-v0.1.csv",
)
QUARANTINE_FIELDS = (
    "external_record_id",
    "source_id",
    "original_image_relpath",
    "reason_code",
    "reason_description",
    "recommended_action",
)


def _load_manifests(
    manifests_dir: Path,
) -> tuple[dict[str, list[dict[str, str]]], list[str]]:
    manifests: dict[str, list[dict[str, str]]] = {}
    all_fields: list[str] = []
    for name in MANIFEST_NAMES:
        path = manifests_dir / name
        fields, rows = read_csv(path)
        forbidden = {
            "package_id",
            "sequence_id",
            "node_id",
            "capture_time",
            "first_abnormal_node",
        }
        if forbidden.intersection(fields):
            raise GovernanceUsageError(f"外部manifest含内部业务字段：{path}")
        manifests[name] = rows
        all_fields.extend(fields)
    return manifests, all_fields


def _license_audit(
    external_root: Path,
    records: list[dict[str, str]],
    mapping: dict[str, Any],
    registry_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], set[str]]:
    registry_ids = {
        (row.get("source_id") or row.get("dataset_id") or "").strip()
        for row in registry_rows
    }
    sources = mapping.get("sources", {})
    used = sorted({row.get("source_id", "") for row in records})
    report: list[dict[str, Any]] = []
    blocked: set[str] = set()
    for source_id in used:
        source = sources.get(source_id, {})
        license_rel = str(source.get("license_file_relpath", ""))
        citation_rel = str(source.get("citation_file_relpath", ""))
        license_ok = bool(license_rel) and (external_root / license_rel).is_file()
        citation_ok = bool(citation_rel) and (external_root / citation_rel).is_file()
        issues: list[str] = []
        if source_id not in registry_ids:
            issues.append("SOURCE_NOT_IN_REGISTRY")
        if not license_ok:
            issues.append("LICENSE_MISSING")
        if not citation_ok:
            issues.append("CITATION_MISSING")
        status = "passed" if not issues else "blocked"
        if issues:
            blocked.add(source_id)
        report.append(
            {
                "source_id": source_id,
                "dataset_name": source.get("dataset_name", ""),
                "license_name": source.get("license_name", ""),
                "license_file": license_rel,
                "citation_file": citation_rel,
                "usage_scope": source.get("usage_scope", ""),
                "attribution_required": str(source.get("license_name", ""))
                .upper()
                .startswith("CC BY"),
                "attribution_source": citation_rel,
                "blocking_issue": "|".join(issues),
                "audit_status": status,
            }
        )
    return report, blocked


def _integrity_audit(
    external_root: Path, manifests: dict[str, list[dict[str, str]]]
) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    checked_images = 0
    annotation_records = 0
    manifest_counts: dict[str, int] = {}
    for name, rows in manifests.items():
        manifest_counts[name] = len(rows)
        for row in rows:
            record_id = row.get("external_record_id", "")
            image_rel = row.get("original_image_relpath", "")
            for field in (
                "original_image_relpath",
                "original_annotation_relpath",
                "license_file_relpath",
                "citation_file_relpath",
                "reference_image_relpath",
                "tampered_image_relpath",
                "parent_or_augmented_from",
            ):
                value = row.get(field, "")
                try:
                    validate_relative_path(value)
                except GovernanceUsageError as exc:
                    issues.append(
                        {
                            "record_id": record_id,
                            "code": "ABSOLUTE_OR_UNSAFE_PATH",
                            "message": str(exc),
                        }
                    )
            nested = row.get("annotation_records_json", "")
            if nested:
                try:
                    value = json.loads(nested)
                    if not isinstance(value, list):
                        raise ValueError("not a list")
                    annotation_records += len(value)
                except (json.JSONDecodeError, ValueError) as exc:
                    issues.append(
                        {
                            "record_id": record_id,
                            "code": "ANNOTATION_JSON_INVALID",
                            "message": str(exc),
                        }
                    )
            if not image_rel:
                continue
            checked_images += 1
            path = external_root / image_rel
            if not path.is_file():
                issues.append(
                    {
                        "record_id": record_id,
                        "code": "IMAGE_MISSING",
                        "message": image_rel,
                    }
                )
                continue
            try:
                width, height, channels = image_metadata(path)
            except ValueError as exc:
                issues.append(
                    {
                        "record_id": record_id,
                        "code": "IMAGE_UNREADABLE",
                        "message": str(exc),
                    }
                )
                continue
            expected = (
                int(row.get("width") or 0),
                int(row.get("height") or 0),
                int(row.get("channels") or 0),
            )
            if expected != (width, height, channels):
                issues.append(
                    {
                        "record_id": record_id,
                        "code": "IMAGE_DIMENSION_MISMATCH",
                        "message": f"manifest={expected}, actual={(width, height, channels)}",
                    }
                )
            digest = sha256_file(path)
            if digest != row.get("sha256", ""):
                issues.append(
                    {
                        "record_id": record_id,
                        "code": "SHA256_MISMATCH",
                        "message": image_rel,
                    }
                )
    return {
        "checked_images": checked_images,
        "annotation_records": annotation_records,
        "manifest_counts": manifest_counts,
        "issue_count": len(issues),
        "issues": issues,
        "passed": not issues,
    }


def _mapping_audit(
    records: list[dict[str, str]], mapping: dict[str, Any]
) -> list[dict[str, Any]]:
    image_sets: dict[tuple[str, str], set[str]] = defaultdict(set)
    annotations: Counter[tuple[str, str]] = Counter()
    sample: dict[tuple[str, str], dict[str, str]] = {}
    for row in records:
        source_id = row.get("source_id", "")
        nested = row.get("annotation_records_json", "")
        if nested:
            for annotation in json.loads(nested):
                original_class = str(annotation.get("original_class", ""))
                key = (source_id, original_class)
                annotations[key] += 1
                image_sets[key].add(row.get("external_record_id", ""))
                sample.setdefault(key, row)
        else:
            original_class = row.get("original_class", "")
            key = (source_id, original_class)
            annotations[key] += int(bool(original_class))
            image_sets[key].add(row.get("external_record_id", ""))
            sample.setdefault(key, row)
    output: list[dict[str, Any]] = []
    for key in sorted(sample):
        row = sample[key]
        source_id, original_class = key
        source_mapping = mapping.get("sources", {}).get(source_id, {})
        class_mapping = source_mapping.get("classes", {}).get(original_class)
        if not isinstance(class_mapping, dict):
            class_mapping = source_mapping.get("default_mapping", {})
        forbidden = {
            "roboflow-defect-cardboard-h0kjy-v1": "不得把bbox伪造成polygon；dirt未经审核不得正式批准为D04。",
            "roboflow-damaged-box-detection-v1": "不得细分为D01—D05或当作独立物理包裹。",
            "zenodo-tampar-10057090": "不得伪造成N1/N2、内部sequence或责任节点。",
            "spb-public-statistics": "不得进入图像训练manifest。",
        }.get(source_id, "")
        risk = row.get("quarantine_reason", "") or row.get("notes", "")
        output.append(
            {
                "source_id": source_id,
                "original_class": original_class,
                "image_count": len(image_sets[key]),
                "annotation_count": annotations[key],
                "mapped_project_status": class_mapping.get(
                    "mapped_project_status", row.get("mapped_project_status", "")
                ),
                "mapped_project_class": class_mapping.get(
                    "mapped_project_class", row.get("mapped_project_class", "")
                ),
                "project_task": class_mapping.get(
                    "project_task", row.get("project_task", "")
                ),
                "manual_review_required": "true"
                if class_mapping.get("requires_manual_review", False)
                else row.get("requires_manual_review", ""),
                "allowed_use": class_mapping.get(
                    "project_task", row.get("project_task", "")
                ),
                "forbidden_use": forbidden,
                "risk_notes": risk,
            }
        )
    return output


def _duplicate_audit(
    records: list[dict[str, str]],
) -> tuple[dict[str, Any], list[dict[str, str]], set[str]]:
    by_hash: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in records:
        if row.get("original_image_relpath") and row.get("sha256"):
            by_hash[row["sha256"]].append(row)
    groups: list[dict[str, Any]] = []
    quarantine: list[dict[str, str]] = []
    blocked_records: set[str] = set()
    counters = Counter()
    for digest, members in sorted(by_hash.items()):
        if len(members) < 2:
            continue
        sources = {row.get("source_id", "") for row in members}
        splits = {row.get("original_split", "") for row in members}
        labels = {row.get("original_class", "") for row in members}
        cross_dataset = len(sources) > 1
        cross_split = len(splits) > 1
        conflicting = len(labels) > 1
        counters["duplicate_groups"] += 1
        counters["duplicate_extra_images"] += len(members) - 1
        counters["cross_dataset_groups"] += int(cross_dataset)
        counters["cross_split_groups"] += int(cross_split)
        counters["conflicting_label_groups"] += int(conflicting)
        reason = (
            "CROSS_SPLIT_DUPLICATE"
            if cross_split
            else ("CONFLICTING_LABEL" if conflicting else "DUPLICATE_CONTENT")
        )
        if cross_split or conflicting:
            blocked_records.update(row.get("external_record_id", "") for row in members)
        groups.append(
            {
                "duplicate_group_id": members[0].get("duplicate_group_id")
                or f"DUP-{digest[:16]}",
                "sha256": digest,
                "member_count": len(members),
                "source_ids": sorted(sources),
                "splits": sorted(splits),
                "labels": sorted(labels),
                "cross_dataset": cross_dataset,
                "cross_split": cross_split,
                "conflicting_label": conflicting,
                "records": [
                    {
                        "external_record_id": row.get("external_record_id", ""),
                        "source_id": row.get("source_id", ""),
                        "original_split": row.get("original_split", ""),
                        "original_class": row.get("original_class", ""),
                        "original_image_relpath": row.get("original_image_relpath", ""),
                    }
                    for row in members
                ],
            }
        )
        for row in members:
            quarantine.append(
                {
                    "external_record_id": row.get("external_record_id", ""),
                    "source_id": row.get("source_id", ""),
                    "original_image_relpath": row.get("original_image_relpath", ""),
                    "reason_code": reason,
                    "reason_description": "字节级SHA-256重复；未删除原文件。",
                    "recommended_action": "划分训练集前按组保留单一split；跨split或标签冲突必须阻塞。",
                }
            )
    return {"summary": dict(counters), "groups": groups}, quarantine, blocked_records


def _readiness(
    records: list[dict[str, str]], duplicate_report: dict[str, Any]
) -> list[dict[str, str]]:
    counts = Counter(row.get("source_id", "") for row in records)
    pair_counts = Counter(row.get("pairing_confidence", "") for row in records)
    cross_split = int(duplicate_report.get("summary", {}).get("cross_split_groups", 0))
    return [
        {
            "task": "完好/损伤二分类",
            "status": "ready_with_review"
            if counts["roboflow-damaged-box-detection-v1"] and cross_split == 0
            else "not_ready",
            "reason": "标签可用于二分类；需审核增强、背景偏差和同split重复。",
        },
        {
            "task": "D02/D03目标检测",
            "status": "ready_with_review"
            if counts["roboflow-defect-cardboard-h0kjy-v1"]
            else "not_ready",
            "reason": "dent/hole保留COCO bbox；训练前需人工抽样和类别不平衡检查。",
        },
        {
            "task": "D04候选目标检测",
            "status": "not_ready",
            "reason": "dirt不等于受潮，必须由成员C审核并批准或否决。",
        },
        {
            "task": "实例分割",
            "status": "not_ready",
            "reason": "D02/D03来源只有bbox；TAMPAR polygon是normal box几何，不是项目损伤实例分割。",
        },
        {
            "task": "前后变化检测",
            "status": "ready_with_review" if pair_counts["probable"] else "not_ready",
            "reason": "TAMPAR只有probable/unresolved配对，需人工确认。",
        },
        {
            "task": "表面归一化",
            "status": "ready_with_review"
            if counts["zenodo-tampar-10057090"]
            else "not_ready",
            "reason": "TAMPAR包含真实polygon/keypoints/uvmap资产，仍需用途复核。",
        },
        {
            "task": "真实连续节点定位",
            "status": "not_ready",
            "reason": "公开数据不能证明真实N1/N2/N3异常节点或责任。",
        },
    ]


def audit_all(
    external_root: Path,
    manifests_dir: Path,
    source_registry: Path,
    class_mapping: Path,
    report_dir: Path,
) -> dict[str, Any]:
    """Run all audits and write reports/quarantine manifests outside raw."""

    if (
        report_dir.resolve().parent != external_root.resolve()
        or report_dir.name != "reports"
    ):
        raise GovernanceUsageError("report-dir必须是external根目录下的reports目录。")
    manifests, _ = _load_manifests(manifests_dir)
    records = [row for rows in manifests.values() for row in rows]
    _, registry_rows = read_csv(source_registry)
    mapping = load_json(class_mapping)

    integrity = _integrity_audit(external_root, manifests)
    license_rows, blocked_sources = _license_audit(
        external_root, records, mapping, registry_rows
    )
    mapping_rows = _mapping_audit(records, mapping)
    duplicate_report, duplicate_quarantine, blocked_records = _duplicate_audit(records)
    readiness_rows = _readiness(records, duplicate_report)

    write_json(
        report_dir / "external-license-audit-v0.1.json",
        {"generated_at": utc_now(), "sources": license_rows},
    )
    write_csv_bom(
        report_dir / "external-class-mapping-audit-v0.1.csv",
        (
            "source_id",
            "original_class",
            "image_count",
            "annotation_count",
            "mapped_project_status",
            "mapped_project_class",
            "project_task",
            "manual_review_required",
            "allowed_use",
            "forbidden_use",
            "risk_notes",
        ),
        mapping_rows,
    )
    duplicate_output = {"generated_at": utc_now(), **duplicate_report}
    write_json(report_dir / "cross-dataset-duplicate-audit-v0.1.json", duplicate_output)

    quarantine_dir = external_root / "quarantine" / "manifests"
    ambiguous: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    blocked_license: list[dict[str, str]] = []
    for row in records:
        reason = row.get("quarantine_reason", "")
        base = {
            "external_record_id": row.get("external_record_id", ""),
            "source_id": row.get("source_id", ""),
            "original_image_relpath": row.get("original_image_relpath", ""),
        }
        if row.get("mapped_project_status") == "candidate":
            ambiguous.append(
                {
                    **base,
                    "reason_code": reason or "AMBIGUOUS_D04_DIRT",
                    "reason_description": "候选类别语义尚未获人工批准。",
                    "recommended_action": "成员C查看样本并批准或否决映射。",
                }
            )
        if row.get("pairing_confidence") == "unresolved":
            item = {
                **base,
                "reason_code": "TAMPAR_PAIR_UNRESOLVED",
                "reason_description": "缺少同split同parcel id参考图。",
                "recommended_action": "人工核对来源结构；不得伪造reference。",
            }
            unresolved.append(item)
            ambiguous.append(item)
        if row.get("source_id") in blocked_sources:
            blocked_license.append(
                {
                    **base,
                    "reason_code": "LICENSE_MISSING",
                    "reason_description": "来源登记、许可证或引用证据不完整。",
                    "recommended_action": "补齐并复核本地证据前保持blocked。",
                }
            )
        if row.get("external_record_id") in blocked_records and not any(
            item["external_record_id"] == row.get("external_record_id")
            for item in duplicate_quarantine
        ):
            raise RuntimeError("重复阻塞记录未进入隔离清单。")

    write_csv_bom(
        quarantine_dir / "ambiguous-class-records-v0.1.csv",
        QUARANTINE_FIELDS,
        ambiguous,
    )
    write_csv_bom(
        quarantine_dir / "duplicate-records-v0.1.csv",
        QUARANTINE_FIELDS,
        duplicate_quarantine,
    )
    write_csv_bom(
        quarantine_dir / "blocked-license-records-v0.1.csv",
        QUARANTINE_FIELDS,
        blocked_license,
    )
    write_csv_bom(
        quarantine_dir / "unresolved-pairs-v0.1.csv", QUARANTINE_FIELDS, unresolved
    )

    readiness = {
        "generated_at": utc_now(),
        "allowed_statuses": [
            "ready",
            "ready_with_review",
            "not_ready",
            "not_applicable",
        ],
        "tasks": readiness_rows,
        "recommended_first_model_task": "D02/D03目标检测",
        "recommendation_reason": "defect-cardboard无精确重复，保留16,592个bbox；先排除dirt并完成dent/hole抽样复核。",
    }
    write_json(report_dir / "external-dataset-readiness-v0.1.json", readiness)
    markdown = [
        "# 外部数据可训练性评估 v0.1",
        "",
        "| 任务 | 状态 | 原因 |",
        "|---|---|---|",
    ]
    markdown.extend(
        f"| {row['task']} | `{row['status']}` | {row['reason']} |"
        for row in readiness_rows
    )
    markdown.extend(
        [
            "",
            "## 推荐首个模型任务",
            "",
            "**D02/D03目标检测**。训练前先排除 `dirt`，完成 dent/hole 人工抽样，并冻结无跨split重复的数据版本。",
            "",
            "本报告不代表已训练模型，也不证明真实连续物流节点定位能力。",
            "",
        ]
    )
    (report_dir / "external-dataset-readiness-v0.1.md").write_text(
        "\n".join(markdown), encoding="utf-8"
    )

    summary = {
        "auditor_version": AUDITOR_VERSION,
        "generated_at": utc_now(),
        "integrity": integrity,
        "license_status_counts": dict(
            Counter(row["audit_status"] for row in license_rows)
        ),
        "duplicate_summary": duplicate_report["summary"],
        "quarantine_counts": {
            "ambiguous_class_records": len(ambiguous),
            "duplicate_records": len(duplicate_quarantine),
            "blocked_license_records": len(blocked_license),
            "unresolved_pairs": len(unresolved),
        },
        "raw_modified": False,
    }
    write_json(report_dir / "external-dataset-audit-summary-v0.1.json", summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="审计外部公开数据治理清单")
    parser.add_argument("--external-root", type=Path, required=True)
    parser.add_argument("--manifests-dir", type=Path, required=True)
    parser.add_argument("--source-registry", type=Path, required=True)
    parser.add_argument("--class-mapping", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        summary = audit_all(
            args.external_root.resolve(),
            args.manifests_dir.resolve(),
            args.source_registry.resolve(),
            args.class_mapping.resolve(),
            args.report_dir.resolve(),
        )
        print(json.dumps(summary, ensure_ascii=False))
        return EXIT_SUCCESS if summary["integrity"]["passed"] else EXIT_AUDIT_BLOCKED
    except GovernanceUsageError as exc:
        print(f"参数或配置错误：{exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    except Exception as exc:  # noqa: BLE001
        print(f"内部错误：{exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
