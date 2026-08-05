"""Validate the external source registry without modifying it or using network access."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.dataset.external_data_common import (
    GovernanceUsageError,
    load_json,
    read_csv,
    utc_now,
    write_json,
)

EXIT_VALID = 0
EXIT_DATA_INVALID = 1
EXIT_USAGE_ERROR = 2
EXIT_INTERNAL_ERROR = 3
VALIDATOR_VERSION = "0.1.0"


@dataclass(frozen=True)
class RegistryIssue:
    """One registry validation observation."""

    severity: str
    code: str
    message: str
    source_id: str = ""
    row_number: int | None = None


def _source_id(row: dict[str, str]) -> str:
    return (row.get("source_id") or row.get("dataset_id") or "").strip()


def _find_license_file(licenses_dir: Path, license_name: str) -> Path | None:
    normalized = "".join(char.lower() for char in license_name if char.isalnum())
    for path in sorted(licenses_dir.glob("*")):
        candidate = "".join(char.lower() for char in path.stem if char.isalnum())
        if normalized and (normalized in candidate or candidate in normalized):
            return path
    if normalized == "ccby40":
        matches = sorted(licenses_dir.glob("CC-BY-4.0*"))
        return matches[0] if matches else None
    return None


def validate_registry(
    source_registry: Path,
    licenses_dir: Path,
    citations_dir: Path,
    external_schema: Path,
    external_root: Path,
) -> dict[str, Any]:
    """Validate registry content and local evidence in a read-only manner."""

    schema = load_json(external_schema)
    if schema.get("external_schema_version") != "0.1":
        raise GovernanceUsageError("external schema版本必须为0.1。")
    if not licenses_dir.is_dir():
        raise GovernanceUsageError(f"许可证目录不存在：{licenses_dir}")
    if not citations_dir.is_dir():
        raise GovernanceUsageError(f"引用目录不存在：{citations_dir}")
    if not external_root.is_dir():
        raise GovernanceUsageError(f"外部数据根目录不存在：{external_root}")

    fields, rows = read_csv(source_registry)
    if not rows:
        raise GovernanceUsageError("来源登记为空。")
    if "dataset_id" not in fields and "source_id" not in fields:
        raise GovernanceUsageError("来源登记缺少dataset_id/source_id。")

    issues: list[RegistryIssue] = []
    seen: dict[str, int] = {}
    accepted_sources = 0
    downloaded_sources = 0
    for index, row in enumerate(rows, start=2):
        source_id = _source_id(row)
        if not source_id:
            issues.append(
                RegistryIssue(
                    "error",
                    "SOURCE_ID_MISSING",
                    "source_id不能为空。",
                    row_number=index,
                )
            )
            continue
        if source_id in seen:
            issues.append(
                RegistryIssue(
                    "error",
                    "SOURCE_ID_DUPLICATE",
                    f"source_id重复，首次出现在第{seen[source_id]}行。",
                    source_id,
                    index,
                )
            )
        else:
            seen[source_id] = index

        required_text = {
            "dataset_name": "数据集名称不能为空。",
            "source_url": "来源网址不能为空。",
            "license": "许可证名称不能为空。",
            "approved_action": "usage_scope/approved_action不能为空。",
            "task_type": "数据集用途/task_type不能为空。",
        }
        for field, message in required_text.items():
            if not (row.get(field) or "").strip():
                issues.append(
                    RegistryIssue(
                        "error", f"{field.upper()}_MISSING", message, source_id, index
                    )
                )

        url = (row.get("source_url") or "").strip()
        parsed = urlparse(url)
        if url and (parsed.scheme not in {"http", "https"} or not parsed.netloc):
            issues.append(
                RegistryIssue(
                    "error",
                    "SOURCE_URL_INVALID",
                    "来源网址必须是HTTP(S)绝对网址。",
                    source_id,
                    index,
                )
            )

        download_status = (row.get("download_status") or "").strip()
        downloaded = download_status.startswith("downloaded")
        blocked = (row.get("mapping_status") or "").strip().startswith("blocked")
        if downloaded:
            downloaded_sources += 1
            accepted_sources += int(not blocked)
        if downloaded and blocked:
            issues.append(
                RegistryIssue(
                    "error",
                    "BLOCKED_SOURCE_ACCEPTED",
                    "blocked来源不得标记为已下载可接受。",
                    source_id,
                    index,
                )
            )

        license_name = (row.get("license") or "").strip()
        license_file = (
            _find_license_file(licenses_dir, license_name) if license_name else None
        )
        if downloaded and license_file is None:
            issues.append(
                RegistryIssue(
                    "error",
                    "LICENSE_FILE_MISSING",
                    "已下载来源缺少本地许可证文件。",
                    source_id,
                    index,
                )
            )
        elif not downloaded and license_file is None:
            issues.append(
                RegistryIssue(
                    "warning",
                    "LICENSE_FILE_NOT_RETAINED",
                    "元数据来源尚未保留对应许可证文件，保持非accepted。",
                    source_id,
                    index,
                )
            )

        citation_file = citations_dir / f"{source_id}.bib"
        if downloaded and not citation_file.is_file():
            issues.append(
                RegistryIssue(
                    "error",
                    "CITATION_FILE_MISSING",
                    "已下载来源缺少引用文件。",
                    source_id,
                    index,
                )
            )
        elif not downloaded and not citation_file.is_file():
            issues.append(
                RegistryIssue(
                    "warning",
                    "CITATION_FILE_NOT_RETAINED",
                    "元数据来源尚未保留引用文件。",
                    source_id,
                    index,
                )
            )

        local_path = (row.get("local_path") or "").strip()
        if downloaded:
            if not local_path:
                issues.append(
                    RegistryIssue(
                        "error",
                        "LOCAL_PATH_MISSING",
                        "已下载来源缺少local_path。",
                        source_id,
                        index,
                    )
                )
            else:
                candidate = (external_root / local_path).resolve()
                try:
                    candidate.relative_to(external_root.resolve())
                except ValueError:
                    issues.append(
                        RegistryIssue(
                            "error",
                            "LOCAL_PATH_ESCAPE",
                            "local_path逃逸外部数据根目录。",
                            source_id,
                            index,
                        )
                    )
                else:
                    if not candidate.exists():
                        issues.append(
                            RegistryIssue(
                                "error",
                                "LOCAL_PATH_NOT_FOUND",
                                "已下载来源对应目录不存在。",
                                source_id,
                                index,
                            )
                        )

            evidence = (
                row.get("integrity_report") or row.get("archive_path") or ""
            ).strip()
            if (
                not evidence
                and (external_root / "reports/download-integrity.json").is_file()
            ):
                evidence = "reports/download-integrity.json"
            if not evidence:
                issues.append(
                    RegistryIssue(
                        "error",
                        "ACQUISITION_RECORD_MISSING",
                        "已下载来源缺少下载时间或完整性记录。",
                        source_id,
                        index,
                    )
                )
            elif not (external_root / evidence).exists():
                issues.append(
                    RegistryIssue(
                        "error",
                        "ACQUISITION_RECORD_NOT_FOUND",
                        "来源完整性记录不存在。",
                        source_id,
                        index,
                    )
                )

    error_count = sum(issue.severity == "error" for issue in issues)
    warning_count = sum(issue.severity == "warning" for issue in issues)
    return {
        "validator_version": VALIDATOR_VERSION,
        "generated_at": utc_now(),
        "source_registry": str(source_registry),
        "read_only": True,
        "summary": {
            "source_count": len(rows),
            "downloaded_source_count": downloaded_sources,
            "accepted_source_count": accepted_sources,
            "error_count": error_count,
            "warning_count": warning_count,
            "valid": error_count == 0,
        },
        "issues": [asdict(issue) for issue in issues],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="只读验证外部数据来源登记")
    parser.add_argument("--source-registry", type=Path, required=True)
    parser.add_argument("--licenses-dir", type=Path, required=True)
    parser.add_argument("--citations-dir", type=Path, required=True)
    parser.add_argument("--external-schema", type=Path, required=True)
    parser.add_argument("--external-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        report = validate_registry(
            args.source_registry.resolve(),
            args.licenses_dir.resolve(),
            args.citations_dir.resolve(),
            args.external_schema.resolve(),
            args.external_root.resolve(),
        )
        write_json(args.report.resolve(), report)
        for issue in report["issues"]:
            print(
                f"[{issue['severity']}] {issue['code']}：{issue['message']}",
                file=sys.stderr,
            )
        print(json.dumps(report["summary"], ensure_ascii=False))
        return EXIT_VALID if report["summary"]["valid"] else EXIT_DATA_INVALID
    except GovernanceUsageError as exc:
        print(f"参数或配置错误：{exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    except Exception as exc:  # noqa: BLE001
        print(f"内部错误：{exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
