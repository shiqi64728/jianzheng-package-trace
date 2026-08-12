from __future__ import annotations

import json
import unittest
from pathlib import Path

from app.backend.main import create_app
from scripts.demo.measure_competition_rc_performance_v11 import percentile_nearest_rank


class RCV11HardeningTests(unittest.TestCase):
    def test_v11_config_is_isolated(self):
        config = json.loads(
            Path("configs/runtime/competition-rc-v1.1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(config["pipeline_version"], "competition-rc-v1.1")
        self.assertIn("competition-rc-v1.1", config["database_path"])

    def test_v11_keeps_active_registry(self):
        config = json.loads(
            Path("configs/runtime/competition-rc-v1.1.json").read_text(encoding="utf-8")
        )
        self.assertTrue(config["active_model_registry"].endswith("detector-v0.1.json"))

    def test_v11_keeps_change_v02_without_real_calibration(self):
        config = json.loads(
            Path("configs/runtime/competition-rc-v1.1.json").read_text(encoding="utf-8")
        )
        self.assertTrue(config["change_config"].endswith("change-detection-v0.2.json"))

    def test_real_world_status_is_pending(self):
        config = json.loads(
            Path("configs/runtime/competition-rc-v1.1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(
            config["real_world_calibration_status"], "PENDING_EXTERNAL_DATA"
        )

    def test_create_app_accepts_v11_config(self):
        app = create_app("configs/runtime/competition-rc-v1.1.json")
        self.assertEqual(
            app.state.service.config["pipeline_version"], "competition-rc-v1.1"
        )

    def test_p90_nearest_rank(self):
        self.assertEqual(percentile_nearest_rank(list(range(1, 11)), 0.9), 9)

    def test_p90_single_value(self):
        self.assertEqual(percentile_nearest_rank([7.5], 0.9), 7.5)

    def test_p90_empty_is_rejected(self):
        with self.assertRaises(ValueError):
            percentile_nearest_rank([], 0.9)


if __name__ == "__main__":
    unittest.main()
