from __future__ import annotations

import csv
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts.dataset import build_external_manifests as builder  # noqa: E402
from scripts.dataset import build_external_review_worklist as worklist  # noqa: E402
from dataset.external_test_support import MAPPING, SCHEMA, create_external_fixture  # noqa: E402


class ExternalReviewWorklistTests(unittest.TestCase):
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
        self.output = self.paths["reports"] / "review-worklists"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def build(self, output: Path | None = None) -> dict:
        return worklist.build_worklists(
            self.paths["manifests"], output or self.output, "fixed-seed"
        )

    @staticmethod
    def read(path: Path) -> list[dict[str, str]]:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))

    def test_fixed_seed_is_reproducible(self) -> None:
        first = self.build()
        before = {path.name: path.read_bytes() for path in self.output.glob("*.csv")}
        second = self.build()
        after = {path.name: path.read_bytes() for path in self.output.glob("*.csv")}
        self.assertEqual(first, second)
        self.assertEqual(before, after)

    def test_input_order_does_not_change_sampling(self) -> None:
        source = self.paths["manifests"] / "damaged-box-detection-v0.1.csv"
        first = self.paths["reports"] / "review-a"
        second = self.paths["reports"] / "review-b"
        self.build(first)
        with source.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
        with source.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(reversed(rows))
        self.build(second)
        self.assertEqual(
            (first / "damaged-box-review-v0.1.csv").read_bytes(),
            (second / "damaged-box-review-v0.1.csv").read_bytes(),
        )

    def test_csv_uses_utf8_bom(self) -> None:
        self.build()
        self.assertTrue(
            all(
                path.read_bytes()[:3] == b"\xef\xbb\xbf"
                for path in self.output.glob("*.csv")
            )
        )

    def test_dirt_is_prioritized(self) -> None:
        self.build()
        rows = self.read(self.output / "defect-cardboard-review-v0.1.csv")
        self.assertTrue(any(row["review_focus"] == "dirt" for row in rows))
        self.assertTrue(any("受潮" in row["review_question"] for row in rows))

    def test_unresolved_pair_is_included(self) -> None:
        self.build()
        rows = self.read(self.output / "tampar-pair-review-v0.1.csv")
        self.assertTrue(any(row["pairing_confidence"] == "unresolved" for row in rows))

    def test_no_images_are_copied(self) -> None:
        summary = self.build()
        self.assertEqual(summary["copies_created"], 0)
        self.assertTrue(all(path.suffix == ".csv" for path in self.output.iterdir()))

    def test_no_absolute_paths_are_written(self) -> None:
        self.build()
        for path in self.output.glob("*.csv"):
            for row in self.read(path):
                image = row["original_image_relpath"]
                self.assertFalse(image.startswith(("/", "\\")))
                self.assertNotIn(":\\", image)

    def test_review_decisions_are_blank_and_duplicates_are_included(self) -> None:
        self.build()
        rows = self.read(self.output / "damaged-box-review-v0.1.csv")
        self.assertTrue(all(not row["review_decision"] for row in rows))
        self.assertTrue(any(row["review_focus"] == "duplicate_group" for row in rows))


if __name__ == "__main__":
    unittest.main()
