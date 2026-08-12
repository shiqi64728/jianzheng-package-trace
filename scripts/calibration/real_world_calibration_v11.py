"""Validate real-sequence worklists and summarize controlled calibration results."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

NODES = ("N1", "N2", "N3")
SURFACES = ("front", "left", "right", "top")
OWNERSHIP = {"SELF_OWNED", "EXPLICITLY_AUTHORIZED"}
PII_FIELDS = {
    "name",
    "real_name",
    "phone",
    "mobile",
    "address",
    "waybill",
    "tracking_number",
}
REGISTRATION_STATUSES = {"SUCCESS", "LOW_CONFIDENCE", "FAILED"}
REQUIRED_FIELDS = {
    "package_alias",
    "node_id",
    "surface",
    "capture_time",
    "image_path",
    "ownership_status",
    "privacy_status",
    "expected_change",
    "change_applied_after_node",
    "change_surface",
    "change_type",
}


class CalibrationInputError(ValueError):
    """Raised when a real-sequence record violates the calibration contract."""


def _parse_time(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise CalibrationInputError(f"capture_time is not ISO 8601: {value}") from error
    if parsed.tzinfo is None:
        raise CalibrationInputError("capture_time must include a timezone offset")
    return parsed


def load_completed_captures(
    path: str | Path,
    *,
    allowed_root: str | Path = "E:/JianZhengData",
) -> list[dict[str, Any]]:
    """Load only complete, authorized, privacy-cleared capture rows."""

    source = Path(path)
    root = Path(allowed_root).resolve()
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        forbidden = sorted(fields & PII_FIELDS)
        if forbidden:
            raise CalibrationInputError(f"PII fields are forbidden: {forbidden}")
        missing = sorted(REQUIRED_FIELDS - fields)
        if missing:
            raise CalibrationInputError(f"missing fields: {missing}")
        captures: list[dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        for line_number, raw in enumerate(reader, start=2):
            if raw.get("collection_status", "").strip() != "CAPTURED":
                continue
            package = raw["package_alias"].strip()
            node = raw["node_id"].strip().upper()
            surface = raw["surface"].strip().lower()
            if not package or node not in NODES or surface not in SURFACES:
                raise CalibrationInputError(
                    f"line {line_number}: invalid package/node/surface"
                )
            if raw["ownership_status"].strip() not in OWNERSHIP:
                raise CalibrationInputError(
                    f"line {line_number}: ownership not approved"
                )
            if raw["privacy_status"].strip() != "PASSED":
                raise CalibrationInputError(
                    f"line {line_number}: privacy_status must be PASSED"
                )
            captured_at = _parse_time(raw["capture_time"].strip())
            image = Path(raw["image_path"].strip()).resolve()
            try:
                image.relative_to(root)
            except ValueError as error:
                raise CalibrationInputError(
                    f"line {line_number}: image is outside allowed root"
                ) from error
            if not image.is_file():
                raise CalibrationInputError(f"line {line_number}: image does not exist")
            key = (package, node, surface)
            if key in seen:
                raise CalibrationInputError(
                    f"line {line_number}: duplicate capture {key}"
                )
            seen.add(key)
            item = dict(raw)
            item.update(
                {
                    "package_alias": package,
                    "node_id": node,
                    "surface": surface,
                    "capture_time": captured_at.isoformat(),
                    "image_path": str(image),
                }
            )
            captures.append(item)
    return captures


def sequence_inventory(captures: list[dict[str, Any]]) -> dict[str, Any]:
    """Describe package/node/surface completeness without inferring missing facts."""

    grouped: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for item in captures:
        grouped[item["package_alias"]].add((item["node_id"], item["surface"]))
    qualified = []
    for package, keys in sorted(grouped.items()):
        front_complete = all((node, "front") in keys for node in NODES)
        full_multisurface = all(
            (node, surface) in keys for node in NODES for surface in SURFACES
        )
        qualified.append(
            {
                "package_alias": package,
                "capture_count": len(keys),
                "surface_count": len({surface for _, surface in keys}),
                "front_complete": front_complete,
                "full_multisurface": full_multisurface,
            }
        )
    return {
        "package_count": len(grouped),
        "image_count": len(captures),
        "surface_count": len({item["surface"] for item in captures}),
        "qualified_packages": [x for x in qualified if x["front_complete"]],
        "packages": qualified,
    }


def calibration_metrics(pair_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute controlled calibration metrics from verified pair observations."""

    statuses = Counter()
    normal_total = normal_false = changed_total = changed_seen = 0
    sequences: dict[str, dict[str, bool]] = defaultdict(
        lambda: {"interval": True, "surface": True}
    )
    for row in pair_results:
        status = row["registration_status"]
        if status not in REGISTRATION_STATUSES:
            raise CalibrationInputError(f"invalid registration_status: {status}")
        statuses[status] += 1
        expected = bool(row["expected_change"])
        observed = bool(row["change_observed"])
        if expected:
            changed_total += 1
            changed_seen += int(observed)
        else:
            normal_total += 1
            normal_false += int(observed)
        package = row.get("package_alias")
        if package:
            sequences[package]["interval"] &= bool(
                row.get("first_abnormal_interval_correct", True)
            )
            sequences[package]["surface"] &= bool(
                row.get("trigger_surface_correct", True)
            )

    def rate(numerator: int, denominator: int) -> float | None:
        return numerator / denominator if denominator else None

    pair_count = len(pair_results)
    sequence_count = len(sequences)
    interval_correct = sum(x["interval"] for x in sequences.values())
    surface_correct = sum(x["surface"] for x in sequences.values())
    return {
        "label": "CONTROLLED REAL-WORLD CALIBRATION",
        "pair_count": pair_count,
        "registration_counts": dict(statuses),
        "registration_usable_rate": rate(
            statuses["SUCCESS"] + statuses["LOW_CONFIDENCE"], pair_count
        ),
        "normal_pair_count": normal_total,
        "normal_false_positive_count": normal_false,
        "normal_false_alarm_rate": rate(normal_false, normal_total),
        "changed_pair_count": changed_total,
        "changed_pair_detected_count": changed_seen,
        "changed_pair_detection_rate": rate(changed_seen, changed_total),
        "sequence_count": sequence_count,
        "first_abnormal_interval_correct_count": interval_correct,
        "first_abnormal_interval_accuracy": rate(interval_correct, sequence_count),
        "trigger_surface_correct_count": surface_correct,
        "trigger_surface_accuracy": rate(surface_correct, sequence_count),
        "statistical_scope": "ENGINEERING_TARGET"
        if sequence_count >= 3
        else "OBSERVATIONAL",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("worklist", type=Path)
    parser.add_argument("--allowed-root", type=Path, default=Path("E:/JianZhengData"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    captures = load_completed_captures(args.worklist, allowed_root=args.allowed_root)
    inventory = sequence_inventory(captures)
    payload = {
        "status": "READY"
        if inventory["qualified_packages"]
        else "PENDING_EXTERNAL_DATA",
        "inventory": inventory,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
