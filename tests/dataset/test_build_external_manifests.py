from __future__ import annotations

import csv
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.dataset import build_external_manifests as builder  # noqa: E402
from dataset.external_test_support import MAPPING, SCHEMA, create_external_fixture  # noqa: E402


class ExternalManifestBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.paths = create_external_fixture(Path(self.temp.name))

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self) -> dict:
        return builder.build_all(
            self.paths["external"],
            SCHEMA,
            MAPPING,
            self.paths["manifests"],
            self.paths["reports"] / "build.json",
        )

    def rows(self, name: str) -> list[dict[str, str]]:
        with (self.paths["manifests"] / name).open(
            "r", encoding="utf-8-sig", newline=""
        ) as handle:
            return list(csv.DictReader(handle))

    def test_defect_mappings_and_dirt_review(self) -> None:
        self.build()
        rows = self.rows("defect-cardboard-v0.1.csv")
        dent = next(row for row in rows if row["original_split"] == "test")
        hole = next(row for row in rows if row["original_split"] == "valid")
        mixed = next(row for row in rows if row["original_split"] == "train")
        self.assertEqual(
            (dent["mapped_project_status"], dent["mapped_project_class"]),
            ("direct", "D02"),
        )
        self.assertEqual(
            (hole["mapped_project_status"], hole["mapped_project_class"]),
            ("direct", "D03"),
        )
        self.assertEqual(mixed["mapped_project_status"], "candidate")
        self.assertIn("D04", mixed["mapped_project_class"])
        self.assertEqual(mixed["requires_manual_review"], "true")

    def test_bbox_and_all_annotations_are_preserved_without_fake_polygon(self) -> None:
        report = self.build()
        self.assertEqual(
            report["manifests"]["defect-cardboard-v0.1.csv"]["annotation_records"], 4
        )
        for row in self.rows("defect-cardboard-v0.1.csv"):
            self.assertEqual(row["original_annotation_type"], "bbox")
            for annotation in json.loads(row["annotation_records_json"]):
                self.assertIn("bbox", annotation)
                self.assertNotIn("polygon", annotation)

    def test_missing_coco_image_fails(self) -> None:
        missing = (
            self.paths["external"]
            / "raw/roboflow/defect-cardboard-h0kjy/extracted/test/test.jpg"
        )
        missing.unlink()
        with self.assertRaises(FileNotFoundError):
            self.build()

    def test_original_coco_is_not_modified(self) -> None:
        coco = (
            self.paths["external"]
            / "raw/roboflow/defect-cardboard-h0kjy/extracted/train/_annotations.coco.json"
        )
        before = hashlib.sha256(coco.read_bytes()).hexdigest()
        self.build()
        self.assertEqual(before, hashlib.sha256(coco.read_bytes()).hexdigest())

    def test_damaged_mapping_split_and_duplicates(self) -> None:
        self.build()
        rows = self.rows("damaged-box-detection-v0.1.csv")
        damaged = [row for row in rows if row["original_class"] == "damagedpackages"]
        normal = [row for row in rows if row["original_class"] == "undamagedpackages"]
        self.assertTrue(
            all(row["mapped_project_class"] == "ABNORMAL_GENERAL" for row in damaged)
        )
        self.assertTrue(all(row["mapped_project_class"] == "NORMAL" for row in normal))
        self.assertEqual(
            {row["original_split"] for row in rows}, {"train", "valid", "test"}
        )
        duplicate = [row for row in rows if row["duplicate_group_id"]]
        self.assertEqual(len(duplicate), 2)
        self.assertEqual(len({row["duplicate_group_id"] for row in duplicate}), 1)

    def test_damaged_never_generates_project_damage_subclasses_or_parent_guess(
        self,
    ) -> None:
        self.build()
        rows = self.rows("damaged-box-detection-v0.1.csv")
        self.assertFalse(
            any(
                row["mapped_project_class"] in {"D01", "D02", "D03", "D04", "D05"}
                for row in rows
            )
        )
        self.assertTrue(all(not row["parent_or_augmented_from"] for row in rows))
        self.assertTrue(all("独立物理包裹" in row["notes"] for row in rows))

    def test_tampar_probable_and_unresolved_pairing(self) -> None:
        self.build()
        rows = self.rows("tampar-pairs-v0.1.csv")
        probable = next(row for row in rows if row["pairing_confidence"] == "probable")
        unresolved = next(
            row for row in rows if row["pairing_confidence"] == "unresolved"
        )
        self.assertTrue(probable["pair_id"])
        self.assertTrue(probable["reference_image_relpath"])
        self.assertEqual(unresolved["quarantine_reason"], "TAMPAR_PAIR_UNRESOLVED")
        self.assertFalse(unresolved["reference_image_relpath"])

    def test_tampar_direct_unlabeled_file_does_not_become_an_operation(self) -> None:
        self.assertEqual(
            builder._tampar_operation(
                ("unlabeled", "test", "aruco_0001.jpg"), "aruco_0001.jpg"
            ),
            "unlabeled",
        )

    def test_tampar_does_not_invent_nodes_damage_classes_or_annotations(self) -> None:
        report = self.build()
        rows = self.rows("tampar-pairs-v0.1.csv")
        self.assertEqual(
            report["manifests"]["tampar-pairs-v0.1.csv"]["annotation_records"], 1
        )
        self.assertFalse(any(row["mapped_project_class"] for row in rows))
        fields = set(rows[0])
        self.assertTrue(
            {
                "package_id",
                "sequence_id",
                "node_id",
                "capture_time",
                "first_abnormal_node",
            }.isdisjoint(fields)
        )
        self.assertTrue(
            all(row["mapped_project_status"] == "change_detection_only" for row in rows)
        )

    def test_stats_are_separate_blocked_non_image_records(self) -> None:
        self.build()
        rows = self.rows("public-stats-v0.1.csv")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["original_annotation_type"], "statistics")
        self.assertEqual(rows[0]["project_task"], "industry_statistics")
        self.assertEqual(rows[0]["quarantine_status"], "blocked")
        self.assertFalse(rows[0]["original_image_relpath"])

    def test_manifests_have_utf8_bom_and_relative_paths(self) -> None:
        self.build()
        for path in self.paths["manifests"].glob("*.csv"):
            self.assertEqual(path.read_bytes()[:3], b"\xef\xbb\xbf")
            for row in self.rows(path.name):
                value = row["original_image_relpath"]
                self.assertFalse(value.startswith(("/", "\\")))
                self.assertNotIn(":\\", value)


if __name__ == "__main__":
    unittest.main()
