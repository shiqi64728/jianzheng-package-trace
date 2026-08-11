from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.runtime.build_change_calibration_suite import build_suite
from scripts.runtime.calibrate_change_thresholds import calibrate, write_outputs


class CalibrationToolTests(unittest.TestCase):
    def test_builds_ten_named_scenarios(self):
        with tempfile.TemporaryDirectory() as temp:
            result = build_suite(temp)
            self.assertEqual(result["scenario_count"], 10)
            self.assertEqual(result["scenarios"][0]["scenario_id"], "NORMAL-01")
            self.assertEqual(result["scenarios"][-1]["scenario_id"], "FAILURE-02")

    def test_same_seed_has_same_image_hashes(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            left, right = build_suite(a, 77), build_suite(b, 77)
            left_hashes = [
                (x["reference_sha256"], x["current_sha256"]) for x in left["scenarios"]
            ]
            right_hashes = [
                (x["reference_sha256"], x["current_sha256"]) for x in right["scenarios"]
            ]
            self.assertEqual(left_hashes, right_hashes)

    def test_calibration_keeps_normals_without_false_alarm(self):
        with tempfile.TemporaryDirectory() as temp:
            build_suite(temp)
            result = calibrate(temp)
            self.assertEqual(result["selected_result"]["normal_false_alarm_count"], 0)

    def test_calibration_observes_all_synthetic_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            build_suite(temp)
            result = calibrate(temp)
            self.assertEqual(result["selected_result"]["change_missed_count"], 0)

    def test_calibration_writes_json_and_markdown(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            build_suite(root)
            result = calibrate(root)
            output_json, output_md = root / "result.json", root / "result.md"
            write_outputs(result, output_json, output_md)
            self.assertEqual(json.loads(output_json.read_text())["scenario_count"], 10)
            self.assertIn("SYNTHETIC_ENGINEERING_CALIBRATION", output_md.read_text())

    def test_calibration_module_does_not_import_detector(self):
        source = Path("scripts/runtime/calibrate_change_thresholds.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("ai.runtime.detector", source)
        self.assertNotIn("/test", source.replace("\\", "/").lower())

    def test_v02_config_records_synthetic_source(self):
        config = json.loads(
            Path("configs/runtime/change-detection-v0.2.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(config["calibration_source"], "synthetic_engineering")
        self.assertEqual(config["significant_change_ratio"], 0.004)


if __name__ == "__main__":
    unittest.main()
