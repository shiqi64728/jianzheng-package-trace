from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.training.analyze_d02_d03_object_sizes import (  # noqa: E402
    ObjectSizeAnalysisError,
    assign_quartile,
    build_distribution,
    collect_bbox_records,
    projected_dimensions,
    quartile_thresholds,
    write_analysis,
)


class ObjectSizeAnalysisTests(unittest.TestCase):
    def _dataset(self, root: Path) -> Path:
        dataset = root / "dataset"
        (dataset / "labels" / "train").mkdir(parents=True)
        (dataset / "labels" / "val").mkdir(parents=True)
        rows = [
            {
                "external_record_id": "a",
                "target_image_relpath": "images/train/a.jpg",
                "target_label_relpath": "labels/train/a.txt",
                "split": "train",
                "width": "800",
                "height": "400",
            },
            {
                "external_record_id": "b",
                "target_image_relpath": "images/val/b.jpg",
                "target_label_relpath": "labels/val/b.txt",
                "split": "val",
                "width": "640",
                "height": "640",
            },
        ]
        with (dataset / "dataset-manifest.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        (dataset / "labels" / "train" / "a.txt").write_text(
            "0 0.5 0.5 0.10 0.20\n1 0.5 0.5 0.20 0.20\n",
            encoding="utf-8",
        )
        (dataset / "labels" / "val" / "b.txt").write_text(
            "0 0.5 0.5 0.05 0.05\n1 0.5 0.5 0.40 0.40\n",
            encoding="utf-8",
        )
        return dataset

    def test_quartile_calculation_is_reproducible(self) -> None:
        values = [0.08, 0.01, 0.07, 0.02, 0.06, 0.03, 0.05, 0.04]
        self.assertEqual(quartile_thresholds(values), quartile_thresholds(values))

    def test_input_order_does_not_change_quartiles(self) -> None:
        values = [0.08, 0.01, 0.07, 0.02, 0.06, 0.03, 0.05, 0.04]
        self.assertEqual(
            quartile_thresholds(values), quartile_thresholds(reversed(values))
        )

    def test_d02_and_d03_are_counted_separately(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            records = collect_bbox_records(self._dataset(Path(temporary)))
            distribution = build_distribution(records)
        self.assertEqual(distribution["classes"]["D02_surface_dent"]["bbox_count"], 2)
        self.assertEqual(distribution["classes"]["D03_carton_tear"]["bbox_count"], 2)

    def test_640_and_960_projection_is_correct(self) -> None:
        width_640, height_640, area_640 = projected_dimensions(0.1, 0.2, 800, 400, 640)
        width_960, height_960, area_960 = projected_dimensions(0.1, 0.2, 800, 400, 960)
        self.assertAlmostEqual(width_640, 64.0)
        self.assertAlmostEqual(height_640, 64.0)
        self.assertAlmostEqual(area_640, 4096.0)
        self.assertAlmostEqual(width_960, 96.0)
        self.assertAlmostEqual(height_960, 96.0)
        self.assertAlmostEqual(area_960, 9216.0)

    def test_quartile_assignment_uses_distribution_thresholds(self) -> None:
        thresholds = {"q25": 0.1, "q50": 0.2, "q75": 0.3}
        self.assertEqual(assign_quartile(0.1, thresholds), "smallest_quartile")
        self.assertEqual(assign_quartile(0.2, thresholds), "q2")
        self.assertEqual(assign_quartile(0.3, thresholds), "q3")
        self.assertEqual(assign_quartile(0.4, thresholds), "largest_quartile")

    def test_analysis_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = self._dataset(root)
            output = root / "output"
            write_analysis(dataset, output)
            with self.assertRaises(ObjectSizeAnalysisError):
                write_analysis(dataset, output)


if __name__ == "__main__":
    unittest.main()
