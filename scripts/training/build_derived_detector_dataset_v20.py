"""Build immutable-val/test, train-only derived D02/D03 dataset v0.2."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
CLASS_NAMES = {0: "D02_surface_dent", 1: "D03_carton_tear"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def split_content_hash(root: Path, split: str) -> dict[str, Any]:
    rows = []
    total = 0
    for folder in ("images", "labels"):
        base = root / folder / split
        for path in sorted(p for p in base.iterdir() if p.is_file()):
            rel = f"{folder}/{split}/{path.name}"
            total += path.stat().st_size
            rows.append(f"{rel}|{path.stat().st_size}|{sha256(path)}")
    return {
        "file_count": len(rows),
        "total_bytes": total,
        "sha256": hashlib.sha256("\n".join(rows).encode()).hexdigest(),
    }


def read_labels(path: Path) -> list[tuple[int, float, float, float, float]]:
    if not path.is_file():
        return []
    output = []
    for line in path.read_text(encoding="utf-8").splitlines():
        class_id, cx, cy, width, height = map(float, line.split())
        output.append((int(class_id), cx, cy, width, height))
    return output


def _label_path(root: Path, image_path: Path, split: str = "train") -> Path:
    return root / "labels" / split / f"{image_path.stem}.txt"


def _iou(box: np.ndarray, boxes: np.ndarray) -> np.ndarray:
    if not len(boxes):
        return np.zeros(0, dtype=float)
    top_left = np.maximum(box[:2], boxes[:, :2])
    bottom_right = np.minimum(box[2:], boxes[:, 2:])
    intersection = np.prod(np.maximum(0.0, bottom_right - top_left), axis=1)
    area = np.prod(np.maximum(0.0, box[2:] - box[:2]))
    other = np.prod(np.maximum(0.0, boxes[:, 2:] - boxes[:, :2]), axis=1)
    return intersection / np.maximum(area + other - intersection, 1e-12)


def _xyxy(
    labels: list[tuple[int, float, float, float, float]], w: int, h: int
) -> np.ndarray:
    return np.asarray(
        [
            [
                (cx - bw / 2) * w,
                (cy - bh / 2) * h,
                (cx + bw / 2) * w,
                (cy + bh / 2) * h,
            ]
            for _, cx, cy, bw, bh in labels
        ],
        dtype=float,
    ).reshape(-1, 4)


def leakage_train_relpaths(near_duplicate_json: Path) -> set[str]:
    report = json.loads(near_duplicate_json.read_text(encoding="utf-8"))
    paths = set()
    for match in report["matches"]:
        for key in ("left", "right"):
            value = match[key]
            if value.startswith("images/train/"):
                paths.add(value)
    return paths


def mine_hard_negatives(
    source_root: Path,
    image_paths: list[Path],
    model_path: Path,
    *,
    confidence: float = 0.50,
) -> list[dict[str, Any]]:
    model = YOLO(str(model_path))
    output = []
    by_path = {str(path.resolve()).casefold(): path for path in image_paths}
    # Supplying hundreds of paths at once makes the Ultralytics loader retain many
    # preprocessed tensors under WDDM.  One image per call is deterministic and
    # keeps hard-negative mining below the laptop GPU memory ceiling.
    for requested_path in image_paths:
        result = model.predict(
            source=str(requested_path),
            imgsz=960,
            conf=confidence,
            iou=0.7,
            batch=1,
            device=0,
            verbose=False,
        )[0]
        image_path = by_path[str(Path(result.path).resolve()).casefold()]
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"cannot decode {image_path}")
        h, w = image.shape[:2]
        labels = read_labels(_label_path(source_root, image_path))
        gt = _xyxy(labels, w, h)
        boxes = result.boxes.xyxy.detach().cpu().numpy()
        confs = result.boxes.conf.detach().cpu().numpy()
        classes = result.boxes.cls.detach().cpu().numpy().astype(int)
        for index, (box, score, class_id) in enumerate(zip(boxes, confs, classes)):
            max_iou = float(np.max(_iou(box, gt))) if len(gt) else 0.0
            if max_iou >= 0.50:
                continue
            output.append(
                {
                    "source_image": f"images/train/{image_path.name}",
                    "prediction_index": index,
                    "predicted_class": CLASS_NAMES.get(class_id, str(class_id)),
                    "confidence": float(score),
                    "max_gt_iou": max_iou,
                    "x1": float(box[0]),
                    "y1": float(box[1]),
                    "x2": float(box[2]),
                    "y2": float(box[3]),
                    "use": "whole-image sampling emphasis; annotations unchanged",
                }
            )
    return output


def choose_crop_targets(
    source_root: Path,
    image_paths: list[Path],
) -> list[dict[str, Any]]:
    per_class: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for image_path in image_paths:
        for index, (class_id, cx, cy, width, height) in enumerate(
            read_labels(_label_path(source_root, image_path))
        ):
            per_class[class_id].append(
                {
                    "source_image": image_path,
                    "bbox_index": index,
                    "class_id": class_id,
                    "cx": cx,
                    "cy": cy,
                    "width": width,
                    "height": height,
                    "area": width * height,
                }
            )
    q1 = {
        class_id: float(np.quantile([row["area"] for row in rows], 0.25))
        for class_id, rows in per_class.items()
    }
    by_source_class: dict[tuple[Path, int], list[dict[str, Any]]] = defaultdict(list)
    for class_id, rows in per_class.items():
        for row in rows:
            if row["area"] <= q1[class_id]:
                by_source_class[(row["source_image"], class_id)].append(row)
    selected = []
    for (image_path, class_id), rows in sorted(
        by_source_class.items(), key=lambda item: (str(item[0][0]), item[0][1])
    ):
        limit = 2 if class_id == 0 else 1
        chosen: list[dict[str, Any]] = []
        for row in sorted(rows, key=lambda value: (value["area"], value["bbox_index"])):
            if any(
                math.hypot(row["cx"] - old["cx"], row["cy"] - old["cy"]) < 0.12
                for old in chosen
            ):
                continue
            chosen.append(row)
            if len(chosen) == limit:
                break
        if len(chosen) < limit:
            for row in sorted(
                rows, key=lambda value: (value["area"], value["bbox_index"])
            ):
                if row not in chosen:
                    chosen.append(row)
                    if len(chosen) == limit:
                        break
        selected.extend(chosen)
    return selected


def crop_bounds(
    image_w: int,
    image_h: int,
    target: dict[str, Any],
    *,
    context_scale: float = 2.5,
    minimum_side: int = 160,
) -> tuple[int, int, int, int]:
    target_w = target["width"] * image_w
    target_h = target["height"] * image_h
    side = min(
        max(max(target_w, target_h) * context_scale, minimum_side), image_w, image_h
    )
    center_x, center_y = target["cx"] * image_w, target["cy"] * image_h
    x1 = min(max(center_x - side / 2, 0), image_w - side)
    y1 = min(max(center_y - side / 2, 0), image_h - side)
    return int(round(x1)), int(round(y1)), int(round(x1 + side)), int(round(y1 + side))


def transform_labels_for_crop(
    labels: list[tuple[int, float, float, float, float]],
    image_w: int,
    image_h: int,
    bounds: tuple[int, int, int, int],
) -> list[tuple[int, float, float, float, float]]:
    crop_x1, crop_y1, crop_x2, crop_y2 = bounds
    crop_w, crop_h = crop_x2 - crop_x1, crop_y2 - crop_y1
    output = []
    for class_id, cx, cy, width, height in labels:
        box_x1, box_y1 = (cx - width / 2) * image_w, (cy - height / 2) * image_h
        box_x2, box_y2 = (cx + width / 2) * image_w, (cy + height / 2) * image_h
        center_x, center_y = cx * image_w, cy * image_h
        if not (crop_x1 <= center_x <= crop_x2 and crop_y1 <= center_y <= crop_y2):
            continue
        clipped_x1, clipped_y1 = max(box_x1, crop_x1), max(box_y1, crop_y1)
        clipped_x2, clipped_y2 = min(box_x2, crop_x2), min(box_y2, crop_y2)
        original_area = max((box_x2 - box_x1) * (box_y2 - box_y1), 1e-12)
        clipped_area = max(clipped_x2 - clipped_x1, 0) * max(clipped_y2 - clipped_y1, 0)
        if clipped_area / original_area < 0.50:
            continue
        new_cx = ((clipped_x1 + clipped_x2) / 2 - crop_x1) / crop_w
        new_cy = ((clipped_y1 + clipped_y2) / 2 - crop_y1) / crop_h
        new_w = (clipped_x2 - clipped_x1) / crop_w
        new_h = (clipped_y2 - clipped_y1) / crop_h
        output.append((class_id, new_cx, new_cy, new_w, new_h))
    return output


def write_labels(
    path: Path, labels: list[tuple[int, float, float, float, float]]
) -> None:
    text = "\n".join(
        f"{class_id} {cx:.10f} {cy:.10f} {width:.10f} {height:.10f}"
        for class_id, cx, cy, width, height in labels
    )
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_dataset(
    source_root: Path,
    output_root: Path,
    model_path: Path,
    near_duplicate_json: Path,
    *,
    crop_strategy: str,
) -> dict[str, Any]:
    if output_root.exists():
        raise FileExistsError(f"refusing overwrite: {output_root}")
    for folder in ("images", "labels"):
        for split in ("train", "val", "test"):
            (output_root / folder / split).mkdir(parents=True, exist_ok=False)

    excluded = leakage_train_relpaths(near_duplicate_json)
    copied_base = []
    eligible_train = []
    for split in ("train", "val", "test"):
        for image_path in sorted(
            p
            for p in (source_root / "images" / split).iterdir()
            if p.suffix.lower() in IMAGE_SUFFIXES
        ):
            rel = f"images/{split}/{image_path.name}"
            if split == "train" and rel in excluded:
                continue
            label_path = _label_path(source_root, image_path, split)
            shutil.copy2(image_path, output_root / rel)
            shutil.copy2(
                label_path,
                output_root / "labels" / split / f"{image_path.stem}.txt",
            )
            if split == "train":
                eligible_train.append(image_path)
            copied_base.append(rel)

    hard_negatives = mine_hard_negatives(source_root, eligible_train, model_path)
    hard_sources = (
        sorted({row["source_image"] for row in hard_negatives})
        if crop_strategy == "all-small-hard"
        else []
    )
    hard_example_rows = []
    for index, rel in enumerate(hard_sources, 1):
        source_image = source_root / rel
        source_label = _label_path(source_root, source_image)
        name = f"hn_{index:04d}_{source_image.name}"
        target_image = output_root / "images" / "train" / name
        target_label = output_root / "labels" / "train" / f"{Path(name).stem}.txt"
        shutil.copy2(source_image, target_image)
        shutil.copy2(source_label, target_label)
        hard_example_rows.append(
            {
                "derived_image": f"images/train/{name}",
                "source_image": rel,
                "strategy": "whole-image sampling emphasis",
                "source_image_sha256": sha256(source_image),
                "derived_image_sha256": sha256(target_image),
                "label_sha256": sha256(target_label),
            }
        )

    crop_rows = []
    targets = choose_crop_targets(source_root, eligible_train)
    if crop_strategy == "d02-single":
        seen_sources: set[Path] = set()
        filtered_targets = []
        for target in targets:
            source_image = target["source_image"]
            if target["class_id"] == 0 and source_image not in seen_sources:
                filtered_targets.append(target)
                seen_sources.add(source_image)
        targets = filtered_targets
    for index, target in enumerate(targets, 1):
        source_image = target["source_image"]
        image = cv2.imread(str(source_image))
        if image is None:
            raise ValueError(f"cannot decode {source_image}")
        h, w = image.shape[:2]
        bounds = crop_bounds(w, h, target)
        x1, y1, x2, y2 = bounds
        crop = image[y1:y2, x1:x2]
        labels = read_labels(_label_path(source_root, source_image))
        transformed = transform_labels_for_crop(labels, w, h, bounds)
        if not transformed:
            raise RuntimeError(
                f"derived crop lost all labels: {source_image}#{target['bbox_index']}"
            )
        resized = cv2.resize(crop, (640, 640), interpolation=cv2.INTER_LINEAR)
        name = f"crop_{index:04d}_c{target['class_id']}_{source_image.stem}.jpg"
        target_image = output_root / "images" / "train" / name
        target_label = output_root / "labels" / "train" / f"{Path(name).stem}.txt"
        if not cv2.imwrite(str(target_image), resized, [cv2.IMWRITE_JPEG_QUALITY, 95]):
            raise OSError(f"cannot write {target_image}")
        write_labels(target_label, transformed)
        crop_rows.append(
            {
                "derived_image": f"images/train/{name}",
                "source_image": f"images/train/{source_image.name}",
                "source_bbox_id": f"images/train/{source_image.name}#{target['bbox_index']}",
                "source_class_id": target["class_id"],
                "source_bbox_area": target["area"],
                "crop_x1": x1,
                "crop_y1": y1,
                "crop_x2": x2,
                "crop_y2": y2,
                "context_scale": 2.5,
                "output_size": 640,
                "transformed_label_count": len(transformed),
                "source_image_sha256": sha256(source_image),
                "derived_image_sha256": sha256(target_image),
                "derived_label_sha256": sha256(target_label),
            }
        )

    (output_root / "dataset.yaml").write_text(
        "\n".join(
            [
                f"path: {output_root.as_posix()}",
                "train: images/train",
                "val: images/val",
                "test: images/test",
                "names:",
                "  0: D02_surface_dent",
                "  1: D03_carton_tear",
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_csv(output_root / "object-centric-crop-manifest-v0.2.csv", crop_rows)
    _write_csv(output_root / "hard-negative-manifest-v0.2.csv", hard_negatives)
    _write_csv(output_root / "hard-example-emphasis-v0.2.csv", hard_example_rows)
    _write_csv(
        output_root / "excluded-leakage-v0.2.csv",
        [
            {"source_image": rel, "reason": "perceptual cross-split leakage"}
            for rel in sorted(excluded)
        ],
    )

    source_hashes = {
        split: split_content_hash(source_root, split)
        for split in ("train", "val", "test")
    }
    derived_hashes = {
        split: split_content_hash(output_root, split)
        for split in ("train", "val", "test")
    }
    lock = {
        "dataset_version": output_root.name,
        "generated_at": datetime.now().astimezone().isoformat(),
        "source_dataset": str(source_root),
        "source_dataset_lock": str(source_root / "dataset-lock.json"),
        "source_dataset_lock_sha256": sha256(source_root / "dataset-lock.json"),
        "random_seed": 42,
        "derived_rules": {
            "train_only": True,
            "excluded_cross_split_leakage_sources": sorted(excluded),
            "crop_strategy": crop_strategy,
            "object_crops": "smallest train quartile; geometry-derived labels; all-small-hard uses D02 max 2/source + D03 max 1/source; d02-single uses D02 max 1/source",
            "hard_examples": "all-small-hard only: one exact train-only sampling copy per source image containing confidence>=0.50 unmatched active-model prediction; labels unchanged",
            "val_modified": False,
            "test_modified": False,
        },
        "counts": {
            "base_train_images": len(eligible_train),
            "excluded_leakage_train_images": len(excluded),
            "hard_negative_predictions": len(hard_negatives),
            "hard_example_images": len(hard_example_rows),
            "object_centric_crops": len(crop_rows),
            "derived_train_images": len(list((output_root / "images/train").iterdir())),
        },
        "source_split_hashes": source_hashes,
        "derived_split_hashes": derived_hashes,
        "val_hash_equal_to_v0.1": source_hashes["val"] == derived_hashes["val"],
        "test_hash_equal_to_v0.1": source_hashes["test"] == derived_hashes["test"],
    }
    lock_path = output_root / f"dataset-lock-{output_root.name.rsplit('-', 1)[-1]}.json"
    lock_path.write_text(
        json.dumps(lock, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_root / "README.md").write_text(
        f"# {output_root.name}\n\n"
        "Derived train-only dataset for Detector Optimization Goal v2.0. "
        "Validation and test images/labels are byte-identical to v0.1. "
        "All crop labels are deterministic geometry transforms; no manual or synthetic boxes were added.\n",
        encoding="utf-8",
    )
    lock["dataset_lock_path"] = str(lock_path)
    lock["dataset_lock_sha256"] = sha256(lock_path)
    return lock


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--active-model", type=Path, required=True)
    parser.add_argument("--near-duplicate-json", type=Path, required=True)
    parser.add_argument(
        "--crop-strategy",
        choices=("all-small-hard", "d02-single"),
        default="all-small-hard",
    )
    args = parser.parse_args()
    report = build_dataset(
        args.source,
        args.output,
        args.active_model,
        args.near_duplicate_json,
        crop_strategy=args.crop_strategy,
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
