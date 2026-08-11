"""Build synthetic and public-data demo sequences outside Git."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path

import cv2
import numpy as np

RUNTIME_DEMO = Path("E:/JianZhengData/runtime/mvp-v0.1/demo")
EXTERNAL_ROOT = Path("E:/JianZhengData/external")
TAMPAR_MANIFEST = EXTERNAL_ROOT / "converted/manifests/tampar-pairs-v0.1.csv"


def base_carton(seed: int = 42) -> np.ndarray:
    _ = seed
    image = np.full((720, 960, 3), (224, 214, 184), dtype=np.uint8)
    cv2.rectangle(image, (90, 80), (870, 650), (143, 119, 82), 8)
    cv2.line(image, (480, 80), (480, 650), (122, 98, 65), 4)
    cv2.putText(
        image,
        "JIANZHENG PACKAGE 001",
        (180, 190),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (75, 63, 47),
        3,
    )
    for x in range(120, 850, 40):
        cv2.line(image, (x, 250), (x, 620), (195, 180, 150), 1)
    for y in range(250, 620, 40):
        cv2.line(image, (120, y), (850, y), (195, 180, 150), 1)
    return image


def build_demo_a() -> dict:
    output = RUNTIME_DEMO / "demo-a-synthetic"
    output.mkdir(parents=True, exist_ok=True)
    n1 = base_carton()
    n2 = n1.copy()
    cv2.ellipse(n2, (650, 420), (85, 45), -15, 0, 360, (92, 75, 55), -1)
    cv2.ellipse(n2, (650, 420), (85, 45), -15, 0, 360, (45, 35, 28), 5)
    cv2.line(n2, (250, 510), (380, 555), (35, 30, 28), 12)
    n3 = n2.copy()
    for node, image in (("N1", n1), ("N2", n2), ("N3", n3)):
        cv2.imwrite(str(output / f"{node}.png"), image)
    metadata = {
        "demo_id": "DEMO-A",
        "label": "SYNTHETIC_DEMO",
        "expected_first_abnormal_interval": "N1_TO_N2",
        "nodes": {node: str(output / f"{node}.png") for node in ("N1", "N2", "N3")},
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def find_probable_pair() -> tuple[Path, Path, str] | None:
    with TAMPAR_MANIFEST.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if row.get("pairing_confidence") != "probable":
                continue
            reference = row.get("reference_image_relpath", "")
            tampered = row.get("tampered_image_relpath", "")
            if not reference or not tampered:
                continue
            ref_path, tampered_path = (
                EXTERNAL_ROOT / reference,
                EXTERNAL_ROOT / tampered,
            )
            if ref_path.is_file() and tampered_path.is_file():
                return ref_path, tampered_path, row.get("pair_id", "")
    return None


def build_demo_b() -> dict:
    output = RUNTIME_DEMO / "demo-b-tampar"
    output.mkdir(parents=True, exist_ok=True)
    pair = find_probable_pair()
    if pair is None:
        return {
            "demo_id": "DEMO-B",
            "status": "NO_PROBABLE_PAIR_AVAILABLE",
            "labels": [
                "PUBLIC_DATA_DEMO",
                "SIMULATED_NODE_SEQUENCE",
                "NOT_REAL_LOGISTICS_TRACE",
            ],
        }
    reference, tampered, pair_id = pair
    shutil.copy2(reference, output / f"N1{reference.suffix.lower()}")
    shutil.copy2(tampered, output / f"N2{tampered.suffix.lower()}")
    shutil.copy2(tampered, output / f"N3{tampered.suffix.lower()}")
    metadata = {
        "demo_id": "DEMO-B",
        "status": "READY",
        "pair_id": pair_id,
        "labels": [
            "PUBLIC_DATA_DEMO",
            "SIMULATED_NODE_SEQUENCE",
            "NOT_REAL_LOGISTICS_TRACE",
            "TAMPAR_PAIR_NOT_HUMAN_CONFIRMED",
            "DEMO_ONLY",
        ],
        "source_reference": str(reference),
        "source_tampered": str(tampered),
        "nodes": {
            "N1": str(next(output.glob("N1.*"))),
            "N2": str(next(output.glob("N2.*"))),
            "N3": str(next(output.glob("N3.*"))),
        },
    }
    (output / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return metadata


def main() -> int:
    RUNTIME_DEMO.mkdir(parents=True, exist_ok=True)
    summary = {"demo_a": build_demo_a(), "demo_b": build_demo_b()}
    output = RUNTIME_DEMO / "demo-cases-v0.1.json"
    output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
