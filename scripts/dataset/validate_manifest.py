"""Validate 件证 dataset manifests against the v0.1 data contract."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import traceback
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Sequence

import cv2

EXIT_VALID = 0
EXIT_DATA_INVALID = 1
EXIT_USAGE_ERROR = 2
EXIT_INTERNAL_ERROR = 3
VALIDATOR_VERSION = "0.1.0"


class UsageError(RuntimeError):
    """Raised for invalid CLI inputs or an unusable contract file."""


class ManifestReadError(RuntimeError):
    """Raised when the CSV itself cannot be decoded or parsed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Issue:
    """A single validation error or warning."""

    severity: str
    code: str
    message: str
    row_number: int | None = None
    record_id: str | None = None
    field: str | None = None


@dataclass
class ValidationReport:
    """Complete validation result, including row-level statistics."""

    manifest: str
    data_root: str
    schema: str
    schema_version: str
    check_files: bool
    total_records: int
    passed_records: int
    failed_records: int
    issues: list[Issue]

    @property
    def error_count(self) -> int:
        return sum(issue.severity == "error" for issue in self.issues)

    @property
    def warning_count(self) -> int:
        return sum(issue.severity == "warning" for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "validator_version": VALIDATOR_VERSION,
            "generated_at": datetime.now(UTC).isoformat(),
            "manifest": self.manifest,
            "data_root": self.data_root,
            "schema": self.schema,
            "schema_version": self.schema_version,
            "check_files": self.check_files,
            "summary": {
                "total_records": self.total_records,
                "passed_records": self.passed_records,
                "failed_records": self.failed_records,
                "error_count": self.error_count,
                "warning_count": self.warning_count,
                "valid": self.error_count == 0,
            },
            "issues": [asdict(issue) for issue in self.issues],
        }


def load_schema(schema_path: Path) -> dict[str, Any]:
    """Load and minimally validate the machine-readable data contract."""

    if not schema_path.is_file():
        raise UsageError(f"数据合同文件不存在：{schema_path}")
    try:
        with schema_path.open("r", encoding="utf-8-sig") as handle:
            schema = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise UsageError(f"无法读取数据合同 {schema_path}：{exc}") from exc

    if not isinstance(schema, dict):
        raise UsageError("数据合同顶层必须是 JSON 对象。")

    required_keys = {
        "schema_version",
        "fields",
        "required_columns",
        "required_values",
        "enums",
        "identifier_patterns",
        "path_rules",
        "split_rules",
        "sequence_rules",
    }
    missing_keys = sorted(required_keys - schema.keys())
    if missing_keys:
        raise UsageError(f"数据合同缺少顶层键：{', '.join(missing_keys)}")

    fields = schema["fields"]
    if (
        not isinstance(fields, list)
        or not fields
        or not all(isinstance(item, str) and item for item in fields)
    ):
        raise UsageError("数据合同 fields 必须是非空字符串数组。")
    if len(fields) != len(set(fields)):
        raise UsageError("数据合同 fields 包含重复字段。")

    for key in ("required_columns", "required_values"):
        value = schema[key]
        if not isinstance(value, list) or not set(value).issubset(fields):
            raise UsageError(f"数据合同 {key} 必须是 fields 的子集。")

    enums = schema["enums"]
    if not isinstance(enums, dict):
        raise UsageError("数据合同 enums 必须是对象。")
    for field, values in enums.items():
        if field not in fields or not isinstance(values, list) or not values:
            raise UsageError(f"数据合同枚举定义无效：{field}")

    return schema


def _read_manifest(
    manifest_path: Path,
) -> tuple[list[str], list[tuple[int, dict[str | None, str | list[str] | None]]]]:
    try:
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            if reader.fieldnames is None:
                return [], []
            fieldnames = [field.strip() for field in reader.fieldnames]
            rows = [
                (line_number, dict(row)) for line_number, row in enumerate(reader, 2)
            ]
            return fieldnames, rows
    except UnicodeDecodeError as exc:
        raise ManifestReadError(
            "CSV_ENCODING_ERROR",
            f"CSV 不是有效的 UTF-8/UTF-8 BOM 文件：{exc}",
        ) from exc
    except csv.Error as exc:
        raise ManifestReadError("CSV_PARSE_ERROR", f"CSV 格式错误：{exc}") from exc
    except OSError as exc:
        raise ManifestReadError("CSV_READ_ERROR", f"无法读取 CSV：{exc}") from exc


