"""初始化“件证”试采集批次目录，不覆盖任何既有批次或文件。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import traceback
from datetime import datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Sequence

if __package__:
    from .validate_manifest import UsageError as ManifestUsageError
    from .validate_manifest import load_schema
else:
    from validate_manifest import UsageError as ManifestUsageError
    from validate_manifest import load_schema

EXIT_SUCCESS = 0
EXIT_INPUT_ERROR = 1
EXIT_CONFIG_ERROR = 2
EXIT_INTERNAL_ERROR = 3
BATCH_SCHEMA_VERSION = "0.1"
MANIFEST_SCHEMA_VERSION = "0.1"

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SCHEMA = REPO_ROOT / "configs" / "training" / "manifest-schema-v0.1.json"
DEFAULT_TEMPLATE = (
    REPO_ROOT / "dataset" / "manifests" / "templates" / "manifest-v0.1.template.csv"
)

BATCH_INFO_FIELDS = (
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
    "camera_or_phone_model",
    "lens",
    "resolution_setting",
    "aspect_ratio_setting",
    "hdr_status",
    "filter_status",
    "lighting",
    "background",
    "notes",
)

SUBDIRECTORIES = ("images", "annotations", "setup_photos", "reports")


class BatchInputError(RuntimeError):
    """用户输入或同名批次冲突。"""


class BatchConfigError(RuntimeError):
    """第一轮 schema 或模板不可用。"""


def _validate_identifier(
    value: str,
    field: str,
    schema: dict[str, Any],
) -> None:
    pattern = schema["identifier_patterns"].get(field)
    if not isinstance(pattern, str) or re.fullmatch(pattern, value) is None:
        raise BatchInputError(
            f"{field} 格式无效；只能使用以字母或数字开头的字母、数字、点、"
            "下划线或连字符，最长 128 个字符。"
        )


def _validate_batch_id(batch_id: str, schema: dict[str, Any]) -> None:
    if not batch_id:
        raise BatchInputError("batch_id 不能为空。")
    if ".." in batch_id:
        raise BatchInputError("batch_id 不得包含“..”。")
    if "/" in batch_id or "\\" in batch_id:
        raise BatchInputError("batch_id 不得包含路径分隔符。")
    windows_path = PureWindowsPath(batch_id)
    posix_path = PurePosixPath(batch_id)
    if (
        windows_path.is_absolute()
        or bool(windows_path.drive)
        or posix_path.is_absolute()
        or batch_id.startswith(("//", "\\\\"))
    ):
        raise BatchInputError("batch_id 不得是绝对路径、盘符路径或 UNC 路径。")
    _validate_identifier(batch_id, "batch_id", schema)


def _load_and_validate_template(
    template_path: Path,
    schema: dict[str, Any],
) -> bytes:
    if not template_path.is_file():
        raise BatchConfigError(f"第一轮 manifest 模板不存在：{template_path}")
    try:
        template_bytes = template_path.read_bytes()
    except OSError as exc:
        raise BatchConfigError(f"无法读取第一轮 manifest 模板：{exc}") from exc
    if not template_bytes.startswith(b"\xef\xbb\xbf"):
        raise BatchConfigError("第一轮 manifest 模板必须使用 UTF-8 BOM。")
    try:
        text = template_bytes.decode("utf-8-sig")
        rows = list(csv.reader(text.splitlines(), strict=True))
    except (UnicodeError, csv.Error) as exc:
        raise BatchConfigError(f"第一轮 manifest 模板无法解析：{exc}") from exc
    if len(rows) != 1:
        raise BatchConfigError("第一轮 manifest 模板必须只有表头，不能包含数据记录。")
    if rows[0] != list(schema["fields"]):
        raise BatchConfigError(
            "第一轮 manifest 模板表头与 schema 的 21 字段顺序不一致。"
        )
    return template_bytes


def _write_text(path: Path, content: str, created_paths: list[Path]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    created_paths.append(path)


def _write_bytes(path: Path, content: bytes, created_paths: list[Path]) -> None:
    with path.open("xb") as handle:
        handle.write(content)
    created_paths.append(path)


def _cleanup_created_paths(created_paths: list[Path]) -> list[str]:
    """只删除本次明确创建的文件和空目录；绝不递归删除。"""

    cleanup_errors: list[str] = []
    for path in reversed(created_paths):
        try:
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                path.rmdir()
        except OSError as exc:
            cleanup_errors.append(f"{path}: {exc}")
    return cleanup_errors


def _build_readme(batch_id: str) -> str:
    return (
        "件证项目试采集批次说明\n"
        "========================\n\n"
        f"批次 ID：{batch_id}\n\n"
        "1. 原始测试图片仅放入 images/，不要裁剪、重编码或覆盖原图。\n"
        "2. manifest.csv 继承数据合同 v0.1，仅填写真实存在的图片记录。\n"
        "3. setup_photos/ 仅放置完全脱敏的布置参考图，不得包含人员或站点信息。\n"
        "4. reports/ 用于保存 manifest 校验和图像质量审计报告。\n"
        "5. privacy_status 与 permission_status 必须由人工填写并复核。\n"
        "6. 不得写入姓名、手机号、详细地址、运单号、Token、Cookie 或其他凭据。\n"
        "7. 自动质量审计不能证明图片已完全脱敏，也不能代替授权核验。\n"
    )


def _build_batch_info(
    *,
    batch_id: str,
    source_type: str,
    collector: str,
    device_id: str,
    permission_status: str,
    purpose: str,
    location_type: str,
    privacy_method: str,
    camera_or_phone_model: str,
    lens: str,
    resolution_setting: str,
    aspect_ratio_setting: str,
    hdr_status: str,
    filter_status: str,
    lighting: str,
    background: str,
    notes: str,
) -> dict[str, str]:
    return {
        "batch_schema_version": BATCH_SCHEMA_VERSION,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "batch_id": batch_id,
        "source_type": source_type,
        "collector": collector,
        "device_id": device_id,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "purpose": purpose,
        "location_type": location_type,
        "permission_status": permission_status,
        "privacy_method": privacy_method,
        "camera_or_phone_model": camera_or_phone_model,
        "lens": lens,
        "resolution_setting": resolution_setting,
        "aspect_ratio_setting": aspect_ratio_setting,
        "hdr_status": hdr_status,
        "filter_status": filter_status,
        "lighting": lighting,
        "background": background,
        "notes": notes,
    }


def initialize_pilot_batch(
    *,
    output_root: Path,
    batch_id: str,
    source_type: str,
    collector: str,
    device_id: str,
    schema_path: Path = DEFAULT_SCHEMA,
    template_path: Path = DEFAULT_TEMPLATE,
    permission_status: str = "pending",
    purpose: str = "试采集图像质量审计与采集流程验证",
    location_type: str = "self_controlled_non_station",
    privacy_method: str = "pending_manual_review",
    camera_or_phone_model: str = "",
    lens: str = "",
    resolution_setting: str = "",
    aspect_ratio_setting: str = "",
    hdr_status: str = "unknown",
    filter_status: str = "unknown",
    lighting: str = "",
    background: str = "",
    notes: str = "",
) -> Path:
    """在明确的 output_root 内创建一个全新的批次并返回其路径。"""

    if not output_root.is_absolute():
        raise BatchInputError("output-root 必须是明确的绝对目录。")
    if not output_root.is_dir():
        raise BatchInputError(f"output-root 不存在或不是目录：{output_root}")

    try:
        schema = load_schema(schema_path.resolve())
    except ManifestUsageError as exc:
        raise BatchConfigError(str(exc)) from exc
    if schema.get("schema_version") != MANIFEST_SCHEMA_VERSION:
        raise BatchConfigError(
            f"manifest schema 必须为 {MANIFEST_SCHEMA_VERSION}，"
            f"实际为 {schema.get('schema_version')!r}。"
        )

    _validate_batch_id(batch_id, schema)
    _validate_identifier(collector, "collector", schema)
    _validate_identifier(device_id, "device_id", schema)
    allowed_source_types = schema["enums"]["source_type"]
    if source_type not in allowed_source_types:
        raise BatchInputError(
            f"source_type 无效；允许值：{', '.join(allowed_source_types)}。"
        )
    allowed_permission_statuses = {"pending", "approved", "not_required", "rejected"}
    if permission_status not in allowed_permission_statuses:
        raise BatchInputError(
            "permission_status 无效；允许值：pending、approved、not_required、rejected。"
        )

    template_bytes = _load_and_validate_template(template_path.resolve(), schema)
    root_resolved = output_root.resolve()
    batch_dir = root_resolved / batch_id
    try:
        batch_dir.resolve(strict=False).relative_to(root_resolved)
    except (OSError, ValueError) as exc:
        raise BatchInputError("batch_id 解析后超出 output-root。") from exc
    if batch_dir.exists():
        raise BatchInputError(f"同名批次已经存在，拒绝覆盖：{batch_dir}")

    created_paths: list[Path] = []
    try:
        batch_dir.mkdir()
        created_paths.append(batch_dir)
        for directory_name in SUBDIRECTORIES:
            directory = batch_dir / directory_name
            directory.mkdir()
            created_paths.append(directory)

        manifest_path = batch_dir / "manifest.csv"
        _write_bytes(manifest_path, template_bytes, created_paths)

        batch_info = _build_batch_info(
            batch_id=batch_id,
            source_type=source_type,
            collector=collector,
            device_id=device_id,
            permission_status=permission_status,
            purpose=purpose,
            location_type=location_type,
            privacy_method=privacy_method,
            camera_or_phone_model=camera_or_phone_model,
            lens=lens,
            resolution_setting=resolution_setting,
            aspect_ratio_setting=aspect_ratio_setting,
            hdr_status=hdr_status,
            filter_status=filter_status,
            lighting=lighting,
            background=background,
            notes=notes,
        )
        if tuple(batch_info) != BATCH_INFO_FIELDS:
            raise RuntimeError("batch-info 字段顺序与稳定接口定义不一致。")
        batch_info_path = batch_dir / "batch-info.json"
        _write_text(
            batch_info_path,
            json.dumps(batch_info, ensure_ascii=False, indent=2) + "\n",
            created_paths,
        )

        readme_path = batch_dir / "README-COLLECTION.txt"
        _write_text(readme_path, _build_readme(batch_id), created_paths)

        hash_lines: list[str] = []
        for path in (manifest_path, batch_info_path, readme_path):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            hash_lines.append(f"{digest} *{path.name}")
        _write_text(
            batch_dir / "SHA256SUMS.txt",
            "\n".join(hash_lines) + "\n",
            created_paths,
        )
    except Exception as exc:
        cleanup_errors = _cleanup_created_paths(created_paths)
        if cleanup_errors:
            detail = "；".join(cleanup_errors)
            raise RuntimeError(
                f"批次初始化失败，且部分本次创建的空结构无法清理：{detail}"
            ) from exc
        raise

    return batch_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="在明确的输出根目录内初始化件证试采集批次；默认拒绝覆盖。"
    )
    parser.add_argument(
        "--output-root", type=Path, required=True, help="批次输出根目录"
    )
    parser.add_argument("--batch-id", required=True, help="批次稳定 ID")
    parser.add_argument("--source-type", required=True, help="数据来源类型")
    parser.add_argument(
        "--collector", required=True, help="采集成员稳定 ID，不要填写姓名"
    )
    parser.add_argument("--device-id", required=True, help="设备稳定 ID")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--template", type=Path, default=DEFAULT_TEMPLATE)
    parser.add_argument("--permission-status", default="pending")
    parser.add_argument("--purpose", default="试采集图像质量审计与采集流程验证")
    parser.add_argument("--location-type", default="self_controlled_non_station")
    parser.add_argument("--privacy-method", default="pending_manual_review")
    parser.add_argument("--camera-or-phone-model", default="")
    parser.add_argument("--lens", default="")
    parser.add_argument("--resolution-setting", default="")
    parser.add_argument("--aspect-ratio-setting", default="")
    parser.add_argument("--hdr-status", default="unknown")
    parser.add_argument("--filter-status", default="unknown")
    parser.add_argument("--lighting", default="")
    parser.add_argument("--background", default="")
    parser.add_argument("--notes", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        batch_dir = initialize_pilot_batch(
            output_root=args.output_root,
            batch_id=args.batch_id,
            source_type=args.source_type,
            collector=args.collector,
            device_id=args.device_id,
            schema_path=args.schema,
            template_path=args.template,
            permission_status=args.permission_status,
            purpose=args.purpose,
            location_type=args.location_type,
            privacy_method=args.privacy_method,
            camera_or_phone_model=args.camera_or_phone_model,
            lens=args.lens,
            resolution_setting=args.resolution_setting,
            aspect_ratio_setting=args.aspect_ratio_setting,
            hdr_status=args.hdr_status,
            filter_status=args.filter_status,
            lighting=args.lighting,
            background=args.background,
            notes=args.notes,
        )
        print(f"批次初始化成功：{batch_dir}")
        print("manifest.csv 已从数据合同 v0.1 模板生成，仅包含 UTF-8 BOM 表头。")
        print("permission_status 来自人工输入；默认值为 pending，不代表已经授权。")
        return EXIT_SUCCESS
    except BatchInputError as exc:
        print(f"[INPUT_ERROR] {exc}", file=sys.stderr)
        return EXIT_INPUT_ERROR
    except BatchConfigError as exc:
        print(f"[CONFIG_ERROR] {exc}", file=sys.stderr)
        return EXIT_CONFIG_ERROR
    except Exception as exc:
        print(f"[INTERNAL_ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
