from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from scripts.calibration.real_world_calibration_v11 import (
    CalibrationInputError,
    calibration_metrics,
    load_completed_captures,
    sequence_inventory,
)


FIELDS = [
    "package_alias",
    "node_id",
    "surface",
    "capture_time",
    "image_path",
    "ownership_status",
    "privacy_status",
    "expected_change",
    "change_applied_after_node",
    "change_surface",
    "change_type",
    "collection_status",
]


class RealWorldCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image = self.root / "capture.jpg"
        self.image.write_bytes(b"fixture")

    def tearDown(self):
        self.temp.cleanup()

    def write(self, rows, fields=FIELDS):
        path = self.root / "worklist.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def row(self, **updates):
        row = {
            "package_alias": "CASE-R01",
            "node_id": "N1",
            "surface": "front",
            "capture_time": "2026-08-12T12:00:00+08:00",
            "image_path": str(self.image),
            "ownership_status": "SELF_OWNED",
            "privacy_status": "PASSED",
            "expected_change": "NORMAL",
            "change_applied_after_node": "",
            "change_surface": "",
            "change_type": "NORMAL_CONTROL",
            "collection_status": "CAPTURED",
        }
        row.update(updates)
        return row

    def test_valid_capture_is_loaded(self):
        rows = load_completed_captures(self.write([self.row()]), allowed_root=self.root)
        self.assertEqual(len(rows), 1)

    def test_pending_capture_is_ignored(self):
        path = self.write([self.row(collection_status="NOT_CAPTURED", image_path="")])
        self.assertEqual(load_completed_captures(path, allowed_root=self.root), [])

    def test_pii_column_is_rejected(self):
        fields = FIELDS + ["phone"]
        with self.assertRaisesRegex(CalibrationInputError, "PII fields"):
            load_completed_captures(
                self.write([{**self.row(), "phone": "fixture"}], fields),
                allowed_root=self.root,
            )

    def test_timezone_is_required(self):
        with self.assertRaisesRegex(CalibrationInputError, "timezone"):
            load_completed_captures(
                self.write([self.row(capture_time="2026-08-12T12:00:00")]),
                allowed_root=self.root,
            )

    def test_privacy_must_pass(self):
        with self.assertRaisesRegex(CalibrationInputError, "privacy_status"):
            load_completed_captures(
                self.write([self.row(privacy_status="PENDING")]), allowed_root=self.root
            )

    def test_ownership_must_be_approved(self):
        with self.assertRaisesRegex(CalibrationInputError, "ownership"):
            load_completed_captures(
                self.write([self.row(ownership_status="UNKNOWN")]),
                allowed_root=self.root,
            )

    def test_duplicate_capture_is_rejected(self):
        with self.assertRaisesRegex(CalibrationInputError, "duplicate capture"):
            load_completed_captures(
                self.write([self.row(), self.row()]), allowed_root=self.root
            )

    def test_front_complete_inventory(self):
        captures = [self.row(node_id=node) for node in ("N1", "N2", "N3")]
        result = sequence_inventory(captures)
        self.assertTrue(result["qualified_packages"][0]["front_complete"])
        self.assertFalse(result["qualified_packages"][0]["full_multisurface"])

    def test_multisurface_inventory(self):
        captures = [
            self.row(node_id=node, surface=surface)
            for node in ("N1", "N2", "N3")
            for surface in ("front", "left", "right", "top")
        ]
        self.assertTrue(
            sequence_inventory(captures)["packages"][0]["full_multisurface"]
        )

    def test_metrics_compute_all_rates(self):
        rows = [
            {
                "registration_status": "SUCCESS",
                "expected_change": False,
                "change_observed": False,
                "package_alias": "R1",
            },
            {
                "registration_status": "LOW_CONFIDENCE",
                "expected_change": False,
                "change_observed": True,
                "package_alias": "R1",
            },
            {
                "registration_status": "FAILED",
                "expected_change": True,
                "change_observed": True,
                "package_alias": "R2",
                "first_abnormal_interval_correct": False,
                "trigger_surface_correct": True,
            },
        ]
        result = calibration_metrics(rows)
        self.assertAlmostEqual(result["registration_usable_rate"], 2 / 3)
        self.assertEqual(result["normal_false_alarm_rate"], 0.5)
        self.assertEqual(result["changed_pair_detection_rate"], 1.0)
        self.assertEqual(result["first_abnormal_interval_accuracy"], 0.5)
        self.assertEqual(result["trigger_surface_accuracy"], 1.0)

    def test_zero_denominator_returns_none(self):
        result = calibration_metrics([])
        self.assertIsNone(result["registration_usable_rate"])
        self.assertEqual(result["statistical_scope"], "OBSERVATIONAL")

    def test_three_sequences_reach_engineering_scope(self):
        rows = [
            {
                "registration_status": "SUCCESS",
                "expected_change": False,
                "change_observed": False,
                "package_alias": f"R{i}",
            }
            for i in range(3)
        ]
        self.assertEqual(
            calibration_metrics(rows)["statistical_scope"], "ENGINEERING_TARGET"
        )

    def test_invalid_registration_status_is_rejected(self):
        with self.assertRaisesRegex(CalibrationInputError, "registration_status"):
            calibration_metrics(
                [
                    {
                        "registration_status": "UNKNOWN",
                        "expected_change": False,
                        "change_observed": False,
                    }
                ]
            )


if __name__ == "__main__":
    unittest.main()