def _add_issue(
    issues: list[Issue],
    severity: str,
    code: str,
    message: str,
    *,
    row_number: int | None = None,
    record_id: str | None = None,
    field: str | None = None,
) -> None:
    issues.append(
        Issue(
            severity=severity,
            code=code,
            message=message,
            row_number=row_number,
            record_id=record_id or None,
            field=field,
        )
    )


def _validate_capture_time(
    value: str,
    issues: list[Issue],
    *,
    row_number: int,
    record_id: str,
) -> None:
    if not value:
        return
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = None
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset() is None:
        _add_issue(
            issues,
            "error",
            "INVALID_CAPTURE_TIME",
            "capture_time 必须是包含时区的 ISO 8601 时间。",
            row_number=row_number,
            record_id=record_id,
            field="capture_time",
        )


def _validate_image_path(
    raw_path: str,
    data_root: Path,
    allowed_extensions: set[str],
    issues: list[Issue],
    *,
    row_number: int,
    record_id: str,
) -> tuple[Path | None, str | None]:
    if not raw_path:
        return None, None

    if "\x00" in raw_path:
        _add_issue(
            issues,
            "error",
            "INVALID_PATH_CHARACTER",
            "image_relpath 包含空字符。",
            row_number=row_number,
            record_id=record_id,
            field="image_relpath",
        )
        return None, None

    if "\\" in raw_path:
        _add_issue(
            issues,
            "error",
            "PATH_BACKSLASH",
            "image_relpath 必须使用正斜杠“/”，不得使用反斜杠。",
            row_number=row_number,
            record_id=record_id,
            field="image_relpath",
        )
        return None, None

    windows_path = PureWindowsPath(raw_path)
    posix_path = PurePosixPath(raw_path)
    if (
        windows_path.is_absolute()
        or bool(windows_path.drive)
        or posix_path.is_absolute()
        or raw_path.startswith("//")
    ):
        _add_issue(
            issues,
            "error",
            "ABSOLUTE_IMAGE_PATH",
            "image_relpath 必须是相对于 data-root 的路径，不得包含盘符、UNC 或根路径。",
            row_number=row_number,
            record_id=record_id,
            field="image_relpath",
        )
        return None, None

    raw_parts = raw_path.split("/")
    if ".." in raw_parts:
        _add_issue(
            issues,
            "error",
            "PARENT_PATH_TRAVERSAL",
            "image_relpath 不得包含“..”越级目录。",
            row_number=row_number,
            record_id=record_id,
            field="image_relpath",
        )
        return None, None
    if any(part in {"", "."} for part in raw_parts):
        _add_issue(
            issues,
            "error",
            "NON_CANONICAL_IMAGE_PATH",
            "image_relpath 不得包含空路径段或“.”路径段。",
            row_number=row_number,
            record_id=record_id,
            field="image_relpath",
        )
        return None, None

    suffix = posix_path.suffix.casefold()
    if suffix not in allowed_extensions:
        _add_issue(
            issues,
            "error",
            "UNSUPPORTED_IMAGE_EXTENSION",
            f"不支持的图片扩展名“{suffix or '<空>'}”。",
            row_number=row_number,
            record_id=record_id,
            field="image_relpath",
        )

    root_resolved = data_root.resolve()
    candidate = data_root.joinpath(*posix_path.parts)
    try:
        resolved = candidate.resolve(strict=False)
        resolved.relative_to(root_resolved)
    except (OSError, ValueError):
        _add_issue(
            issues,
            "error",
            "IMAGE_PATH_OUTSIDE_ROOT",
            "image_relpath 解析后位于 data-root 之外。",
            row_number=row_number,
            record_id=record_id,
            field="image_relpath",
        )
        return None, None

    normalized_key = "/".join(posix_path.parts).casefold()
    return resolved, normalized_key


def _add_group_issues(
    rows: Sequence[dict[str, str | int]],
    issues: list[Issue],
    *,
    severity: str,
    code: str,
    message: str,
    field: str,
) -> None:
    for row in rows:
        _add_issue(
            issues,
            severity,
            code,
            message,
            row_number=int(row["_row_number"]),
            record_id=str(row.get("record_id", "")),
            field=field,
        )


