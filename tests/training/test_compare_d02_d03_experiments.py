from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.training.compare_d02_d03_experiments import (  # noqa: E402
    ExperimentComparisonError,
    _comparison_rows,
    audit_experiment_configs,
    ensure_validation_only,
    metric_change,
    validate_candidate_path,
    verify_hash_contract,
)
from scripts.training.evaluate_d02_d03_baseline import _stable_sample  # noqa: E402
from scripts.training.train_d02_d03_baseline import (  # noqa: E402
    load_experiment_config,
)


BASELINE_CONFIG = (
    REPO_ROOT
    / "configs"
    / "training"
    / "experiments"
    / "d02-d03-yolo26n-baseline-v0.1.json"
)
CANDIDATE_CONFIG = (
    REPO_ROOT
    / "configs"
    / "training"
    / "experiments"
    / "d02-d03-yolo26n-imgsz960-v0.1.json"
)


class ExperimentComparisonTests(unittest.TestCase):
    def _configs(self) -> tuple[dict, dict]:
        return (
            json.loads(BASELINE_CONFIG.read_text(encoding="utf-8")),
            json.loads(CANDIDATE_CONFIG.read_text(encoding="utf-8")),
        )

    def test_expected_config_diff_is_valid(self) -> None:
        baseline, candidate = self._configs()
        result = audit_experiment_configs(baseline, candidate)
        self.assertTrue(result["valid"])
        self.assertEqual(result["active_change"], {"baseline": 640, "candidate": 960})

    def test_non_imgsz_hyperparameter_change_fails(self) -> None:
        baseline, candidate = self._configs()
        candidate["optimizer"] = "SGD"
        with self.assertRaises(ExperimentComparisonError):
            audit_experiment_configs(baseline, candidate)

    def test_seed_change_fails(self) -> None:
        baseline, candidate = self._configs()
        candidate["seed"] = 43
        with self.assertRaises(ExperimentComparisonError):
            audit_experiment_configs(baseline, candidate)

    def test_dataset_lock_hash_change_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = [root / name for name in ("lock", "weight", "best")]
            for path in paths:
                path.write_bytes(path.name.encode())
            digests = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
            paths[0].write_bytes(b"changed")
            with self.assertRaises(ExperimentComparisonError):
                verify_hash_contract(*paths, *digests)

    def test_pretrained_hash_change_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = [root / name for name in ("lock", "weight", "best")]
            for path in paths:
                path.write_bytes(path.name.encode())
            digests = [hashlib.sha256(path.read_bytes()).hexdigest() for path in paths]
            paths[1].write_bytes(b"changed")
            with self.assertRaises(ExperimentComparisonError):
                verify_hash_contract(*paths, *digests)

    def test_candidate_cannot_use_release_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            models = Path(temporary) / "models"
            with self.assertRaises(ExperimentComparisonError):
                validate_candidate_path(models / "releases" / "candidate", models)

    def test_candidate_experiment_path_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            models = Path(temporary) / "models"
            validate_candidate_path(models / "experiments" / "candidate", models)

    def test_absolute_metric_change_is_correct(self) -> None:
        self.assertAlmostEqual(metric_change(0.2, 0.25)["absolute_change"], 0.05)

    def test_relative_metric_change_is_correct(self) -> None:
        self.assertAlmostEqual(
            metric_change(0.2, 0.25)["relative_change_percent"], 25.0
        )

    def test_per_class_metrics_remain_associated(self) -> None:
        def metrics(d02: float, d03: float) -> dict:
            return {
                "overall": {
                    key: 0.5 for key in ("precision", "recall", "mAP50", "mAP50-95")
                },
                "per_class": {
                    "D02_surface_dent": {
                        key: d02 for key in ("precision", "recall", "mAP50", "mAP50-95")
                    },
                    "D03_carton_tear": {
                        key: d03 for key in ("precision", "recall", "mAP50", "mAP50-95")
                    },
                },
                "speed": {"inference_ms_per_image": 1.0},
            }

        training = {
            "actual_batch": 8,
            "best_epoch": 1,
            "duration_seconds": 10.0,
            "average_epoch_seconds": 1.0,
            "peak_gpu_memory_bytes": 100,
            "best_pt_size_bytes": 10,
        }
        rows = _comparison_rows(
            metrics(0.1, 0.2), metrics(0.3, 0.4), training, training
        )
        indexed = {row["metric"]: row for row in rows}
        self.assertEqual(indexed["D02_surface_dent.precision"]["baseline"], 0.1)
        self.assertEqual(indexed["D03_carton_tear.precision"]["candidate"], 0.4)

    def test_candidate_test_payload_is_rejected(self) -> None:
        with self.assertRaises(ExperimentComparisonError):
            ensure_validation_only({"split": "test", "mAP50": 0.9})
        with self.assertRaises(ExperimentComparisonError):
            ensure_validation_only({"test": {"mAP50": 0.9}})

    def test_qualitative_sample_list_is_shared_and_deterministic(self) -> None:
        rows = [
            {"external_record_id": str(index), "target_image_relpath": f"{index}.jpg"}
            for index in range(40)
        ]
        baseline = _stable_sample(rows, 20, 42)
        candidate = _stable_sample(list(reversed(rows)), 20, 42)
        self.assertEqual(baseline, candidate)

    def test_original_640_training_config_still_parses(self) -> None:
        self.assertEqual(load_experiment_config(BASELINE_CONFIG)["imgsz"], 640)

    def test_960_training_config_parses(self) -> None:
        self.assertEqual(load_experiment_config(CANDIDATE_CONFIG)["imgsz"], 960)


if __name__ == "__main__":
    unittest.main()
