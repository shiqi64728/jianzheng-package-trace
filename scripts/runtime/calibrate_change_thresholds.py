"""Scan only change-detector parameters on the synthetic engineering suite."""

from __future__ import annotations

import argparse
import itertools
import json
import sys
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai.runtime.change_detector import ChangeDetector, serializable_change
from ai.runtime.registration import ImageRegistrar

DEFAULT_SUITE = Path("E:/JianZhengData/runtime/calibration/change-v0.1")
DEFAULT_CONFIG = Path("configs/runtime/change-detection-v0.1.json")
DEFAULT_OUTPUT_JSON = DEFAULT_SUITE / "change-calibration-v0.1.json"
DEFAULT_OUTPUT_MD = DEFAULT_SUITE / "change-calibration-v0.1.md"


def evaluate_config(manifest: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    detector = ChangeDetector(ImageRegistrar(config))
    observations = []
    for scenario in manifest["scenarios"]:
        reference = cv2.imread(scenario["reference_path"], cv2.IMREAD_COLOR)
        current = cv2.imread(scenario["current_path"], cv2.IMREAD_COLOR)
        if reference is None or current is None:
            raise RuntimeError(
                f"unreadable calibration scenario: {scenario['scenario_id']}"
            )
        result = serializable_change(detector.detect(reference, current))
        observations.append(
            {
                "scenario_id": scenario["scenario_id"],
                "category": scenario["category"],
                "registration_status": result["registration_status"],
                "change_score": result["change_score"],
                "changed_pixel_ratio": result["changed_pixel_ratio"],
                "changed_region_count": result["changed_region_count"],
                "is_significant": result["is_significant"],
            }
        )
    normal_false = sum(
        item["category"] == "normal" and item["is_significant"] for item in observations
    )
    change_missed = sum(
        item["category"] == "change" and not item["is_significant"]
        for item in observations
    )
    failure_not_failed = sum(
        item["category"] == "failure" and item["registration_status"] != "FAILED"
        for item in observations
    )
    return {
        "normal_false_alarm_count": normal_false,
        "change_missed_count": change_missed,
        "failure_not_failed_count": failure_not_failed,
        "normal_observed_count": sum(
            item["category"] == "normal" for item in observations
        ),
        "change_observed_count": sum(
            item["category"] == "change" for item in observations
        ),
        "failure_observed_count": sum(
            item["category"] == "failure" for item in observations
        ),
        "observations": observations,
    }


def calibrate(
    suite_root: str | Path = DEFAULT_SUITE,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    suite_root = Path(suite_root)
    manifest = json.loads(
        (suite_root / "calibration-manifest.json").read_text(encoding="utf-8")
    )
    baseline = json.loads(Path(config_path).read_text(encoding="utf-8"))
    candidates = []
    for threshold, area, ratio in itertools.product(
        (24, 32, 40), (120, 180, 260), (0.004, 0.006, 0.01)
    ):
        config = deepcopy(baseline)
        config["pixel_difference_threshold"] = threshold
        config["minimum_region_area"] = area
        config["significant_change_ratio"] = ratio
        result = evaluate_config(manifest, config)
        distance = (
            abs(threshold - int(baseline["pixel_difference_threshold"])) / 8
            + abs(area - int(baseline["minimum_region_area"])) / 60
            + abs(ratio - float(baseline["significant_change_ratio"])) / 0.002
        )
        candidates.append(
            {
                "parameters": {
                    "pixel_difference_threshold": threshold,
                    "minimum_region_area": area,
                    "significant_change_ratio": ratio,
                },
                "engineering_distance_from_v01": distance,
                **result,
            }
        )
    candidates.sort(
        key=lambda item: (
            item["normal_false_alarm_count"],
            item["change_missed_count"],
            item["failure_not_failed_count"],
            item["engineering_distance_from_v01"],
        )
    )
    selected = candidates[0]
    baseline_result = evaluate_config(manifest, baseline)
    return {
        "calibration_version": "change-calibration-v0.1",
        "label": "SYNTHETIC_ENGINEERING_CALIBRATION",
        "generated_at": datetime.now().astimezone().isoformat(),
        "scenario_count": manifest["scenario_count"],
        "candidate_count": len(candidates),
        "baseline_parameters": {
            key: baseline[key]
            for key in (
                "pixel_difference_threshold",
                "minimum_region_area",
                "significant_change_ratio",
            )
        },
        "baseline_result": baseline_result,
        "selected_parameters": selected["parameters"],
        "selected_result": {
            key: selected[key]
            for key in (
                "normal_false_alarm_count",
                "change_missed_count",
                "failure_not_failed_count",
                "normal_observed_count",
                "change_observed_count",
                "failure_observed_count",
                "observations",
            )
        },
        "selection_rule": "minimize normal false alarms, then missed synthetic changes, then retain the closest v0.1 engineering parameters",
        "real_world_claim": "NOT_EVALUATED",
    }


def write_outputs(payload: dict[str, Any], output_json: Path, output_md: Path) -> None:
    if output_json.exists() or output_md.exists():
        raise RuntimeError("calibration output exists; refusing to overwrite")
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    baseline = payload["baseline_parameters"]
    selected = payload["selected_parameters"]
    result = payload["selected_result"]
    output_md.write_text(
        "\n".join(
            [
                "# Change calibration v0.1",
                "",
                "- Label: `SYNTHETIC_ENGINEERING_CALIBRATION`",
                f"- Scenarios: {payload['scenario_count']}",
                f"- Candidate configurations: {payload['candidate_count']}",
                f"- Baseline: `{json.dumps(baseline, sort_keys=True)}`",
                f"- Selected: `{json.dumps(selected, sort_keys=True)}`",
                f"- Normal false alarms: {result['normal_false_alarm_count']}",
                f"- Synthetic changes missed: {result['change_missed_count']}",
                "- Real logistics performance: not evaluated.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite-root", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
    args = parser.parse_args()
    payload = calibrate(args.suite_root, args.config)
    write_outputs(payload, args.output_json, args.output_md)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
