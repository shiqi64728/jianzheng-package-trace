"""Perceptual cross-split duplicate audit using OpenCV DCT hashes."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

SPLIT_PAIRS = (("train", "val"), ("train", "test"), ("val", "test"))
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def perceptual_hash(path: str | Path) -> int:
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise ValueError(f"cannot decode image: {path}")
    resized = cv2.resize(image, (32, 32), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(resized))[:8, :8]
    values = dct.flatten()[1:]
    threshold = float(np.median(values))
    bits = values > threshold
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def hamming(left: int, right: int) -> int:
    return (left ^ right).bit_count()


def _images(root: Path, split: str) -> list[Path]:
    folder = root / "images" / split
    return sorted(p for p in folder.iterdir() if p.suffix.lower() in IMAGE_SUFFIXES)


def audit_dataset(dataset_root: str | Path, *, threshold: int = 6) -> dict[str, Any]:
    root = Path(dataset_root)
    items: dict[str, list[dict[str, Any]]] = {}
    for split in ("train", "val", "test"):
        records = []
        for path in _images(root, split):
            raw = path.read_bytes()
            records.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "phash": perceptual_hash(path),
                }
            )
        items[split] = records
    matches = []
    pair_counts = {}
    for left_split, right_split in SPLIT_PAIRS:
        key = f"{left_split}_vs_{right_split}"
        pair_counts[key] = len(items[left_split]) * len(items[right_split])
        for left, right in itertools.product(items[left_split], items[right_split]):
            distance = hamming(left["phash"], right["phash"])
            exact = left["sha256"] == right["sha256"]
            if exact or distance <= threshold:
                matches.append(
                    {
                        "split_pair": key,
                        "left": left["path"],
                        "right": right["path"],
                        "exact_sha256": exact,
                        "phash_hamming": distance,
                        "classification": "EXACT"
                        if exact
                        else "PERCEPTUAL_NEAR_DUPLICATE",
                    }
                )
    matches.sort(key=lambda x: (x["phash_hamming"], x["left"], x["right"]))
    return {
        "report_version": "near-duplicate-audit-v1.1",
        "generated_at": datetime.now().astimezone().isoformat(),
        "method": "OpenCV 32x32 DCT 63-bit perceptual hash",
        "threshold_hamming_lte": threshold,
        "purpose": "DATA_LEAKAGE_AUDIT_ONLY",
        "test_predictions_accessed": False,
        "split_image_counts": {key: len(value) for key, value in items.items()},
        "cross_split_pair_counts": pair_counts,
        "exact_cross_split_count": sum(x["exact_sha256"] for x in matches),
        "perceptual_near_duplicate_count": sum(not x["exact_sha256"] for x in matches),
        "suspected_split_leakage": bool(matches),
        "matches": matches,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--threshold", type=int, default=6)
    args = parser.parse_args()
    report = audit_dataset(args.dataset, threshold=args.threshold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "exact": report["exact_cross_split_count"],
                "near": report["perceptual_near_duplicate_count"],
                "suspected_split_leakage": report["suspected_split_leakage"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