def _validate_row(
    row: dict[str, str | int],
    schema: dict[str, Any],
    data_root: Path,
    issues: list[Issue],
    resolved_paths: dict[int, Path],
    normalized_image_paths: dict[int, str],
) -> None:
    row_number = int(row["_row_number"])
    record_id = str(row.get("record_id", ""))

    for field in schema["required_values"]:
        if not str(row.get(field, "")):
            _add_issue(
                issues,
                "error",
                "MISSING_VALUE",
                f"必填字段 {field} 不能为空。",
                row_number=row_number,
                record_id=record_id,
                field=field,
            )

    if row.get("schema_version") and row["schema_version"] != schema["schema_version"]:
        _add_issue(
            issues,
            "error",
            "SCHEMA_VERSION_MISMATCH",
            f"schema_version 必须为 {schema['schema_version']}。",
            row_number=row_number,
            record_id=record_id,
            field="schema_version",
        )

    for field, allowed in schema["enums"].items():
        value = str(row.get(field, ""))
        if value and value not in allowed:
            _add_issue(
                issues,
                "error",
                "INVALID_ENUM",
                f"{field} 的值“{value}”不在允许枚举中：{', '.join(allowed)}。",
                row_number=row_number,
                record_id=record_id,
                field=field,
            )

    for field, pattern in schema["identifier_patterns"].items():
        value = str(row.get(field, ""))
        if value and re.fullmatch(pattern, value) is None:
            _add_issue(
                issues,
                "error",
                "INVALID_IDENTIFIER",
                f"{field} 的格式无效；只允许以字母或数字开头，并使用字母、数字、点、下划线或连字符。",
                row_number=row_number,
                record_id=record_id,
                field=field,
            )

    _validate_capture_time(
        str(row.get("capture_time", "")),
        issues,
        row_number=row_number,
        record_id=record_id,
    )

    allowed_extensions = {
        str(value).casefold() for value in schema["path_rules"]["allowed_extensions"]
    }
    resolved, normalized = _validate_image_path(
        str(row.get("image_relpath", "")),
        data_root,
        allowed_extensions,
        issues,
        row_number=row_number,
        record_id=record_id,
    )
    if resolved is not None:
        resolved_paths[row_number] = resolved
    if normalized is not None:
        normalized_image_paths[row_number] = normalized

    source_type = str(row.get("source_type", ""))
    node_id = str(row.get("node_id", ""))
    sequence_id = str(row.get("sequence_id", ""))
    status = str(row.get("status", ""))
    damage_type = str(row.get("damage_type", ""))
    severity = str(row.get("severity", ""))
    first_abnormal = str(row.get("first_abnormal_node", ""))
    privacy_status = str(row.get("privacy_status", ""))
    annotation_status = str(row.get("annotation_status", ""))
    split = str(row.get("split", ""))
    reviewer = str(row.get("reviewer", ""))

    if status == "normal":
        if damage_type and damage_type != "NONE":
            _add_issue(
                issues,
                "error",
                "NORMAL_WITH_DAMAGE_TYPE",
                "正常样本必须使用 damage_type=NONE。",
                row_number=row_number,
                record_id=record_id,
                field="damage_type",
            )
        if severity and severity != "none":
            _add_issue(
                issues,
                "error",
                "NORMAL_WITH_SEVERITY",
                "正常样本必须使用 severity=none。",
                row_number=row_number,
                record_id=record_id,
                field="severity",
            )
    elif status == "abnormal":
        if damage_type == "NONE":
            _add_issue(
                issues,
                "error",
                "ABNORMAL_WITHOUT_DAMAGE_TYPE",
                "异常样本不得使用 damage_type=NONE。",
                row_number=row_number,
                record_id=record_id,
                field="damage_type",
            )
        if severity == "none":
            _add_issue(
                issues,
                "error",
                "ABNORMAL_WITHOUT_SEVERITY",
                "异常样本不得使用 severity=none。",
                row_number=row_number,
                record_id=record_id,
                field="severity",
            )

    if source_type == "continuous_node":
        if not sequence_id:
            _add_issue(
                issues,
                "error",
                "CONTINUOUS_MISSING_SEQUENCE_ID",
                "continuous_node 记录必须填写 sequence_id。",
                row_number=row_number,
                record_id=record_id,
                field="sequence_id",
            )
        if node_id == "NA":
            _add_issue(
                issues,
                "error",
                "CONTINUOUS_NODE_NA",
                "continuous_node 记录的 node_id 不得为 NA。",
                row_number=row_number,
                record_id=record_id,
                field="node_id",
            )
        if status == "abnormal" and first_abnormal == "NONE":
            _add_issue(
                issues,
                "error",
                "ABNORMAL_SEQUENCE_WITH_NONE_FIRST_NODE",
                "连续序列中的异常记录不得使用 first_abnormal_node=NONE。",
                row_number=row_number,
                record_id=record_id,
                field="first_abnormal_node",
            )
    elif source_type and sequence_id:
        _add_issue(
            issues,
            "error",
            "NON_CONTINUOUS_HAS_SEQUENCE_ID",
            "非 continuous_node 记录不得填写 sequence_id。",
            row_number=row_number,
            record_id=record_id,
            field="sequence_id",
        )

    if (
        source_type != "continuous_node"
        and status == "normal"
        and first_abnormal
        not in {
            "",
            "NONE",
        }
    ):
        _add_issue(
            issues,
            "error",
            "NORMAL_WITH_FIRST_ABNORMAL_NODE",
            "非连续正常样本必须使用 first_abnormal_node=NONE。",
            row_number=row_number,
            record_id=record_id,
            field="first_abnormal_node",
        )
    if (
        source_type != "continuous_node"
        and status == "abnormal"
        and first_abnormal == "NONE"
    ):
        _add_issue(
            issues,
            "error",
            "ABNORMAL_WITH_NONE_FIRST_NODE",
            "非连续异常样本应使用 UNKNOWN 或已知节点，不得使用 NONE。",
            row_number=row_number,
            record_id=record_id,
            field="first_abnormal_node",
        )

    if privacy_status in {"rejected", "pending_review"}:
        _add_issue(
            issues,
            "error",
            "PRIVACY_NOT_APPROVED",
            "可接收清单的 privacy_status 必须为 masked 或 not_applicable；该记录必须返工。",
            row_number=row_number,
            record_id=record_id,
            field="privacy_status",
        )

    if split in {"train", "val", "test"} and annotation_status not in {
        "labelled",
        "reviewed",
    }:
        _add_issue(
            issues,
            "error",
            "ANNOTATION_NOT_READY",
            "train/val/test 记录必须达到 labelled 或 reviewed 状态。",
            row_number=row_number,
            record_id=record_id,
            field="annotation_status",
        )
    if annotation_status == "reviewed" and not reviewer:
        _add_issue(
            issues,
            "error",
            "REVIEWER_REQUIRED",
            "annotation_status=reviewed 时必须填写 reviewer。",
            row_number=row_number,
            record_id=record_id,
            field="reviewer",
        )


