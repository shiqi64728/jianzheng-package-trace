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

from scripts.dataset import audit_external_datasets as auditor  # noqa: E402
from scripts.dataset import build_external_manifests as builder  # noqa: E402
from dataset.external_test_support import MAPPING, SCHEMA, create_external_fixture  # noqa: E402


class ExternalDatasetAuditTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.paths = create_external_fixture(Path(self.temp.name))
        builder.build_all(
            self.paths["external"],
            SCHEMA,
            MAPPING,
            self.paths["manifests"],
            self.paths["reports"] / "build.json",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def audit(self) -> dict:
        return auditor.audit_all(
            self.paths["external"],
            self.paths["manifests"],
            self.paths["registry"],
            MAPPING,
            self.paths["reports"],
        )

    def test_within_dataset_duplicate_is_reported_without_deletion(self) -> None:
        before = sum(
            1 for path in (self.paths["external"] / "raw").rglob("*") if path.is_file()
        )
        summary = self.audit()
        after = sum(
            1 for path in (self.paths["external"] / "raw").rglob("*") if path.is_file()
        )
        self.assertEqual(summary["duplicate_summary"]["duplicate_extra_images"], 1)
        self.assertEqual(before, after)
        self.assertTrue(
            (
                self.paths["external"]
                / "quarantine/manifests/duplicate-records-v0.1.csv"
            ).is_file()
        )

    def test_cross_dataset_duplicate_is_detected(self) -> None:
        report, _, _ = auditor._duplicate_audit(
            [
                {
                    "external_record_id": "a",
                    "source_id": "s1",
                    "original_image_relpath": "a.jpg",
                    "sha256": "x",
                    "original_split": "train",
                    "original_class": "normal",
                },
                {
                    "external_record_id": "b",
                    "source_id": "s2",
                    "original_image_relpath": "b.jpg",
                    "sha256": "x",
                    "original_split": "train",
                    "original_class": "normal",
                },
            ]
        )
        self.assertEqual(report["summary"]["cross_dataset_groups"], 1)

    def test_cross_split_duplicate_is_training_blocker(self) -> None:
        report, quarantine, blocked = auditor._duplicate_audit(
            [
                {
                    "external_record_id": "a",
                    "source_id": "s",
                    "original_image_relpath": "a.jpg",
                    "sha256": "x",
                    "original_split": "train",
                    "original_class": "normal",
                },
                {
                    "external_record_id": "b",
                    "source_id": "s",
                    "original_image_relpath": "b.jpg",
                    "sha256": "x",
                    "original_split": "test",
                    "original_class": "normal",
                },
            ]
        )
        self.assertEqual(report["summary"]["cross_split_groups"], 1)
        self.assertEqual(blocked, {"a", "b"})
        self.assertTrue(
            all(row["reason_code"] == "CROSS_SPLIT_DUPLICATE" for row in quarantine)
        )

    def test_conflicting_labels_are_training_blocker(self) -> None:
        report, _, blocked = auditor._duplicate_audit(
            [
                {
                    "external_record_id": "a",
                    "source_id": "s",
                    "original_image_relpath": "a.jpg",
                    "sha256": "x",
                    "original_split": "train",
                    "original_class": "normal",
                },
                {
                    "external_record_id": "b",
                    "source_id": "s",
                    "original_image_relpath": "b.jpg",
                    "sha256": "x",
                    "original_split": "train",
                    "original_class": "damaged",
                },
            ]
        )
        self.assertEqual(report["summary"]["conflicting_label_groups"], 1)
        self.assertEqual(blocked, {"a", "b"})

    def test_missing_license_is_blocked(self) -> None:
        (self.paths["licenses"] / "CC-BY-4.0-legalcode.txt").unlink()
        self.audit()
        report = json.loads(
            (self.paths["reports"] / "external-license-audit-v0.1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(
            any(row["audit_status"] == "blocked" for row in report["sources"])
        )
        blocked = (
            self.paths["external"]
            / "quarantine/manifests/blocked-license-records-v0.1.csv"
        )
        with blocked.open("r", encoding="utf-8-sig", newline="") as handle:
            self.assertGreater(len(list(csv.DictReader(handle))), 1)

    def test_mapping_audit_contains_d04_candidate(self) -> None:
        self.audit()
        path = self.paths["reports"] / "external-class-mapping-audit-v0.1.csv"
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        dirt = next(row for row in rows if row["original_class"] == "dirt")
        self.assertEqual(dirt["mapped_project_status"], "candidate")
        self.assertEqual(dirt["mapped_project_class"], "D04")

    def test_readiness_blocks_continuous_nodes_and_segmentation(self) -> None:
        self.audit()
        report = json.loads(
            (self.paths["reports"] / "external-dataset-readiness-v0.1.json").read_text(
                encoding="utf-8"
            )
        )
        states = {row["task"]: row["status"] for row in report["tasks"]}
        self.assertEqual(states["真实连续节点定位"], "not_ready")
        self.assertEqual(states["实例分割"], "not_ready")
        self.assertEqual(states["D04候选目标检测"], "not_ready")

    def test_audit_does_not_modify_raw(self) -> None:
        files = sorted(
            path
            for path in (self.paths["external"] / "raw").rglob("*")
            if path.is_file()
        )
        before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
        summary = self.audit()
        after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
        self.assertTrue(summary["integrity"]["passed"])
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
