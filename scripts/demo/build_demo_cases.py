"""Build deterministic competition demo assets in the external v0.2 runtime."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ai.runtime.detector import Detector
from ai.runtime.model_registry import ModelRegistry

RUNTIME_DEMO = Path("E:/JianZhengData/runtime/mvp-v0.2/demo")
EXTERNAL_ROOT = Path("E:/JianZhengData/external")
TAMPAR_MANIFEST = EXTERNAL_ROOT / "converted/manifests/tampar-pairs-v0.1.csv"
FROZEN_ROOT = Path("E:/JianZhengData/training/detect-d02-d03-v0.1")
ACTIVE_REGISTRY = Path("E:/JianZhengData/models/active/detector-v0.1.json")


def base_carton(seed: int = 42, surface: str = "front") -> np.ndarray:
    rng = np.random.default_rng(seed + sum(ord(char) for char in surface))
    image = np.full((720, 960, 3), (224, 214, 184), dtype=np.uint8)
    noise = rng.normal(0, 3, image.shape[:2]).astype(np.int16)
    image = np.clip(image.astype(np.int16) + noise[:, :, None], 0, 255).astype(np.uint8)
    cv2.rectangle(image, (90, 80), (870, 650), (143, 119, 82), 8)
    cv2.line(image, (480, 80), (480, 650), (122, 98, 65), 4)
    cv2.putText(
        image,
        f"JIANZHENG {surface.upper()} 001",
        (150, 190),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.15,
        (75, 63, 47),
        3,
    )
    for x in range(120, 850, 40):
        cv2.line(image, (x, 250), (x, 620), (195, 180, 150), 1)
    for y in range(250, 620, 40):
        cv2.line(image, (120, y), (850, y), (195, 180, 150), 1)
    return image


def _write_metadata(output: Path, payload: dict) -> dict:
    (output / "metadata.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def build_demo_a() -> dict:
    output = RUNTIME_DEMO / "DEMO-A"
    output.mkdir(parents=True, exist_ok=True)
    n1 = base_carton()
    n2 = n1.copy()
    cv2.ellipse(n2, (650, 420), (85, 45), -15, 0, 360, (92, 75, 55), -1)
    cv2.ellipse(n2, (650, 420), (85, 45), -15, 0, 360, (45, 35, 28), 5)
    n3 = n2.copy()
    nodes = {}
    for node, image in (("N1", n1), ("N2", n2), ("N3", n3)):
        path = output / f"{node}-front.png"
        cv2.imwrite(str(path), image)
        nodes[node] = {"front": str(path)}
    return _write_metadata(
        output,
        {
            "demo_id": "DEMO-A",
            "label": "SYNTHETIC_DEMO",
            "expected_first_abnormal_interval": "N1_TO_N2",
            "nodes": nodes,
        },
    )


def find_probable_pair() -> tuple[Path, Path, str] | None:
    with TAMPAR_MANIFEST.open(encoding="utf-8-sig", newline="") as stream:
        rows = sorted(csv.DictReader(stream), key=lambda row: row.get("pair_id", ""))
        for row in rows:
            if row.get("pairing_confidence") != "probable":
                continue
            reference = row.get("reference_image_relpath", "")
            tampered = row.get("tampered_image_relpath", "")
            if not reference or not tampered:
                continue
            ref_path = EXTERNAL_ROOT / reference
            tampered_path = EXTERNAL_ROOT / tampered
            if ref_path.is_file() and tampered_path.is_file():
                return ref_path, tampered_path, row.get("pair_id", "")
    return None


def build_demo_b() -> dict:
    output = RUNTIME_DEMO / "DEMO-B"
    output.mkdir(parents=True, exist_ok=True)
    pair = find_probable_pair()
    if pair is None:
        return _write_metadata(
            output,
            {
                "demo_id": "DEMO-B",
                "status": "NO_PROBABLE_PAIR_AVAILABLE",
                "labels": ["PUBLIC_DATA_DEMO", "NOT_REAL_LOGISTICS_TRACE"],
            },
        )
    reference, tampered, pair_id = pair
    nodes = {}
    for node, source in (("N1", reference), ("N2", tampered), ("N3", tampered)):
        destination = output / f"{node}-front{source.suffix.lower()}"
        shutil.copy2(source, destination)
        nodes[node] = {"front": str(destination)}
    return _write_metadata(
        output,
        {
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
            "nodes": nodes,
        },
    )


def _val_candidates(seed: int = 20260811) -> list[Path]:
    candidates = []
    for image in (FROZEN_ROOT / "images" / "val").glob("*"):
        label = FROZEN_ROOT / "labels" / "val" / f"{image.stem}.txt"
        if (
            image.is_file()
            and label.is_file()
            and label.read_text(encoding="utf-8").strip()
        ):
            candidates.append(image)
    return sorted(
        candidates,
        key=lambda path: hashlib.sha256(f"{seed}|{path.name}".encode()).hexdigest(),
    )


def build_demo_c(detector: Detector | None = None) -> dict:
    output = RUNTIME_DEMO / "DEMO-C"
    output.mkdir(parents=True, exist_ok=True)
    detector = detector or Detector(ModelRegistry(ACTIVE_REGISTRY), confidence=0.25)
    selected = None
    prediction = None
    label_path = None
    considered = 0
    for candidate in _val_candidates():
        considered += 1
        result = detector.predict(candidate)
        if result["detections"]:
            selected = candidate
            prediction = result
            label_path = FROZEN_ROOT / "labels" / "val" / f"{candidate.stem}.txt"
            break
    if selected is None or prediction is None or label_path is None:
        raise RuntimeError(
            "no deterministic val candidate produced an active detector result"
        )
    destination = output / f"public-val-sample{selected.suffix.lower()}"
    shutil.copy2(selected, destination)
    ground_truth = [
        line.split()[0]
        for line in label_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return _write_metadata(
        output,
        {
            "demo_id": "DEMO-C",
            "labels": ["PUBLIC_DATA_DETECTION_DEMO", "NOT_REAL_LOGISTICS_TRACE"],
            "selection_seed": 20260811,
            "selection_rule": "frozen public val, nonempty ground truth, deterministic SHA ordering, first active detector result",
            "source_split": "val",
            "source_image": str(selected),
            "copied_image": str(destination),
            "ground_truth_class_ids": ground_truth,
            "prediction": prediction,
            "candidates_considered": considered,
            "prediction_boxes_edited": False,
        },
    )


def build_demo_d() -> dict:
    output = RUNTIME_DEMO / "DEMO-D"
    output.mkdir(parents=True, exist_ok=True)
    surfaces = ("front", "left", "right", "top")
    nodes: dict[str, dict[str, str]] = {node: {} for node in ("N1", "N2", "N3")}
    for surface in surfaces:
        original = base_carton(100, surface)
        changed = original.copy()
        if surface == "left":
            cv2.rectangle(changed, (560, 330), (760, 485), (64, 52, 42), -1)
            cv2.line(changed, (540, 310), (785, 505), (32, 28, 24), 12)
        for node, image in (
            ("N1", original),
            ("N2", changed if surface == "left" else original),
            ("N3", changed if surface == "left" else original),
        ):
            path = output / f"{node}-{surface}.png"
            cv2.imwrite(str(path), image)
            nodes[node][surface] = str(path)
    return _write_metadata(
        output,
        {
            "demo_id": "DEMO-D",
            "label": "MULTISURFACE_SYNTHETIC_DEMO",
            "expected_first_abnormal_interval": "N1_TO_N2",
            "expected_trigger_surface": "left",
            "nodes": nodes,
        },
    )


def main() -> int:
    RUNTIME_DEMO.mkdir(parents=True, exist_ok=True)
    summary_path = RUNTIME_DEMO / "demo-cases-v0.2.json"
    if summary_path.exists():
        print(summary_path.read_text(encoding="utf-8"))
        return 0
    summary = {
        "demo_a": build_demo_a(),
        "demo_b": build_demo_b(),
        "demo_c": build_demo_c(),
        "demo_d": build_demo_d(),
    }
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
