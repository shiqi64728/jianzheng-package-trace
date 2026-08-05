"""Build deterministic member-C review worklists from external manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from pathlib import Path
from typing import Any, Callable, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.dataset.external_data_common import (
    GovernanceUsageError,
    read_csv,
    validate_relative_path,
    write_csv_bom,
)

EXIT_SUCCESS = 0
EXIT_USAGE_ERROR = 2
EXIT_INTERNAL_ERROR = 3
WORKLIST_FIELDS = (
    "external_record_id",
    "source_id",
    "original_image_relpath",
    "review_focus",
    "review_question",
    "duplicate_group_id",
    "pairing_confidence",
    "review_decision",
    "review_notes",
)


def _rank(seed: str, record_id: str, focus: str) -> str:
    return hashlib.sha256(
        f"{seed}\x1f{record_id}\x1f{focus}".encode("utf-8")
    ).hexdigest()


def _select(
    rows: list[dict[str, str]],
    count: int,
    seed: str,
    focus: str,
    predicate: Callable[[dict[str, str]], bool],
) -> list[dict[str, str]]:
    candidates = [row for row in rows if predicate(row)]
    candidates.sort(
        key=lambda row: (
            _rank(seed, row.get("external_record_id", ""), focus),
            row.get("external_record_id", ""),
        )
    )
    return candidates[:count]


def _work_row(row: dict[str, str], focus: str, question: str) -> dict[str, str]:
    path = row.get("original_image_relpath", "")
    validate_relative_path(path)
    return {
        "external_record_id": row.get("external_record_id", ""),
        "source_id": row.get("source_id", ""),
        "original_image_relpath": path,
        "review_focus": focus,
        "review_question": question,
        "duplicate_group_id": row.get("duplicate_group_id", ""),
        "pairing_confidence": row.get("pairing_confidence", ""),
        "review_decision": "",
        "review_notes": "",
    }


def build_worklists(manifests_dir: Path, report_dir: Path, seed: str) -> dict[str, Any]:
    """Build all worklists deterministically without reading or copying images."""

    if not seed:
        raise GovernanceUsageError("seed不能为空。")
    _, defect = read_csv(manifests_dir / "defect-cardboard-v0.1.csv")
    _, damaged = read_csv(manifests_dir / "damaged-box-detection-v0.1.csv")
    _, tampar = read_csv(manifests_dir / "tampar-pairs-v0.1.csv")

    defect_output: list[dict[str, str]] = []
    defect_specs = (
        ("dent", 20, "bbox是否覆盖凹陷，样本是否符合D02语义？"),
        ("hole", 20, "bbox是否覆盖破口，样本是否符合D03语义？"),
        ("dirt", 50, "该样本是否明确受潮，而非阴影、印刷或普通污点？"),
    )
    for class_name, count, question in defect_specs:
        selected = _select(
            defect,
            count,
            seed,
            class_name,
            lambda row, name=class_name: (
                name
                in {
                    str(item.get("original_class", ""))
                    for item in json.loads(row.get("annotation_records_json") or "[]")
                }
            ),
        )
        defect_output.extend(_work_row(row, class_name, question) for row in selected)

    damaged_output: list[dict[str, str]] = []
    for class_name, count, question in (
        ("undamagedpackages", 30, "是否确为完好纸箱，是否存在背景捷径或非纸箱样本？"),
        ("damagedpackages", 50, "是否确为一般破损，是否错标或依赖明显背景？"),
    ):
        selected = _select(
            damaged,
            count,
            seed,
            class_name,
            lambda row, name=class_name: row.get("original_class") == name,
        )
        damaged_output.extend(_work_row(row, class_name, question) for row in selected)
    duplicate_rows = sorted(
        (row for row in damaged if row.get("duplicate_group_id")),
        key=lambda row: (
            row.get("duplicate_group_id", ""),
            row.get("external_record_id", ""),
        ),
    )
    damaged_output.extend(
        _work_row(
            row,
            "duplicate_group",
            "重复内容是否保持同一类别和split；训练候选应保留哪一份？",
        )
        for row in duplicate_rows
    )

    tampar_output: list[dict[str, str]] = []
    for confidence, count, question in (
        ("confirmed", 30, "reference和tampered是否为同一表面，确认依据是否充分？"),
        ("probable", 30, "基于parcel id和时间邻近的配对是否真实对应同一表面？"),
        ("unresolved", 100, "能否从本地论文/目录证据确定配对；不能则保持unresolved。"),
    ):
        selected = _select(
            tampar,
            count,
            seed,
            confidence,
            lambda row, value=confidence: row.get("pairing_confidence") == value,
        )
        tampar_output.extend(_work_row(row, confidence, question) for row in selected)

    report_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "defect-cardboard-review-v0.1.csv": defect_output,
        "damaged-box-review-v0.1.csv": damaged_output,
        "tampar-pair-review-v0.1.csv": tampar_output,
    }
    for name, rows in outputs.items():
        write_csv_bom(report_dir / name, WORKLIST_FIELDS, rows)
    return {
        "seed": seed,
        "outputs": {name: len(rows) for name, rows in outputs.items()},
        "copies_created": 0,
        "absolute_paths_written": 0,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成成员C外部数据人工审核工作清单")
    parser.add_argument("--manifests-dir", type=Path, required=True)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--seed", default="jianzheng-external-review-v0.1")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        summary = build_worklists(
            args.manifests_dir.resolve(), args.report_dir.resolve(), args.seed
        )
        print(json.dumps(summary, ensure_ascii=False))
        return EXIT_SUCCESS
    except GovernanceUsageError as exc:
        print(f"参数或配置错误：{exc}", file=sys.stderr)
        return EXIT_USAGE_ERROR
    except Exception as exc:  # noqa: BLE001
        print(f"内部错误：{exc}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return EXIT_INTERNAL_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