def _validate_groups(
    records: list[dict[str, str | int]],
    schema: dict[str, Any],
    normalized_image_paths: dict[int, str],
    issues: list[Issue],
) -> None:
    record_groups: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    image_groups: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    package_groups: dict[str, list[dict[str, str | int]]] = defaultdict(list)
    sequence_groups: dict[str, list[dict[str, str | int]]] = defaultdict(list)

    for row in records:
        row_number = int(row["_row_number"])
        record_id = str(row.get("record_id", ""))
        package_id = str(row.get("package_id", ""))
        sequence_id = str(row.get("sequence_id", ""))
        if record_id:
            record_groups[record_id.casefold()].append(row)
        if row_number in normalized_image_paths:
            image_groups[normalized_image_paths[row_number]].append(row)
        if package_id:
            package_groups[package_id.casefold()].append(row)
        if sequence_id:
            sequence_groups[sequence_id.casefold()].append(row)

    for rows in record_groups.values():
        if len(rows) > 1:
            _add_group_issues(
                rows,
                issues,
                severity="error",
                code="DUPLICATE_RECORD_ID",
                message=f"record_id 重复，共出现 {len(rows)} 次。",
                field="record_id",
            )

    for rows in image_groups.values():
        if len(rows) > 1:
            _add_group_issues(
                rows,
                issues,
                severity="error",
                code="DUPLICATE_IMAGE_RELPATH",
                message=f"同一 image_relpath 被重复引用，共出现 {len(rows)} 次。",
                field="image_relpath",
            )

    protected_splits = set(schema["split_rules"]["protected_splits"])
    for rows in package_groups.values():
        splits = {
            str(row.get("split", ""))
            for row in rows
            if row.get("split") in protected_splits
        }
        if len(splits) > 1:
            _add_group_issues(
                rows,
                issues,
                severity="error",
                code="PACKAGE_SPLIT_LEAKAGE",
                message=f"同一 package_id 跨数据集：{', '.join(sorted(splits))}。",
                field="split",
            )

        for consistency_field, code in (
            ("batch_id", "PACKAGE_ID_BATCH_CONFLICT"),
            ("source_type", "PACKAGE_ID_SOURCE_CONFLICT"),
        ):
            values = {
                str(row.get(consistency_field, ""))
                for row in rows
                if row.get(consistency_field)
            }
            if len(values) > 1:
                _add_group_issues(
                    rows,
                    issues,
                    severity="error",
                    code=code,
                    message=(
                        "同一 package_id 出现互相冲突的"
                        f" {consistency_field}：{', '.join(sorted(values))}；"
                        "可能是包裹 ID 重复使用。"
                    ),
                    field=consistency_field,
                )

    required_nodes = set(schema["sequence_rules"]["required_nodes"])
    node_order = {"N1": 1, "N2": 2, "N3": 3}
    for rows in sequence_groups.values():
        splits = {
            str(row.get("split", ""))
            for row in rows
            if row.get("split") in protected_splits
        }
        if len(splits) > 1:
            _add_group_issues(
                rows,
                issues,
                severity="error",
                code="SEQUENCE_SPLIT_LEAKAGE",
                message=f"同一 sequence_id 跨数据集：{', '.join(sorted(splits))}。",
                field="split",
            )

        packages = {
            str(row.get("package_id", "")) for row in rows if row.get("package_id")
        }
        if len(packages) > 1:
            _add_group_issues(
                rows,
                issues,
                severity="error",
                code="SEQUENCE_PACKAGE_CONFLICT",
                message=f"同一 sequence_id 对应多个 package_id：{', '.join(sorted(packages))}。",
                field="package_id",
            )

        sources = {str(row.get("source_type", "")) for row in rows}
        if sources != {"continuous_node"}:
            _add_group_issues(
                rows,
                issues,
                severity="error",
                code="SEQUENCE_SOURCE_CONFLICT",
                message="填写 sequence_id 的记录必须全部使用 source_type=continuous_node。",
                field="source_type",
            )

        nodes = {str(row.get("node_id", "")) for row in rows}
        missing_nodes = sorted(required_nodes - nodes)
        if missing_nodes:
            _add_group_issues(
                rows,
                issues,
                severity="error",
                code="INCOMPLETE_SEQUENCE_NODES",
                message=f"连续序列缺少节点：{', '.join(missing_nodes)}。",
                field="node_id",
            )

        slot_groups: dict[tuple[str, str], list[dict[str, str | int]]] = defaultdict(
            list
        )
        for row in rows:
            slot_groups[
                (str(row.get("node_id", "")), str(row.get("surface", "")))
            ].append(row)
        for slot, slot_rows in slot_groups.items():
            if len(slot_rows) > 1:
                _add_group_issues(
                    slot_rows,
                    issues,
                    severity="error",
                    code="DUPLICATE_SEQUENCE_SLOT",
                    message=f"同一序列节点/表面槽位重复：{slot[0]}/{slot[1]}。",
                    field="image_relpath",
                )

        first_values = {
            str(row.get("first_abnormal_node", ""))
            for row in rows
            if row.get("first_abnormal_node")
        }
        if len(first_values) > 1:
            _add_group_issues(
                rows,
                issues,
                severity="error",
                code="SEQUENCE_FIRST_ABNORMAL_CONFLICT",
                message=(
                    "同一 sequence_id 的 first_abnormal_node 不一致："
                    f"{', '.join(sorted(first_values))}。"
                ),
                field="first_abnormal_node",
            )
            continue
        if not first_values:
            continue

        first_abnormal = next(iter(first_values))
        abnormal_rows = [row for row in rows if row.get("status") == "abnormal"]
        if first_abnormal == "UNKNOWN" and required_nodes.issubset(nodes):
            _add_group_issues(
                rows,
                issues,
                severity="error",
                code="FIRST_ABNORMAL_UNKNOWN_COMPLETE_SEQUENCE",
                message="完整 N1/N2/N3 序列不得使用 first_abnormal_node=UNKNOWN。",
                field="first_abnormal_node",
            )
        elif first_abnormal == "NONE" and abnormal_rows:
            _add_group_issues(
                abnormal_rows,
                issues,
                severity="error",
                code="FIRST_ABNORMAL_NONE_WITH_DAMAGE",
                message="序列含异常记录时 first_abnormal_node 不得为 NONE。",
                field="first_abnormal_node",
            )
        elif first_abnormal in node_order:
            earlier_abnormal = [
                row
                for row in abnormal_rows
                if node_order.get(str(row.get("node_id", "")), 99)
                < node_order[first_abnormal]
            ]
            if earlier_abnormal:
                _add_group_issues(
                    earlier_abnormal,
                    issues,
                    severity="error",
                    code="ABNORMAL_BEFORE_FIRST_NODE",
                    message="记录在 first_abnormal_node 之前已经标为 abnormal。",
                    field="first_abnormal_node",
                )
            if not any(
                row.get("status") == "abnormal" and row.get("node_id") == first_abnormal
                for row in rows
            ):
                _add_group_issues(
                    rows,
                    issues,
                    severity="error",
                    code="FIRST_ABNORMAL_NODE_MISMATCH",
                    message=(
                        f"first_abnormal_node={first_abnormal}，但该节点没有异常记录。"
                    ),
                    field="first_abnormal_node",
                )


