"""Shared, read-only helpers for external dataset governance."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Sequence

import cv2

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
EXTERNAL_SCHEMA_VERSION = "0.1"


class GovernanceUsageError(RuntimeError):
    """Raised when CLI inputs or governance configuration are unusable."""


def utc_now() -> str:
    """Return a stable ISO 8601 UTC timestamp for reports."""

    return datetime.now(UTC).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    """Read a JSON object with explicit UTF-8 handling."""

    if not path.is_file():
        raise GovernanceUsageError(f"JSON文件不存在：{path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GovernanceUsageError(f"无法读取JSON文件 {path}：{exc}") from exc
    if not isinstance(value, dict):
        raise GovernanceUsageError(f"JSON顶层必须是对象：{path}")
    return value


def write_json(path: Path, value: Any) -> None:
    """Write a human-readable UTF-8 JSON report."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    """Read a CSV as strings without changing the source file."""

    if not path.is_file():
        raise GovernanceUsageError(f"CSV文件不存在：{path}")
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            return fields, [dict(row) for row in reader]
    except (OSError, UnicodeError, csv.Error) as exc:
        raise GovernanceUsageError(f"无法读取CSV文件 {path}：{exc}") from exc


def write_csv_bom(
    path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, Any]]
) -> None:
    """Write WPS-compatible UTF-8 BOM CSV with deterministic columns."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(fieldnames),
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def sha256_file(path: Path) -> str:
    """Compute a file SHA-256 using bounded memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_id(prefix: str, *parts: str, length: int = 24) -> str:
    """Create a deterministic identifier without Python's randomized hash()."""

    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:length]}"


def relative_posix(path: Path, root: Path) -> str:
    """Return a root-relative POSIX path and reject escapes."""

    try:
        relative = path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise GovernanceUsageError(f"路径不在外部数据根目录内：{path}") from exc
    value = relative.as_posix()
    validate_relative_path(value)
    return value


def validate_relative_path(value: str) -> None:
    """Reject absolute, Windows, UNC and parent-traversal paths."""

    if not value:
        return
    posix = PurePosixPath(value.replace("\\", "/"))
    windows = PureWindowsPath(value)
    if (
        posix.is_absolute()
        or windows.is_absolute()
        or windows.drive
        or value.startswith(("\\\\", "//"))
        or ".." in posix.parts
    ):
        raise GovernanceUsageError(f"外部清单路径必须是安全相对路径：{value}")


def image_metadata(path: Path) -> tuple[int, int, int]:
    """Decode an image read-only and return width, height and channels."""

    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise ValueError(f"图片无法读取：{path}")
    height, width = image.shape[:2]
    channels = 1 if image.ndim == 2 else int(image.shape[2])
    return width, height, channels


def empty_manifest_record(fields: Sequence[str]) -> dict[str, Any]:
    """Create an empty row for every declared external schema field."""

    return {field: "" for field in fields}


def load_schema_fields(schema_path: Path) -> list[str]:
    """Load and validate the external schema's ordered field list."""

    schema = load_json(schema_path)
    fields = schema.get("fields")
    if (
        not isinstance(fields, list)
        or not fields
        or not all(isinstance(field, str) and field for field in fields)
    ):
        raise GovernanceUsageError("external schema fields必须是非空字符串数组。")
    if len(fields) != len(set(fields)):
        raise GovernanceUsageError("external schema fields存在重复字段。")
    forbidden = {
        "package_id",
        "sequence_id",
        "node_id",
        "capture_time",
        "first_abnormal_node",
    }
    present = sorted(forbidden.intersection(fields))
    if present:
        raise GovernanceUsageError(
            f"external schema包含内部业务字段：{', '.join(present)}"
        )
    return fields


def source_base_record(
    fields: Sequence[str], source_id: str, source: dict[str, Any]
) -> dict[str, Any]:
    """Build the common provenance portion of one manifest row."""

    row = empty_manifest_record(fields)
    row.update(
        {
            "external_schema_version": EXTERNAL_SCHEMA_VERSION,
            "source_id": source_id,
            "dataset_name": source.get("dataset_name", ""),
            "dataset_version": source.get("dataset_version", ""),
            "source_provider": source.get("provider", ""),
            "source_url": source.get("source_url", ""),
            "license_id": source.get("license_id", ""),
            "license_name": source.get("license_name", ""),
            "license_file_relpath": source.get("license_file_relpath", ""),
            "citation_file_relpath": source.get("citation_file_relpath", ""),
            "usage_scope": source.get("usage_scope", ""),
        }
    )
    return row
