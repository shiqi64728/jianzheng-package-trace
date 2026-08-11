"""Build deterministic synthetic engineering calibration pairs outside Git."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

DEFAULT_OUTPUT = Path("E:/JianZhengData/runtime/calibration/change-v0.1")
SCENARIOS = (
    ("NORMAL-01", "normal", "slight_translation"),
    ("NORMAL-02", "normal", "slight_rotation"),
    ("NORMAL-03", "normal", "perspective_change"),
    ("NORMAL-04", "normal", "slight_brightness_change"),
    ("CHANGE-01", "change", "small_local_change"),
    ("CHANGE-02", "change", "large_local_change"),
    ("CHANGE-03", "change", "corner_change"),
    ("CHANGE-04", "change", "tape_shape_change"),
    ("FAILURE-01", "failure", "textureless_pair"),
    ("FAILURE-02", "failure", "severe_view_change"),
)


def base_image(seed: int = 20260811) -> np.ndarray:
    rng = np.random.default_rng(seed)
    image = np.full((480, 640, 3), (211, 198, 163), dtype=np.uint8)
    noise = rng.normal(0, 5, image.shape[:2]).astype(np.int16)
    image = np.clip(image.astype(np.int16) + noise[:, :, None], 0, 255).astype(np.uint8)
    cv2.rectangle(image, (35, 30), (605, 450), (104, 82, 55), 6)
    cv2.line(image, (320, 35), (320, 445), (126, 101, 68), 5)
    for x in range(65, 600, 38):
        cv2.line(image, (x, 120), (x, 430), (180, 162, 127), 1)
    for y in range(120, 430, 34):
        cv2.line(image, (60, y), (600, y), (180, 162, 127), 1)
    cv2.putText(
        image,
        "JZ-CAL-001",
        (105, 92),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.25,
        (58, 48, 38),
        3,
    )
    for _ in range(45):
        center = (int(rng.integers(50, 590)), int(rng.integers(125, 425)))
        cv2.circle(image, center, int(rng.integers(1, 4)), (96, 82, 61), -1)
    return image


def build_pair(scenario_id: str, seed: int = 20260811) -> tuple[np.ndarray, np.ndarray]:
    reference = base_image(seed)
    current = reference.copy()
    height, width = reference.shape[:2]
    if scenario_id == "NORMAL-01":
        matrix = np.float32([[1, 0, 7], [0, 1, -5]])
        current = cv2.warpAffine(
            reference, matrix, (width, height), borderMode=cv2.BORDER_REFLECT
        )
    elif scenario_id == "NORMAL-02":
        matrix = cv2.getRotationMatrix2D((width / 2, height / 2), 1.8, 1.0)
        current = cv2.warpAffine(
            reference, matrix, (width, height), borderMode=cv2.BORDER_REFLECT
        )
    elif scenario_id == "NORMAL-03":
        source = np.float32(
            [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]
        )
        target = np.float32(
            [[5, 8], [width - 10, 3], [width - 4, height - 8], [11, height - 2]]
        )
        current = cv2.warpPerspective(
            reference,
            cv2.getPerspectiveTransform(source, target),
            (width, height),
            borderMode=cv2.BORDER_REFLECT,
        )
    elif scenario_id == "NORMAL-04":
        current = cv2.convertScaleAbs(reference, alpha=1.015, beta=5)
    elif scenario_id == "CHANGE-01":
        cv2.ellipse(current, (445, 310), (28, 18), 10, 0, 360, (65, 55, 45), -1)
    elif scenario_id == "CHANGE-02":
        cv2.rectangle(current, (385, 245), (560, 365), (74, 60, 47), -1)
        cv2.rectangle(current, (385, 245), (560, 365), (35, 30, 26), 5)
    elif scenario_id == "CHANGE-03":
        triangle = np.array([[36, 31], [155, 31], [36, 145]], dtype=np.int32)
        cv2.fillPoly(current, [triangle], (61, 50, 42))
    elif scenario_id == "CHANGE-04":
        cv2.line(current, (240, 45), (405, 444), (236, 229, 205), 26)
        cv2.line(current, (240, 45), (405, 444), (115, 100, 80), 2)
    elif scenario_id == "FAILURE-01":
        reference = np.full_like(reference, 160)
        current = np.full_like(reference, 170)
    elif scenario_id == "FAILURE-02":
        current = cv2.resize(
            reference[15:145, 30:210], (width, height), interpolation=cv2.INTER_CUBIC
        )
    else:
        raise ValueError(f"unknown scenario: {scenario_id}")
    return reference, current


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_suite(output: str | Path = DEFAULT_OUTPUT, seed: int = 20260811) -> dict:
    root = Path(output)
    manifest_path = root / "calibration-manifest.json"
    if manifest_path.exists():
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    if root.exists() and any(root.iterdir()):
        raise RuntimeError(f"calibration output is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    records = []
    for scenario_id, category, description in SCENARIOS:
        reference, current = build_pair(scenario_id, seed)
        scenario_dir = root / scenario_id
        scenario_dir.mkdir()
        reference_path = scenario_dir / "reference.png"
        current_path = scenario_dir / "current.png"
        cv2.imwrite(str(reference_path), reference)
        cv2.imwrite(str(current_path), current)
        records.append(
            {
                "scenario_id": scenario_id,
                "category": category,
                "description": description,
                "reference_path": str(reference_path),
                "current_path": str(current_path),
                "reference_sha256": _sha256(reference_path),
                "current_sha256": _sha256(current_path),
            }
        )
    payload = {
        "suite_version": "change-calibration-v0.1",
        "label": "SYNTHETIC_ENGINEERING_CALIBRATION",
        "seed": seed,
        "generated_at": datetime.now().astimezone().isoformat(),
        "scenario_count": len(records),
        "scenarios": records,
        "limitation": "Synthetic engineering calibration; not a real logistics benchmark.",
    }
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=20260811)
    args = parser.parse_args()
    print(json.dumps(build_suite(args.output, args.seed), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