def validate_manifest(
    manifest_path: Path,
    data_root: Path,
    schema_path: Path,
    *,
    check_files: bool = False,
) -> ValidationReport:
    """Validate a manifest without modifying the CSV or any image."""

    manifest_path = manifest_path.resolve()
    data_root = data_root.resolve()
    schema_path = schema_path.resolve()

    if not manifest_path.is_file():
        raise UsageError(f"清单文件不存在：{manifest_path}")
    if not data_root.is_dir():
        raise UsageError(f"数据根目录不存在或不是目录：{data_root}")

    schema = load_schema(schema_path)
    issues: list[Issue] = []

    try:
        fieldnames, raw_rows = _read_manifest(manifest_path)
    except ManifestReadError as exc:
        _add_issue(issues, "error", exc.code, str(exc))
        return ValidationReport(
            manifest=str(manifest_path),
            data_root=str(data_root),
            schema=str(schema_path),
            schema_version=str(schema["schema_version"]),
            check_files=check_files,
            total_records=0,
            passed_records=0,
            failed_records=0,
            issues=issues,
        )

    if not fieldnames:
        _add_issue(issues, "error", "EMPTY_MANIFEST", "清单为空或缺少表头。")
        return ValidationReport(
            manifest=str(manifest_path),
            data_root=str(data_root),
            schema=str(schema_path),
            schema_version=str(schema["schema_version"]),
            check_files=check_files,
            total_records=0,
            passed_records=0,
            failed_records=0,
            issues=issues,
        )

    expected_fields = list(schema["fields"])
    missing_columns = [
        field for field in schema["required_columns"] if field not in fieldnames
    ]
    extra_columns = [field for field in fieldnames if field not in expected_fields]
    duplicate_columns = sorted(
        {field for field in fieldnames if fieldnames.count(field) > 1}
    )
    for field in missing_columns:
        _add_issue(
            issues,
            "error",
            "MISSING_COLUMN",
            f"缺少必需列：{field}。",
            field=field,
        )
    for field in extra_columns:
        _add_issue(
            issues,
            "warning",
            "EXTRA_COLUMN",
            f"发现合同之外的列：{field}；验证器不会使用该列。",
            field=field,
        )
    for field in duplicate_columns:
        _add_issue(
            issues,
            "error",
            "DUPLICATE_COLUMN",
            f"CSV 表头包含重复列：{field}。",
            field=field,
        )

    records: list[dict[str, str | int]] = []
    resolved_paths: dict[int, Path] = {}
    normalized_image_paths: dict[int, str] = {}
    for row_number, raw_row in raw_rows:
        if None in raw_row:
            _add_issue(
                issues,
                "error",
                "MALFORMED_ROW",
                "该行字段数量超过表头列数。",
                row_number=row_number,
            )
        normalized_row: dict[str, str | int] = {"_row_number": row_number}
        for field in expected_fields:
            value = raw_row.get(field, "")
            text = "" if value is None or isinstance(value, list) else str(value)
            stripped = text.strip()
            normalized_row[field] = stripped
            if text != stripped:
                _add_issue(
                    issues,
                    "warning",
                    "SURROUNDING_WHITESPACE",
                    f"{field} 含首尾空白；请在源 CSV 中清理。",
                    row_number=row_number,
                    record_id=str(normalized_row.get("record_id", "")),
                    field=field,
                )
        records.append(normalized_row)
        _validate_row(
            normalized_row,
            schema,
            data_root,
            issues,
            resolved_paths,
            normalized_image_paths,
        )

    if not records:
        _add_issue(issues, "error", "EMPTY_MANIFEST", "清单只有表头，没有数据记录。")
    else:
        _validate_groups(records, schema, normalized_image_paths, issues)

    if check_files:
        for row in records:
            row_number = int(row["_row_number"])
            image_path = resolved_paths.get(row_number)
            if image_path is None:
                continue
            record_id = str(row.get("record_id", ""))
            if not image_path.is_file():
                _add_issue(
                    issues,
                    "error",
                    "IMAGE_NOT_FOUND",
                    f"图片不存在：{row.get('image_relpath', '')}。",
                    row_number=row_number,
                    record_id=record_id,
                    field="image_relpath",
                )
                continue
            try:
                image = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
            except cv2.error as exc:
                _add_issue(
                    issues,
                    "error",
                    "IMAGE_READ_ERROR",
                    f"OpenCV 读取图片时出错：{exc}",
                    row_number=row_number,
                    record_id=record_id,
                    field="image_relpath",
                )
                continue
            if image is None or image.size == 0:
                _add_issue(
                    issues,
                    "error",
                    "IMAGE_UNREADABLE",
                    "图片存在，但 OpenCV 无法解码或内容为空。",
                    row_number=row_number,
                    record_id=record_id,
                    field="image_relpath",
                )

    failed_rows = {
        issue.row_number
        for issue in issues
        if issue.severity == "error" and issue.row_number is not None
    }
    if (
        any(issue.severity == "error" and issue.row_number is None for issue in issues)
        and records
    ):
        if missing_columns or duplicate_columns:
            failed_rows.update(int(row["_row_number"]) for row in records)

    total_records = len(records)
    failed_records = len(failed_rows)
    passed_records = max(0, total_records - failed_records)
    return ValidationReport(
        manifest=str(manifest_path),
        data_root=str(data_root),
        schema=str(schema_path),
        schema_version=str(schema["schema_version"]),
        check_files=check_files,
        total_records=total_records,
        passed_records=passed_records,
        failed_records=failed_records,
        issues=issues,
    )


