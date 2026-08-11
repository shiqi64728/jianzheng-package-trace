from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.training import prepare_d02_d03_dataset as prepare  # noqa: E402


class D02D03DatasetPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.external = self.root / "external"
        self.raw = self.external / "raw/roboflow/defect-cardboard-h0kjy/extracted"
        self.manifest = self.external / "converted/manifests/defect.csv"
        self.license = self.external / "reports/license.json"
        self.mapping = self.root / "mapping.json"
        self.output = self.root / "training/detect-d02-d03-v0.1"
        self.rows = [
            self.make_row("dent.png", "train", "dent", [10, 20, 30, 40], "accepted"),
            self.make_row("hole.png", "valid", "hole", [20, 10, 20, 30], "accepted"),
            self.make_row("dent-test.png", "test", "dent", [5, 5, 10, 10], "accepted"),
            self.make_row(
                "dirt.png", "train", "dirt", [1, 1, 20, 20], "review_required"
            ),
            self.make_row(
                "review.png", "train", "dent", [1, 1, 20, 20], "review_required"
            ),
        ]
        self.write_inputs()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_row(
        self,
        name: str,
        split: str,
        original_class: str,
        bbox: list[float],
        quarantine_status: str,
    ) -> dict[str, str]:
        path = self.raw / split / name
        path.parent.mkdir(parents=True, exist_ok=True)
        value = int(hashlib.sha256(name.encode()).hexdigest()[:2], 16)
        image = np.full((100, 100, 3), value, dtype=np.uint8)
        image[0, 0] = (value, (value + 31) % 256, (value + 67) % 256)
        self.assertTrue(cv2.imwrite(str(path), image))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        source_rel = path.relative_to(self.external).as_posix()
        annotation = {
            "original_annotation_id": f"ann-{name}",
            "original_image_id": f"img-{name}",
            "original_class": original_class,
            "bbox": bbox,
            "iscrowd": 0,
        }
        mapped = {"dent": "D02", "hole": "D03"}.get(original_class, "D04")
        return {
            "external_record_id": f"record-{name}",
            "source_id": prepare.SOURCE_ID,
            "original_image_relpath": source_rel,
            "original_split": split,
            "original_class": original_class,
            "mapped_project_status": "direct"
            if original_class != "dirt"
            else "candidate",
            "mapped_project_class": mapped,
            "requires_manual_review": str(quarantine_status != "accepted").lower(),
            "quarantine_status": quarantine_status,
            "sha256": digest,
            "width": "100",
            "height": "100",
            "annotation_records_json": json.dumps([annotation]),
        }

    def write_inputs(self) -> None:
        self.manifest.parent.mkdir(parents=True, exist_ok=True)
        fields = list(self.rows[0])
        with self.manifest.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(self.rows)
        self.license.parent.mkdir(parents=True, exist_ok=True)
        self.license.write_text(
            json.dumps(
                {
                    "sources": [
                        {
                            "source_id": prepare.SOURCE_ID,
                            "audit_status": "passed",
                            "blocking_issue": "",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.mapping.write_text(
            json.dumps(
                {
                    "mapping_version": "0.1",
                    "sources": {
                        prepare.SOURCE_ID: {
                            "classes": {
                                "dent": {"mapped_project_class": "D02"},
                                "hole": {"mapped_project_class": "D03"},
                            }
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

    def build(self, output: Path | None = None) -> dict:
        return prepare.build_dataset(
            self.external,
            self.manifest,
            self.license,
            self.mapping,
            output or self.output,
            "source-commit",
            "2026-08-11T00:00:00+08:00",
        )

    def rewrite_rows(self) -> None:
        self.write_inputs()

    def test_dent_maps_to_class_zero(self) -> None:
        self.build()
        label = (self.output / "labels/train/dent.txt").read_text(encoding="utf-8")
        self.assertTrue(label.startswith("0 "))

    def test_hole_maps_to_class_one(self) -> None:
        self.build()
        label = (self.output / "labels/val/hole.txt").read_text(encoding="utf-8")
        self.assertTrue(label.startswith("1 "))

    def test_dirt_image_is_excluded_as_a_whole(self) -> None:
        result = self.build()
        self.assertEqual(result["report"]["excluded_reason_counts"]["DIRT_PRESENT"], 1)
        self.assertFalse((self.output / "images/train/dirt.png").exists())

    def test_bbox_normalization_is_correct(self) -> None:
        self.build()
        values = (self.output / "labels/train/dent.txt").read_text().split()
        self.assertEqual(values[0], "0")
        self.assertEqual([float(value) for value in values[1:]], [0.25, 0.4, 0.3, 0.4])

    def test_zero_width_bbox_fails(self) -> None:
        annotations = json.loads(self.rows[0]["annotation_records_json"])
        annotations[0]["bbox"] = [10, 10, 0, 20]
        self.rows[0]["annotation_records_json"] = json.dumps(annotations)
        self.rewrite_rows()
        with self.assertRaises(prepare.DatasetPreparationError):
            self.build()
        self.assertFalse(self.output.exists())

    def test_out_of_bounds_bbox_fails(self) -> None:
        annotations = json.loads(self.rows[0]["annotation_records_json"])
        annotations[0]["bbox"] = [90, 90, 20, 20]
        self.rows[0]["annotation_records_json"] = json.dumps(annotations)
        self.rewrite_rows()
        with self.assertRaises(prepare.DatasetPreparationError):
            self.build()

    def test_missing_image_fails(self) -> None:
        (self.external / self.rows[0]["original_image_relpath"]).unlink()
        with self.assertRaises(prepare.DatasetPreparationError):
            self.build()

    def test_blocked_record_is_excluded(self) -> None:
        self.rows.append(
            self.make_row("blocked.png", "train", "dent", [1, 1, 20, 20], "blocked")
        )
        self.rewrite_rows()
        result = self.build()
        self.assertEqual(
            result["report"]["excluded_reason_counts"]["QUARANTINE_NOT_ACCEPTED"], 2
        )

    def test_review_required_record_is_excluded(self) -> None:
        result = self.build()
        self.assertEqual(
            result["report"]["excluded_reason_counts"]["QUARANTINE_NOT_ACCEPTED"], 1
        )
        self.assertFalse((self.output / "images/train/review.png").exists())

    def test_copy_sha256_matches_source(self) -> None:
        self.build()
        source = self.external / self.rows[0]["original_image_relpath"]
        copy = self.output / "images/train/dent.png"
        self.assertEqual(prepare.sha256_file(source), prepare.sha256_file(copy))

    def test_raw_is_not_modified(self) -> None:
        before = {path: prepare.sha256_file(path) for path in self.raw.rglob("*.png")}
        self.build()
        after = {path: prepare.sha256_file(path) for path in self.raw.rglob("*.png")}
        self.assertEqual(before, after)

    def test_source_splits_are_preserved(self) -> None:
        result = self.build()
        self.assertEqual(result["lock"]["train_image_count"], 1)
        self.assertEqual(result["lock"]["val_image_count"], 1)
        self.assertEqual(result["lock"]["test_image_count"], 1)

    def test_cross_split_exact_duplicate_fails(self) -> None:
        source = self.external / self.rows[0]["original_image_relpath"]
        duplicate = self.external / self.rows[1]["original_image_relpath"]
        duplicate.write_bytes(source.read_bytes())
        self.rows[1]["sha256"] = prepare.sha256_file(duplicate)
        self.rewrite_rows()
        with self.assertRaisesRegex(prepare.DatasetPreparationError, "精确重复"):
            self.build()

    def test_dataset_yaml_contains_fixed_classes_and_real_test(self) -> None:
        self.build()
        text = (self.output / "dataset.yaml").read_text(encoding="utf-8")
        self.assertIn("0: D02_surface_dent", text)
        self.assertIn("1: D03_carton_tear", text)
        self.assertIn("test: images/test", text)

    def test_dataset_lock_is_reproducible_with_fixed_timestamp(self) -> None:
        first = self.build(self.root / "training/first")["lock"]
        second = self.build(self.root / "training/second")["lock"]
        self.assertEqual(first, second)

    def test_existing_frozen_directory_is_rejected(self) -> None:
        self.output.mkdir(parents=True)
        with self.assertRaisesRegex(prepare.DatasetPreparationError, "拒绝覆盖"):
            self.build()

    def test_validator_rejects_invalid_class_id(self) -> None:
        self.build()
        label = self.output / "labels/train/dent.txt"
        label.write_text(label.read_text().replace("0 ", "2 "), encoding="utf-8")
        with self.assertRaises(prepare.DatasetPreparationError):
            prepare.validate_frozen_dataset(self.output)

    def test_copies_are_regular_independent_files(self) -> None:
        self.build()
        source = self.external / self.rows[0]["original_image_relpath"]
        copy = self.output / "images/train/dent.png"
        self.assertFalse(copy.is_symlink())
        self.assertFalse(source.samefile(copy))


if __name__ == "__main__":
    unittest.main()
