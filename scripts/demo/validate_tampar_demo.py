"""Observe 20 deterministic probable TAMPAR pairs under v0.1 and v0.2 configs."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai.runtime.change_detector import ChangeDetector, serializable_change
from ai.runtime.registration import ImageRegistrar

EXTERNAL_ROOT = Path("E:/JianZhengData/external")
MANIFEST = EXTERNAL_ROOT / "converted/manifests/tampar-pairs-v0.1.csv"
CONFIGS = {
    "v0.1": Path("configs/runtime/change-detection-v0.1.json"),
    "v0.2": Path("configs/runtime/change-detection-v0.2.json"),
}
OUTPUT = Path("E:/JianZhengData/runtime/mvp-v0.2/logs/tampar-observation-v01-v02.json")


def probable_pairs(limit: int = 20) -> list[dict[str, str]]:
    unique: dict[str, dict[str, str]] = {}
    with MANIFEST.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            pair_id = row.get("pair_id", "")
            if (
                row.get("pairing_confidence") == "probable"
                and pair_id
                and row.get("reference_image_relpath")
                and row.get("tampered_image_relpath")
            ):
                unique.setdefault(pair_id, row)
    return [unique[key] for key in sorted(unique)[:limit]]


def resize_for_demo(image, maximum: int = 1400):
    height, width = image.shape[:2]
    scale = min(1.0, maximum / max(height, width))
    if scale == 1.0:
        return image
    return cv2.resize(image, (round(width * scale), round(height * scale)))


def main() -> int:
    if OUTPUT.exists():
        raise RuntimeError(
            f"observation report exists; refusing to overwrite: {OUTPUT}"
        )
    detectors = {
        version: ChangeDetector(ImageRegistrar(config))
        for version, config in CONFIGS.items()
    }
    observations = []
    for row in probable_pairs():
        reference = EXTERNAL_ROOT / row["reference_image_relpath"]
        tampered = EXTERNAL_ROOT / row["tampered_image_relpath"]
        ref_image = cv2.imread(str(reference), cv2.IMREAD_COLOR)
        cur_image = cv2.imread(str(tampered), cv2.IMREAD_COLOR)
        if ref_image is None or cur_image is None:
            observations.append(
                {"pair_id": row["pair_id"], "observation_status": "IMAGE_UNREADABLE"}
            )
            continue
        version_results = {}
        for version, detector in detectors.items():
            result = serializable_change(
                detector.detect(resize_for_demo(ref_image), resize_for_demo(cur_image))
            )
            version_results[version] = {
                "registration_status": result["registration_status"],
                "change_score": result["change_score"],
                "changed_pixel_ratio": result["changed_pixel_ratio"],
                "changed_region_count": result["changed_region_count"],
                "is_significant": result["is_significant"],
                "warnings": result["warnings"],
            }
        observations.append(
            {
                "pair_id": row["pair_id"],
                "pairing_confidence": "probable",
                "observation_status": "OBSERVED",
                "versions": version_results,
            }
        )
    payload = {
        "report_version": "tampar-observation-v01-v02",
        "generated_at": datetime.now().astimezone().isoformat(),
        "record_count": len(observations),
        "labels": ["TAMPAR_PAIR_NOT_HUMAN_CONFIRMED", "OBSERVATION_ONLY", "DEMO_ONLY"],
        "interpretation": "The probable pairs are not human-confirmed; this report records engineering behavior only.",
        "observations": observations,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