def write_report(report: ValidationReport, report_path: Path) -> None:
    """Write a UTF-8 JSON report to the explicitly requested location."""

    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(report.to_dict(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except OSError as exc:
        raise UsageError(f"无法写入 JSON 报告 {report_path}：{exc}") from exc


def print_summary(report: ValidationReport) -> None:
    """Print a deterministic Chinese console summary."""

    print(
        "验证摘要："
        f"总记录={report.total_records}，"
        f"通过记录={report.passed_records}，"
        f"失败记录={report.failed_records}，"
        f"错误={report.error_count}，"
        f"警告={report.warning_count}"
    )
    for issue in report.issues:
        context_parts: list[str] = []
        if issue.row_number is not None:
            context_parts.append(f"行={issue.row_number}")
        if issue.record_id:
            context_parts.append(f"record_id={issue.record_id}")
        if issue.field:
            context_parts.append(f"字段={issue.field}")
        context = "，".join(context_parts) if context_parts else "全局"
        print(f"[{issue.severity.upper()}] {issue.code}（{context}）：{issue.message}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="按件证数据合同 v0.1 只读校验 CSV 清单。"
    )
    parser.add_argument("--manifest", type=Path, required=True, help="待校验 CSV 清单")
    parser.add_argument("--data-root", type=Path, required=True, help="图片数据根目录")
    parser.add_argument(
        "--schema", type=Path, required=True, help="机器可读数据合同 JSON"
    )
    parser.add_argument("--report", type=Path, help="可选 JSON 报告输出路径")
    parser.add_argument(
        "--check-files",
        action="store_true",
        help="检查图片存在性并使用 OpenCV 尝试解码",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        report = validate_manifest(
            args.manifest,
            args.data_root,
            args.schema,
            check_files=args.check_files,
        )
        if args.report is not None:
            write_report(report, args.report)
        print_summary(report)
        return EXIT_DATA_INVALID if report.error_count else EXIT_VALID
    except UsageError as exc:
        print(f"[USAGE_ERROR] {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    except Exception as exc:
        print(f"[INTERNAL_ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
