"""Observe at most 20 deterministic probable TAMPAR pairs; never report accuracy."""

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
CONFIG = Path("configs/runtime/change-detection-v0.1.json")
OUTPUT = Path(
    "E:/JianZhengData/runtime/mvp-v0.1/logs/tampar-demo-observation-report-v0.1.json"
)


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
        raise RuntimeError(f"演示观察报告已存在，拒绝覆盖：{OUTPUT}")
    detector = ChangeDetector(ImageRegistrar(CONFIG))
    observations = []
    for row in probable_pairs():
        reference = EXTERNAL_ROOT / row["reference_image_relpath"]
        tampered = EXTERNAL_ROOT / row["tampered_image_relpath"]
        ref_image = cv2.imread(str(reference), cv2.IMREAD_COLOR)
        cur_image = cv2.imread(str(tampered), cv2.IMREAD_COLOR)
        if ref_image is None or cur_image is None:
            observations.append(
                {
                    "pair_id": row["pair_id"],
                    "observation_status": "IMAGE_UNREADABLE",
                }
            )
            continue
        result = serializable_change(
            detector.detect(resize_for_demo(ref_image), resize_for_demo(cur_image))
        )
        observations.append(
            {
                "pair_id": row["pair_id"],
                "pairing_confidence": "probable",
                "reference_image_relpath": row["reference_image_relpath"],
                "tampered_image_relpath": row["tampered_image_relpath"],
                "observation_status": "OBSERVED",
                "registration_status": result["registration_status"],
                "change_score": result["change_score"],
                "changed_pixel_ratio": result["changed_pixel_ratio"],
                "changed_region_count": result["changed_region_count"],
                "is_significant": result["is_significant"],
                "warnings": result["warnings"],
            }
        )
    payload = {
        "report_version": "tampar-demo-observation-v0.1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "record_count": len(observations),
        "labels": ["TAMPAR_PAIR_NOT_HUMAN_CONFIRMED", "DEMO_ONLY"],
        "prohibited_interpretation": "本报告仅为观察记录，不形成任何模型性能评价；probable pair未经人工确认。",
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
