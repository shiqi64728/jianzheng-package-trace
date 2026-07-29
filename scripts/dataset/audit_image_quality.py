"""只读审计“件证”试采集图片的可读性、尺寸、模糊、曝光和精确重复内容。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import traceback
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from statistics import fmean
from typing import Any, Sequence

import cv2
import numpy as np

if __package__:
    from .init_pilot_batch import BATCH_INFO_FIELDS
    from .validate_manifest import Issue as ManifestIssue
    from .validate_manifest import UsageError as ManifestUsageError
    from .validate_manifest import validate_manifest
else:
    from init_pilot_batch import BATCH_INFO_FIELDS
    from validate_manifest import Issue as ManifestIssue
    from validate_manifest import UsageError as ManifestUsageError
    from validate_manifest import validate_manifest

EXIT_VALID = 0
EXIT_DATA_INVALID = 1
EXIT_USAGE_ERROR = 2
EXIT_INTERNAL_ERROR = 3
TOOL_VERSION = "0.1.0"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = REPO_ROOT / "configs" / "training" / "manifest-schema-v0.1.json"
DEFAULT_QUALITY_CONFIG = REPO_ROOT / "configs" / "training" / "image-quality-v0.1.json"

QUALITY_STATUSES = {"PASS", "WARN", "FAIL"}
REPORT_CSV_FIELDS = (
    "record_id",
    "image_relpath",
    "sha256",
    "file_size_bytes",
    "width",
    "height",
    "channels",
    "aspect_ratio",
    "mean_gray",
    "std_gray",
    "laplacian_variance",
    "underexposed_ratio",
    "overexposed_ratio",
    "readable",
    "quality_status",
    "quality_flags",
    "quality_messages",
)

REQUIRED_CONFIG_KEYS = {
    "config_version",
    "description",
    "calibration_note",
    "min_width",
    "min_height",
    "allowed_aspect_ratio_min",
    "allowed_aspect_ratio_max",
    "blur_warn_below",
    "blur_fail_below",
    "underexposed_pixel_max",
    "overexposed_pixel_min",
    "mean_gray_warn_low",
    "mean_gray_warn_high",
    "underexposed_ratio_warn",
    "overexposed_ratio_warn",
    "duplicate_content_level",
    "resolution_outlier_level",
    "resolution_outlier_min_batch_size",
    "resolution_outlier_max_fraction",
    "low_resolution_level",
    "extreme_aspect_ratio_level",
    "possible_blur_level",
    "severe_blur_level",
    "underexposure_level",
    "overexposure_level",
}


class AuditUsageError(RuntimeError):
    """CLI、schema、配置或报告路径不可用。"""


@dataclass
class QualityRecord:
    """一张图片的只读质量指标和筛查结果。"""

    record_id: str
    image_relpath: str
    sha256: str | None = None
    file_size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    channels: int | None = None
    aspect_ratio: float | None = None
    mean_gray: float | None = None
    std_gray: float | None = None
    laplacian_variance: float | None = None
    underexposed_ratio: float | None = None
    overexposed_ratio: float | None = None
    readable: bool = False
    quality_status: str = "PASS"
    quality_flags: list[str] | None = None
    quality_messages: list[str] | None = None

    def __post_init__(self) -> None:
        if self.quality_flags is None:
            self.quality_flags = []
        if self.quality_messages is None:
            self.quality_messages = []

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DuplicateGroup:
    """一组原始字节 SHA-256 完全相同的不同清单记录。"""

    duplicate_group_id: str
    sha256: str
    record_ids: list[str]
    image_relpaths: list[str]


@dataclass(frozen=True)
class BatchIssue:
    """批次元数据的一条错误或警告。"""

    severity: str
    code: str
    message: str


@dataclass
class QualityReport:
    """完整批次质量报告。"""

    manifest_schema_version: str
    quality_config_version: str
    batch_status: str
    record_count: int
    pass_count: int
    warning_count: int
    fail_count: int
    readable_count: int
    unreadable_count: int
    duplicate_group_count: int
    resolution_groups: list[dict[str, Any]]
    brightness_summary: dict[str, float | int | None]
    blur_summary: dict[str, float | int | None]
    duplicate_groups: list[DuplicateGroup]
    records: list[QualityRecord]
    manifest_error_count: int
    manifest_warning_count: int
    manifest_issues: list[ManifestIssue]
    batch_info_status: str
    batch_info_issues: list[BatchIssue]

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_version": TOOL_VERSION,
            "manifest_schema_version": self.manifest_schema_version,
            "quality_config_version": self.quality_config_version,
            "generated_at": datetime.now(UTC).isoformat(),
            "batch_status": self.batch_status,
            "record_count": self.record_count,
            "pass_count": self.pass_count,
            "warning_count": self.warning_count,
            "fail_count": self.fail_count,
            "readable_count": self.readable_count,
            "unreadable_count": self.unreadable_count,
            "duplicate_group_count": self.duplicate_group_count,
            "resolution_groups": self.resolution_groups,
            "brightness_summary": self.brightness_summary,
            "blur_summary": self.blur_summary,
            "duplicate_groups": [asdict(group) for group in self.duplicate_groups],
            "manifest_validation": {
                "error_count": self.manifest_error_count,
                "warning_count": self.manifest_warning_count,
                "issues": [asdict(issue) for issue in self.manifest_issues],
            },
            "batch_info_validation": {
                "status": self.batch_info_status,
                "issues": [asdict(issue) for issue in self.batch_info_issues],
            },
            "privacy_and_permission_notice": (
                "隐私和授权字段是人工声明，不是图像质量工具自动识别结果。"
            ),
            "records": [record.to_dict() for record in self.records],
        }


def _require_number(
    config: dict[str, Any],
    key: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    value = config[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise AuditUsageError(f"质量配置 {key} 必须是数字。")
    number = float(value)
    if minimum is not None and number < minimum:
        raise AuditUsageError(f"质量配置 {key} 不得小于 {minimum}。")
    if maximum is not None and number > maximum:
        raise AuditUsageError(f"质量配置 {key} 不得大于 {maximum}。")
    return number


def _require_integer(
    config: dict[str, Any],
    key: str,
    *,
    minimum: int,
    maximum: int | None = None,
) -> int:
    value = config[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise AuditUsageError(f"质量配置 {key} 必须是整数。")
    if value < minimum or (maximum is not None and value > maximum):
        range_text = f"{minimum}—{maximum}" if maximum is not None else f">={minimum}"
        raise AuditUsageError(f"质量配置 {key} 必须位于 {range_text}。")
    return value


def load_quality_config(config_path: Path) -> dict[str, Any]:
    """读取并完整验证第一版质量阈值配置。"""

    if not config_path.is_file():
        raise AuditUsageError(f"图像质量配置不存在：{config_path}")
    try:
        with config_path.open("r", encoding="utf-8-sig") as handle:
            config = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AuditUsageError(f"无法读取图像质量配置 {config_path}：{exc}") from exc
    if not isinstance(config, dict):
        raise AuditUsageError("图像质量配置顶层必须是 JSON 对象。")
    missing = sorted(REQUIRED_CONFIG_KEYS - config.keys())
    if missing:
        raise AuditUsageError(f"图像质量配置缺少字段：{', '.join(missing)}")
    if config["config_version"] != "0.1":
        raise AuditUsageError("图像质量配置 config_version 必须为 0.1。")
    if (
        not isinstance(config["description"], str)
        or "第一版工程初始值" not in config["description"]
    ):
        raise AuditUsageError("质量配置 description 必须声明“第一版工程初始值”。")
    if (
        not isinstance(config["calibration_note"], str)
        or "20—50" not in config["calibration_note"]
    ):
        raise AuditUsageError("质量配置 calibration_note 必须声明 20—50 张校准要求。")

    _require_integer(config, "min_width", minimum=1)
    _require_integer(config, "min_height", minimum=1)
    aspect_min = _require_number(config, "allowed_aspect_ratio_min", minimum=0.01)
    aspect_max = _require_number(config, "allowed_aspect_ratio_max", minimum=0.01)
    if aspect_min >= aspect_max:
        raise AuditUsageError("allowed_aspect_ratio_min 必须小于 max。")
    blur_warn = _require_number(config, "blur_warn_below", minimum=0.0)
    blur_fail = _require_number(config, "blur_fail_below", minimum=0.0)
    if blur_fail > blur_warn:
        raise AuditUsageError("blur_fail_below 不得大于 blur_warn_below。")
    under_pixel = _require_integer(
        config, "underexposed_pixel_max", minimum=0, maximum=255
    )
    over_pixel = _require_integer(
        config, "overexposed_pixel_min", minimum=0, maximum=255
    )
    if under_pixel >= over_pixel:
        raise AuditUsageError("underexposed_pixel_max 必须小于 overexposed_pixel_min。")
    mean_low = _require_number(config, "mean_gray_warn_low", minimum=0, maximum=255)
    mean_high = _require_number(config, "mean_gray_warn_high", minimum=0, maximum=255)
    if mean_low >= mean_high:
        raise AuditUsageError("mean_gray_warn_low 必须小于 mean_gray_warn_high。")
    _require_number(config, "underexposed_ratio_warn", minimum=0.0, maximum=1.0)
    _require_number(config, "overexposed_ratio_warn", minimum=0.0, maximum=1.0)
    _require_integer(config, "resolution_outlier_min_batch_size", minimum=2)
    outlier_fraction = _require_number(
        config,
        "resolution_outlier_max_fraction",
        minimum=0.0,
        maximum=1.0,
    )
    if outlier_fraction == 0.0:
        raise AuditUsageError("resolution_outlier_max_fraction 必须大于 0。")

    for key in (
        "duplicate_content_level",
        "resolution_outlier_level",
        "low_resolution_level",
        "extreme_aspect_ratio_level",
        "possible_blur_level",
        "severe_blur_level",
        "underexposure_level",
        "overexposure_level",
    ):
        if config[key] not in {"WARN", "FAIL"}:
            raise AuditUsageError(f"质量配置 {key} 只能是 WARN 或 FAIL。")
    if config["low_resolution_level"] != "FAIL":
        raise AuditUsageError("low_resolution_level 必须为 FAIL。")
    return config


def _read_manifest_rows(manifest_path: Path) -> list[dict[str, str]]:
    """在第一轮验证通过后读取记录；这里不重复字段、枚举或路径校验。"""

    try:
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            return [
                {
                    str(key): "" if value is None else str(value).strip()
                    for key, value in row.items()
                }
                for row in reader
            ]
    except (OSError, UnicodeError, csv.Error) as exc:
        raise AuditUsageError(f"第一轮验证后重新读取 manifest 失败：{exc}") from exc


def _audit_batch_info(
    data_root: Path,
    rows: list[dict[str, str]],
) -> list[BatchIssue]:
    """检查批次元数据完整性；不尝试识别图片中的隐私或授权事实。"""

    batch_info_path = data_root / "batch-info.json"
    if not batch_info_path.is_file():
        return [
            BatchIssue(
                "error",
                "BATCH_INFO_MISSING",
                "批次根目录缺少 batch-info.json。",
            )
        ]
    try:
        with batch_info_path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [
            BatchIssue(
                "error",
                "BATCH_INFO_UNREADABLE",
                f"无法读取 batch-info.json：{exc}",
            )
        ]
    if not isinstance(payload, dict):
        return [
            BatchIssue(
                "error",
                "BATCH_INFO_INVALID",
                "batch-info.json 顶层必须是 JSON 对象。",
            )
        ]

    issues: list[BatchIssue] = []
    missing_fields = [field for field in BATCH_INFO_FIELDS if field not in payload]
    if missing_fields:
        issues.append(
            BatchIssue(
                "error",
                "BATCH_INFO_FIELDS_MISSING",
                f"batch-info.json 缺少字段：{', '.join(missing_fields)}。",
            )
        )

    required_values = (
        "batch_schema_version",
        "manifest_schema_version",
        "batch_id",
        "source_type",
        "collector",
        "device_id",
        "created_at",
        "purpose",
        "location_type",
        "permission_status",
        "privacy_method",
    )
    empty_required = [
        field for field in required_values if not str(payload.get(field, "")).strip()
    ]
    if empty_required:
        issues.append(
            BatchIssue(
                "error",
                "BATCH_INFO_REQUIRED_VALUES_MISSING",
                f"batch-info.json 必填值为空：{', '.join(empty_required)}。",
            )
        )

    capture_fields = (
        "camera_or_phone_model",
        "lens",
        "resolution_setting",
        "aspect_ratio_setting",
        "hdr_status",
        "filter_status",
        "lighting",
        "background",
    )
    incomplete_capture = [
        field
        for field in capture_fields
        if str(payload.get(field, "")).strip().casefold() in {"", "unknown", "pending"}
    ]
    if incomplete_capture:
        issues.append(
            BatchIssue(
                "warning",
                "BATCH_CAPTURE_METADATA_INCOMPLETE",
                f"拍摄参数尚未完整记录：{', '.join(incomplete_capture)}。",
            )
        )

    created_at = str(payload.get("created_at", "")).strip()
    if created_at:
        try:
            parsed_time = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            parsed_time = None
        if (
            parsed_time is None
            or parsed_time.tzinfo is None
            or parsed_time.utcoffset() is None
        ):
            issues.append(
                BatchIssue(
                    "error",
                    "BATCH_CREATED_AT_INVALID",
                    "batch-info.json 的 created_at 必须是包含时区的 ISO 8601 时间。",
                )
            )

    if payload.get("manifest_schema_version") != "0.1":
        issues.append(
            BatchIssue(
                "error",
                "BATCH_MANIFEST_SCHEMA_MISMATCH",
                "batch-info.json 的 manifest_schema_version 必须为 0.1。",
            )
        )
    if payload.get("permission_status") == "pending":
        issues.append(
            BatchIssue(
                "warning",
                "PERMISSION_STATUS_PENDING",
                "permission_status 仍为 pending；该值是人工声明，必须人工复核。",
            )
        )
    if payload.get("privacy_method") == "pending_manual_review":
        issues.append(
            BatchIssue(
                "warning",
                "PRIVACY_REVIEW_PENDING",
                "privacy_method 仍为 pending_manual_review；工具不会自动判断是否脱敏。",
            )
        )

    manifest_matches = {
        "batch_id": {row.get("batch_id", "") for row in rows},
        "source_type": {row.get("source_type", "") for row in rows},
        "collector": {row.get("collector", "") for row in rows},
        "device_id": {row.get("device_id", "") for row in rows},
    }
    mismatches = [
        field
        for field, values in manifest_matches.items()
        if values and values != {str(payload.get(field, ""))}
    ]
    if mismatches:
        issues.append(
            BatchIssue(
                "error",
                "BATCH_MANIFEST_METADATA_MISMATCH",
                (
                    "manifest 与 batch-info.json 的批次级字段不一致或同批次出现多个值："
                    f"{', '.join(mismatches)}。"
                ),
            )
        )
    return issues


def _apply_flag(
    record: QualityRecord,
    flag: str,
    level: str,
    message: str,
) -> None:
    if record.quality_flags is None or record.quality_messages is None:
        raise RuntimeError("质量记录列表未初始化。")
    if flag not in record.quality_flags:
        record.quality_flags.append(flag)
        record.quality_messages.append(message)
    if level == "FAIL":
        record.quality_status = "FAIL"
    elif level == "WARN" and record.quality_status == "PASS":
        record.quality_status = "WARN"


def _unreadable_record(
    record: QualityRecord,
    message: str,
) -> QualityRecord:
    _apply_flag(record, "UNREADABLE_IMAGE", "FAIL", message)
    return record


def _decode_and_measure(
    *,
    record_id: str,
    image_relpath: str,
    image_path: Path,
    config: dict[str, Any],
) -> QualityRecord:
    record = QualityRecord(record_id=record_id, image_relpath=image_relpath)
    if not image_path.exists():
        return _unreadable_record(record, "图片不存在，无法进行质量审计。")
    if not image_path.is_file():
        return _unreadable_record(record, "图片路径不是普通文件。")
    try:
        image_bytes = image_path.read_bytes()
    except OSError as exc:
        return _unreadable_record(record, f"无法读取图片文件：{exc}")

    record.file_size_bytes = len(image_bytes)
    record.sha256 = hashlib.sha256(image_bytes).hexdigest()
    if not image_bytes:
        return _unreadable_record(record, "图片文件为 0 字节。")
    try:
        encoded = np.frombuffer(image_bytes, dtype=np.uint8)
        image = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    except cv2.error as exc:
        return _unreadable_record(record, f"OpenCV 解码图片时出错：{exc}")
    if image is None or image.size == 0:
        return _unreadable_record(record, "文件存在，但 OpenCV 无法解码。")
    if image.ndim == 2:
        channels = 1
    elif image.ndim == 3:
        channels = int(image.shape[2])
    else:
        return _unreadable_record(record, f"图片数组维度不合理：{image.ndim}。")
    if channels not in {1, 3, 4}:
        return _unreadable_record(record, f"图片通道数不合理：{channels}。")

    height, width = int(image.shape[0]), int(image.shape[1])
    if width <= 0 or height <= 0:
        return _unreadable_record(record, "图片宽高必须大于 0。")
    try:
        if channels == 1:
            gray = image
        elif channels == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
    except cv2.error as exc:
        return _unreadable_record(record, f"OpenCV 灰度转换失败：{exc}")
    if gray.size == 0:
        return _unreadable_record(record, "灰度图数组为空。")

    if gray.dtype != np.uint8:
        try:
            gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        except cv2.error as exc:
            return _unreadable_record(record, f"灰度范围归一化失败：{exc}")

    record.readable = True
    record.width = width
    record.height = height
    record.channels = channels
    record.aspect_ratio = round(width / height, 6)
    record.mean_gray = round(float(np.mean(gray)), 6)
    record.std_gray = round(float(np.std(gray)), 6)
    try:
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    except cv2.error as exc:
        return _unreadable_record(record, f"OpenCV Laplacian 计算失败：{exc}")
    record.laplacian_variance = round(float(laplacian.var()), 6)
    record.underexposed_ratio = round(
        float(np.mean(gray <= config["underexposed_pixel_max"])), 6
    )
    record.overexposed_ratio = round(
        float(np.mean(gray >= config["overexposed_pixel_min"])), 6
    )

    if width < config["min_width"] or height < config["min_height"]:
        _apply_flag(
            record,
            "LOW_RESOLUTION",
            config["low_resolution_level"],
            (
                f"分辨率 {width}×{height} 低于工程初始最低值 "
                f"{config['min_width']}×{config['min_height']}。"
            ),
        )
    if (
        record.aspect_ratio < config["allowed_aspect_ratio_min"]
        or record.aspect_ratio > config["allowed_aspect_ratio_max"]
    ):
        _apply_flag(
            record,
            "EXTREME_ASPECT_RATIO",
            config["extreme_aspect_ratio_level"],
            f"长宽比 {record.aspect_ratio} 位于工程初始允许范围之外。",
        )
    if record.laplacian_variance < config["blur_fail_below"]:
        _apply_flag(
            record,
            "SEVERE_BLUR",
            config["severe_blur_level"],
            (
                f"Laplacian 方差 {record.laplacian_variance} 低于严重模糊筛查值；"
                "纯色纸箱也可能天然低分，必须人工复核。"
            ),
        )
    elif record.laplacian_variance < config["blur_warn_below"]:
        _apply_flag(
            record,
            "POSSIBLE_BLUR",
            config["possible_blur_level"],
            (
                f"Laplacian 方差 {record.laplacian_variance} 低于模糊候选筛查值；"
                "该指标不是最终人工结论。"
            ),
        )
    if (
        record.mean_gray < config["mean_gray_warn_low"]
        or record.underexposed_ratio >= config["underexposed_ratio_warn"]
    ):
        _apply_flag(
            record,
            "POSSIBLE_UNDEREXPOSURE",
            config["underexposure_level"],
            "灰度均值或暗像素比例触发欠曝候选；深色纸箱不等于拍摄错误。",
        )
    if (
        record.mean_gray > config["mean_gray_warn_high"]
        or record.overexposed_ratio >= config["overexposed_ratio_warn"]
    ):
        _apply_flag(
            record,
            "POSSIBLE_OVEREXPOSURE",
            config["overexposure_level"],
            "灰度均值或亮像素比例触发过曝候选，必须结合原图人工查看。",
        )
    return record


def _apply_duplicate_flags(
    records: list[QualityRecord],
    config: dict[str, Any],
) -> list[DuplicateGroup]:
    groups_by_hash: dict[str, list[QualityRecord]] = defaultdict(list)
    for record in records:
        if record.sha256 is not None and record.file_size_bytes:
            groups_by_hash[record.sha256].append(record)

    duplicate_groups: list[DuplicateGroup] = []
    duplicate_index = 0
    for digest in sorted(groups_by_hash):
        group = groups_by_hash[digest]
        distinct_paths = {record.image_relpath for record in group}
        distinct_ids = {record.record_id for record in group}
        if len(distinct_paths) < 2 or len(distinct_ids) < 2:
            continue
        duplicate_index += 1
        group_id = f"DUP-{duplicate_index:04d}"
        ordered = sorted(group, key=lambda item: (item.record_id, item.image_relpath))
        duplicate_groups.append(
            DuplicateGroup(
                duplicate_group_id=group_id,
                sha256=digest,
                record_ids=[record.record_id for record in ordered],
                image_relpaths=[record.image_relpath for record in ordered],
            )
        )
        for record in ordered:
            _apply_flag(
                record,
                "DUPLICATE_CONTENT",
                config["duplicate_content_level"],
                f"原始文件字节与重复组 {group_id} 中其他文件完全相同。",
            )
    return duplicate_groups


def _apply_resolution_outliers(
    records: list[QualityRecord],
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    readable_records = [
        record
        for record in records
        if record.readable and record.width is not None and record.height is not None
    ]
    counts: Counter[tuple[int, int]] = Counter(
        (int(record.width), int(record.height)) for record in readable_records
    )
    ordered_groups = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    resolution_groups = [
        {"width": size[0], "height": size[1], "count": count}
        for size, count in ordered_groups
    ]
    if len(readable_records) < config["resolution_outlier_min_batch_size"]:
        return resolution_groups

    common_size = ordered_groups[0][0] if ordered_groups else None
    total = len(readable_records)
    outlier_sizes = {
        size
        for size, count in ordered_groups
        if size != common_size
        and count / total <= config["resolution_outlier_max_fraction"]
    }
    for record in readable_records:
        size = (int(record.width), int(record.height))
        if size in outlier_sizes:
            _apply_flag(
                record,
                "RESOLUTION_OUTLIER",
                config["resolution_outlier_level"],
                "该尺寸在本批次中属于少数分辨率，建议人工确认拍摄参数是否一致。",
            )
    return resolution_groups


def _numeric_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None}
    return {
        "count": len(values),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "mean": round(fmean(values), 6),
    }


def _build_report(
    *,
    records: list[QualityRecord],
    manifest_schema_version: str,
    quality_config_version: str,
    manifest_issues: list[ManifestIssue],
    manifest_record_count: int,
    batch_info_issues: list[BatchIssue] | None = None,
    duplicate_groups: list[DuplicateGroup] | None = None,
    resolution_groups: list[dict[str, Any]] | None = None,
) -> QualityReport:
    batch_info_issues = batch_info_issues or []
    duplicate_groups = duplicate_groups or []
    resolution_groups = resolution_groups or []
    manifest_error_count = sum(issue.severity == "error" for issue in manifest_issues)
    manifest_warning_count = sum(
        issue.severity == "warning" for issue in manifest_issues
    )
    pass_count = sum(record.quality_status == "PASS" for record in records)
    warning_count = sum(record.quality_status == "WARN" for record in records)
    fail_count = sum(record.quality_status == "FAIL" for record in records)
    readable_count = sum(record.readable for record in records)
    unreadable_count = len(records) - readable_count
    batch_info_error_count = sum(
        issue.severity == "error" for issue in batch_info_issues
    )
    batch_info_warning_count = sum(
        issue.severity == "warning" for issue in batch_info_issues
    )
    if manifest_error_count or batch_info_error_count or fail_count:
        batch_status = "FAIL"
    elif warning_count or manifest_warning_count or batch_info_warning_count:
        batch_status = "PASS_WITH_WARNINGS"
    else:
        batch_status = "PASS"

    brightness_values = [
        float(record.mean_gray) for record in records if record.mean_gray is not None
    ]
    blur_values = [
        float(record.laplacian_variance)
        for record in records
        if record.laplacian_variance is not None
    ]
    return QualityReport(
        manifest_schema_version=manifest_schema_version,
        quality_config_version=quality_config_version,
        batch_status=batch_status,
        record_count=manifest_record_count,
        pass_count=pass_count,
        warning_count=warning_count,
        fail_count=fail_count,
        readable_count=readable_count,
        unreadable_count=unreadable_count,
        duplicate_group_count=len(duplicate_groups),
        resolution_groups=resolution_groups,
        brightness_summary=_numeric_summary(brightness_values),
        blur_summary=_numeric_summary(blur_values),
        duplicate_groups=duplicate_groups,
        records=records,
        manifest_error_count=manifest_error_count,
        manifest_warning_count=manifest_warning_count,
        manifest_issues=manifest_issues,
        batch_info_status=(
            "FAIL"
            if batch_info_error_count
            else "WARN"
            if batch_info_warning_count
            else "PASS"
        ),
        batch_info_issues=batch_info_issues,
    )


def audit_manifest_images(
    *,
    manifest_path: Path,
    data_root: Path,
    schema_path: Path,
    quality_config_path: Path,
    check_files: bool,
) -> QualityReport:
    """复用第一轮结构校验后，只读计算图片质量指标。"""

    if not check_files:
        raise AuditUsageError(
            "图像质量审计必须显式提供 --check-files；未授权读取图片时请只运行第一轮校验器。"
        )
    config = load_quality_config(quality_config_path.resolve())
    try:
        structure_report = validate_manifest(
            manifest_path.resolve(),
            data_root.resolve(),
            schema_path.resolve(),
            check_files=False,
        )
    except ManifestUsageError as exc:
        raise AuditUsageError(str(exc)) from exc

    if structure_report.error_count:
        batch_info_issues = _audit_batch_info(data_root.resolve(), [])
        return _build_report(
            records=[],
            manifest_schema_version=structure_report.schema_version,
            quality_config_version=str(config["config_version"]),
            manifest_issues=structure_report.issues,
            manifest_record_count=structure_report.total_records,
            batch_info_issues=batch_info_issues,
        )

    rows = _read_manifest_rows(manifest_path.resolve())
    batch_info_issues = _audit_batch_info(data_root.resolve(), rows)
    records: list[QualityRecord] = []
    root = data_root.resolve()
    for row in rows:
        image_relpath = row["image_relpath"]
        image_path = root.joinpath(*PurePosixPath(image_relpath).parts)
        records.append(
            _decode_and_measure(
                record_id=row["record_id"],
                image_relpath=image_relpath,
                image_path=image_path,
                config=config,
            )
        )

    duplicate_groups = _apply_duplicate_flags(records, config)
    resolution_groups = _apply_resolution_outliers(records, config)
    return _build_report(
        records=records,
        manifest_schema_version=structure_report.schema_version,
        quality_config_version=str(config["config_version"]),
        manifest_issues=structure_report.issues,
        manifest_record_count=structure_report.total_records,
        batch_info_issues=batch_info_issues,
        duplicate_groups=duplicate_groups,
        resolution_groups=resolution_groups,
    )


def _validate_report_paths(
    *,
    report_json: Path,
    report_csv: Path,
    protected_paths: Sequence[Path],
) -> None:
    json_resolved = report_json.resolve()
    csv_resolved = report_csv.resolve()
    if json_resolved == csv_resolved:
        raise AuditUsageError("report-json 与 report-csv 不得指向同一个文件。")
    protected = {path.resolve() for path in protected_paths}
    if json_resolved in protected or csv_resolved in protected:
        raise AuditUsageError("报告路径不得覆盖 manifest、schema、配置或原始图片。")


def write_json_report(report: QualityReport, report_path: Path) -> None:
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(report.to_dict(), handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    except OSError as exc:
        raise AuditUsageError(f"无法写入 JSON 报告 {report_path}：{exc}") from exc


def write_csv_report(report: QualityReport, report_path: Path) -> None:
    try:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REPORT_CSV_FIELDS)
            writer.writeheader()
            for record in report.records:
                row = record.to_dict()
                row["quality_flags"] = "|".join(record.quality_flags or [])
                row["quality_messages"] = "；".join(record.quality_messages or [])
                writer.writerow({field: row.get(field) for field in REPORT_CSV_FIELDS})
    except OSError as exc:
        raise AuditUsageError(f"无法写入 CSV 报告 {report_path}：{exc}") from exc


def print_summary(
    report: QualityReport,
    report_json: Path,
    report_csv: Path,
) -> None:
    common_resolution = "无"
    if report.resolution_groups:
        first = report.resolution_groups[0]
        common_resolution = f"{first['width']}×{first['height']}（{first['count']}张）"
    print(f"批次状态：{report.batch_status}")
    print(f"总图片数：{report.record_count}")
    print(f"通过数：{report.pass_count}")
    print(f"警告数：{report.warning_count}")
    print(f"失败数：{report.fail_count}")
    print(f"不可读数：{report.unreadable_count}")
    print(f"重复内容组数：{report.duplicate_group_count}")
    print(f"最常见分辨率：{common_resolution}")
    print(f"JSON 报告：{report_json}")
    print(f"CSV 报告：{report_csv}")
    if report.manifest_error_count:
        print(f"第一轮 manifest 结构错误：{report.manifest_error_count}")
    print(f"批次元数据状态：{report.batch_info_status}")
    for issue in report.batch_info_issues:
        print(f"[{issue.severity.upper()}] {issue.code}：{issue.message}")
    print("隐私和授权字段是人工声明，不是图像质量工具自动识别结果。")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="复用数据合同 v0.1，只读审计试采集图片质量并输出 JSON/CSV 报告。"
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument(
        "--quality-config",
        type=Path,
        default=DEFAULT_QUALITY_CONFIG,
    )
    parser.add_argument("--report-json", type=Path, required=True)
    parser.add_argument("--report-csv", type=Path, required=True)
    parser.add_argument(
        "--check-files",
        action="store_true",
        help="显式允许只读打开清单引用的图片；质量审计必须提供此参数",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = audit_manifest_images(
            manifest_path=args.manifest,
            data_root=args.data_root,
            schema_path=args.schema,
            quality_config_path=args.quality_config,
            check_files=args.check_files,
        )
        image_paths = [
            args.data_root.joinpath(*PurePosixPath(record.image_relpath).parts)
            for record in report.records
        ]
        _validate_report_paths(
            report_json=args.report_json,
            report_csv=args.report_csv,
            protected_paths=[
                args.manifest,
                args.schema,
                args.quality_config,
                *image_paths,
            ],
        )
        write_json_report(report, args.report_json)
        write_csv_report(report, args.report_csv)
        print_summary(report, args.report_json, args.report_csv)
        return EXIT_DATA_INVALID if report.batch_status == "FAIL" else EXIT_VALID
    except AuditUsageError as exc:
        print(f"[USAGE_ERROR] {exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    except Exception as exc:
        print(f"[INTERNAL_ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
