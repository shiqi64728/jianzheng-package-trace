from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.training.build_derived_detector_dataset_v20 import (
    crop_bounds,
    leakage_train_relpaths,
    split_content_hash,
    transform_labels_for_crop,
)
from scripts.training.finalize_detector_goal_v20 import promotion_gate, reserve_lock
from scripts.training.run_detector_goal_v20 import load_config


class DerivedDatasetTests(unittest.TestCase):
    def test_split_hash_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for kind in ("images", "labels"):
                (root / kind / "val").mkdir(parents=True)
            (root / "images/val/a.jpg").write_bytes(b"image")
            (root / "labels/val/a.txt").write_text("0 0.5 0.5 0.2 0.2\n")
            self.assertEqual(
                split_content_hash(root, "val"), split_content_hash(root, "val")
            )

    def test_split_hash_detects_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for kind in ("images", "labels"):
                (root / kind / "test").mkdir(parents=True)
            image = root / "images/test/a.jpg"
            image.write_bytes(b"before")
            (root / "labels/test/a.txt").write_text("")
            before = split_content_hash(root, "test")["sha256"]
            image.write_bytes(b"after")
            self.assertNotEqual(before, split_content_hash(root, "test")["sha256"])

    def test_crop_bounds_keep_context_and_image_bounds(self) -> None:
        target = {"width": 0.2, "height": 0.25, "cx": 0.15, "cy": 0.15}
        left, top, right, bottom = crop_bounds(
            100, 80, target, context_scale=2.0, minimum_side=40
        )
        self.assertGreaterEqual(left, 0)
        self.assertGreaterEqual(top, 0)
        self.assertLessEqual(right, 100)
        self.assertLessEqual(bottom, 80)

    def test_crop_label_transform_is_geometry_derived(self) -> None:
        labels = [(0, 0.5, 0.5, 0.2, 0.2)]
        transformed = transform_labels_for_crop(labels, 100, 100, (25, 25, 75, 75))
        self.assertEqual(len(transformed), 1)
        cls, x, y, width, height = transformed[0]
        self.assertEqual(cls, 0)
        self.assertAlmostEqual(x, 0.5)
        self.assertAlmostEqual(y, 0.5)
        self.assertAlmostEqual(width, 0.4)
        self.assertAlmostEqual(height, 0.4)

    def test_crop_drops_boxes_outside_crop(self) -> None:
        labels = [(0, 0.9, 0.9, 0.1, 0.1)]
        self.assertEqual(
            transform_labels_for_crop(labels, 100, 100, (0, 0, 25, 25)), []
        )

    def test_near_duplicate_audit_extracts_only_train_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp) / "near.json"
            report.write_text(
                json.dumps(
                    {
                        "matches": [
                            {"left": "images/train/a.jpg", "right": "images/val/a.jpg"},
                            {"left": "images/val/b.jpg", "right": "images/test/b.jpg"},
                        ]
                    }
                )
            )
            self.assertEqual(leakage_train_relpaths(report), {"images/train/a.jpg"})


class GoalGuardTests(unittest.TestCase):
    def _metrics(self, overall: float, d02: float, d03: float) -> dict:
        return {
            "overall": {"mAP50-95": overall},
            "per_class": {
                "D02_surface_dent": {"mAP50-95": d02},
                "D03_carton_tear": {"mAP50-95": d03},
            },
        }

    def test_promotion_gate_passes_all_required_metrics(self) -> None:
        result = promotion_gate(self._metrics(0.100, 0.051, 0.110), 10.0)
        self.assertEqual(result["decision"], "PROMOTE")

    def test_strong_promotion_requires_0_110(self) -> None:
        result = promotion_gate(self._metrics(0.110, 0.051, 0.110), 10.0)
        self.assertEqual(result["decision"], "STRONG_PROMOTION")

    def test_promotion_rejects_d02_failure(self) -> None:
        result = promotion_gate(self._metrics(0.120, 0.049, 0.120), 10.0)
        self.assertEqual(result["decision"], "KEEP_CURRENT_ACTIVE")
        self.assertEqual(result["active_registry_action"], "PRESERVE_CURRENT")

    def test_promotion_rejects_latency_failure(self) -> None:
        result = promotion_gate(self._metrics(0.120, 0.060, 0.120), 20.0)
        self.assertEqual(result["decision"], "KEEP_CURRENT_ACTIVE")

    def test_single_access_lock_refuses_second_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            lock = Path(temp) / "lock.json"
            reserve_lock(lock, {"state": "RUNNING"})
            with self.assertRaises(FileExistsError):
                reserve_lock(lock, {"state": "RUNNING"})

    def test_config_rejects_test_access(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            config = {
                "experiment_id": "EXP-01",
                "hypothesis": "h",
                "main_change": "c",
                "dataset_yaml": "dataset.yaml",
                "model": "yolo26n.pt",
                "epochs": 100,
                "patience": 25,
                "seed": 42,
                "device": 0,
                "optimizer": "auto",
                "amp": True,
                "cache": False,
                "test_access_allowed": True,
            }
            path.write_text(json.dumps(config))
            with self.assertRaises(ValueError):
                load_config(path)

    def test_tracker_lists_full_budget(self) -> None:
        tracker = Path("docs/goals/detector-optimization-v2.0.md").read_text(
            encoding="utf-8"
        )
        for index in range(1, 7):
            self.assertIn(f"EXP-{index:02d}", tracker)


if __name__ == "__main__":
    unittest.main()
