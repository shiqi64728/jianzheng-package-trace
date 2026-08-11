from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.training import train_d02_d03_baseline as training  # noqa: E402


class D02D03TrainingConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        model_root = root / "models"
        self.config = {
            "experiment_id": "d02-d03-yolo26n-baseline-v0.1",
            "dataset_version": "detect-d02-d03-v0.1",
            "dataset_yaml": str(root / "training/dataset.yaml"),
            "dataset_lock": str(root / "training/dataset-lock.json"),
            "model": str(model_root / "pretrained/ultralytics/yolo26n.pt"),
            "model_metadata": str(
                model_root / "pretrained/ultralytics/yolo26n.metadata.json"
            ),
            "external_model_root": str(model_root),
            "task": "detect",
            "imgsz": 640,
            "epochs": 100,
            "patience": 25,
            "batch": -1,
            "device": 0,
            "workers": 4,
            "cache": False,
            "seed": 42,
            "deterministic": True,
            "optimizer": "auto",
            "pretrained": True,
            "amp": True,
            "project": str(root / "runs"),
            "name": "detect-d02-d03-yolo26n-v0.1",
            "save": True,
            "save_period": 10,
            "smoke": {
                "epochs": 3,
                "fraction": 0.25,
                "project": str(root / "runs"),
                "name": "smoke-d02-d03-yolo26n-v0.1",
            },
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_valid_experiment_config_is_parseable(self) -> None:
        self.assertEqual(
            training.validate_experiment_config(deepcopy(self.config))["epochs"], 100
        )

    def test_model_path_must_be_under_external_model_root(self) -> None:
        config = deepcopy(self.config)
        config["model"] = str(Path(self.temp.name) / "outside/yolo26n.pt")
        with self.assertRaisesRegex(training.TrainingPipelineError, "外部模型区"):
            training.validate_experiment_config(config)

    def test_only_yolo26n_is_allowed(self) -> None:
        config = deepcopy(self.config)
        config["model"] = str(
            Path(config["external_model_root"]) / "pretrained/ultralytics/yolo26s.pt"
        )
        with self.assertRaisesRegex(training.TrainingPipelineError, "yolo26n"):
            training.validate_experiment_config(config)

    def test_fixed_training_parameters_cannot_drift(self) -> None:
        config = deepcopy(self.config)
        config["epochs"] = 101
        with self.assertRaisesRegex(training.TrainingPipelineError, "固定值"):
            training.validate_experiment_config(config)

    def test_manual_recipe_tuning_keys_are_rejected(self) -> None:
        config = deepcopy(self.config)
        config["lr0"] = 0.2
        with self.assertRaisesRegex(training.TrainingPipelineError, "官方recipe"):
            training.validate_experiment_config(config)

    def test_config_file_round_trip(self) -> None:
        path = Path(self.temp.name) / "experiment.json"
        path.write_text(json.dumps(self.config), encoding="utf-8")
        self.assertEqual(training.load_experiment_config(path)["batch"], -1)

    def test_results_csv_preserves_one_based_epoch_number(self) -> None:
        path = Path(self.temp.name) / "results.csv"
        path.write_text(
            "epoch,metrics/mAP50-95(B),train/box_loss\n"
            "1,0.1,2.0\n"
            "2,0.3,1.5\n"
            "3,0.2,1.4\n",
            encoding="utf-8",
        )
        self.assertEqual(training._parse_results_csv(path)["best_epoch"], 2)


if __name__ == "__main__":
    unittest.main()
