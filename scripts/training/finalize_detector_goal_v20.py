"""One-shot final-test and promotion gate for Detector Goal v2.0."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ACTIVE_TEST_AP = 0.0755004514183389
ACTIVE_TEST_D03_AP = 0.1141889012


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def promotion_gate(metrics: dict[str, Any], latency_ms: float) -> dict[str, Any]:
    overall_ap = metrics["overall"]["mAP50-95"]
    d02_ap = metrics["per_class"]["D02_surface_dent"]["mAP50-95"]
    d03_ap = metrics["per_class"]["D03_carton_tear"]["mAP50-95"]
    checks = {
        "overall_ap_at_least_0_095": overall_ap >= 0.095,
        "d02_ap_at_least_0_050": d02_ap >= 0.050,
        "d03_no_catastrophic_regression": d03_ap >= ACTIVE_TEST_D03_AP * 0.90,
        "latency_within_1_75x": latency_ms <= 8.191 * 1.75,
    }
    passed = all(checks.values())
    return {
        "decision": "STRONG_PROMOTION"
        if passed and overall_ap >= 0.110
        else ("PROMOTE" if passed else "KEEP_CURRENT_ACTIVE"),
        "active_registry_action": "CREATE_V2_REGISTRY"
        if passed
        else "PRESERVE_CURRENT",
        "checks": checks,
        "relative_overall_ap_change": overall_ap / ACTIVE_TEST_AP - 1.0,
    }


def reserve_lock(lock: Path, payload: dict[str, Any]) -> None:
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def run_once(args: argparse.Namespace) -> dict[str, Any]:
    from scripts.training.run_detector_goal_v20 import metric_values
    from ultralytics import YOLO

    candidate_sha = sha256(args.candidate)
    if candidate_sha != args.expected_sha:
        raise ValueError(f"candidate SHA mismatch: {candidate_sha}")
    dataset_lock_sha = sha256(args.dataset_lock)
    selected_at = datetime.now().astimezone().isoformat()
    reserve = {
        "lock_version": "final-test-lock-v2.0",
        "state": "RUNNING",
        "candidate": str(args.candidate),
        "candidate_sha256": candidate_sha,
        "dataset_lock": str(args.dataset_lock),
        "dataset_lock_sha256": dataset_lock_sha,
        "selected_val_metrics": json.loads(
            args.val_evidence.read_text(encoding="utf-8")
        ),
        "selection_reason": args.selection_reason,
        "test_started_at": selected_at,
        "single_access_guard": True,
    }
    reserve_lock(args.lock, reserve)
    metrics = YOLO(str(args.candidate)).val(
        data=str(args.dataset_yaml),
        split="test",
        imgsz=args.imgsz,
        batch=args.batch,
        device=0,
        workers=4,
        project=str(args.output.parent),
        name=args.output.name,
        exist_ok=False,
        plots=True,
        verbose=True,
    )
    values = metric_values(metrics)
    latency = float(metrics.speed["inference"])
    report = {
        **reserve,
        "state": "COMPLETED",
        "test_completed_at": datetime.now().astimezone().isoformat(),
        "split": "test",
        "test_access_count": 1,
        "threshold_tuning_performed": False,
        **values,
        "speed_ms_per_image": {
            key: float(value) for key, value in metrics.speed.items()
        },
        "promotion_gate": promotion_gate(values, latency),
        "output_dir": str(metrics.save_dir),
    }
    args.lock.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--val-evidence", type=Path, required=True)
    parser.add_argument("--dataset-yaml", type=Path, required=True)
    parser.add_argument("--dataset-lock", type=Path, required=True)
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--selection-reason", required=True)
    parser.add_argument("--imgsz", type=int, required=True)
    parser.add_argument("--batch", type=int, default=8)
    run_once(parser.parse_args())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
