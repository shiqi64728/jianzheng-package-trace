from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.training.run_yolo26s_candidate_v11 import load_config


CONFIG = Path("configs/training/experiments/d02-d03-yolo26s-imgsz640-v1.1.json")


class Yolo26sCandidateConfigTests(unittest.TestCase):
    def test_committed_config_is_valid(self):
        self.assertEqual(load_config(CONFIG)["imgsz"], 640)

    def test_only_yolo26s_is_allowed(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        config["model"] = "E:/models/yolo26m.pt"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "only authorized"):
                load_config(path)

    def test_imgsz_cannot_drift(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        config["imgsz"] = 1280
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config.json"
            path.write_text(json.dumps(config), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "fixed parameter drift"):
                load_config(path)

    def test_seed_is_fixed(self):
        self.assertEqual(load_config(CONFIG)["seed"], 42)

    def test_smoke_is_exactly_three_epochs(self):
        self.assertEqual(load_config(CONFIG)["smoke"]["epochs"], 3)


if __name__ == "__main__":
    unittest.main()
