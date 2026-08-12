from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from scripts.training.audit_near_duplicates_v11 import (
    audit_dataset,
    hamming,
    perceptual_hash,
)


class NearDuplicateAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for split in ("train", "val", "test"):
            (self.root / "images" / split).mkdir(parents=True)

    def tearDown(self):
        self.temp.cleanup()

    def write(self, split, name, image):
        path = self.root / "images" / split / name
        cv2.imwrite(str(path), image)
        return path

    @staticmethod
    def pattern(seed=0):
        rng = np.random.default_rng(seed)
        image = np.zeros((64, 64, 3), dtype=np.uint8)
        image[:] = rng.integers(0, 50, size=3)
        cv2.rectangle(image, (10, 12), (48, 45), (220, 80 + seed, 30), -1)
        cv2.line(image, (0, seed + 5), (63, 60 - seed), (255, 255, 255), 2)
        return image

    def test_same_image_has_same_hash(self):
        left = self.write("train", "a.png", self.pattern())
        right = self.write("val", "b.png", self.pattern())
        self.assertEqual(perceptual_hash(left), perceptual_hash(right))

    def test_hamming_is_symmetric(self):
        self.assertEqual(hamming(0b1010, 0b0011), hamming(0b0011, 0b1010))

    def test_hamming_counts_different_bits(self):
        self.assertEqual(hamming(0b1111, 0), 4)

    def test_exact_cross_split_is_reported(self):
        image = self.pattern()
        self.write("train", "a.png", image)
        self.write("val", "a.png", image)
        self.write("test", "z.png", self.pattern(7))
        report = audit_dataset(self.root, threshold=0)
        self.assertEqual(report["exact_cross_split_count"], 1)
        self.assertTrue(report["suspected_split_leakage"])

    def test_different_encoding_is_perceptual_match(self):
        image = self.pattern()
        self.write("train", "a.png", image)
        self.write("val", "a.jpg", image)
        self.write("test", "z.png", self.pattern(8))
        report = audit_dataset(self.root, threshold=6)
        self.assertGreaterEqual(report["perceptual_near_duplicate_count"], 1)

    def test_no_match_is_clean(self):
        self.write("train", "a.png", self.pattern(1))
        self.write("val", "b.png", self.pattern(20))
        self.write("test", "c.png", self.pattern(40))
        report = audit_dataset(self.root, threshold=0)
        self.assertEqual(report["exact_cross_split_count"], 0)

    def test_all_three_split_pairs_are_counted(self):
        for index, split in enumerate(("train", "val", "test")):
            self.write(split, f"{split}.png", self.pattern(index * 11))
        report = audit_dataset(self.root, threshold=0)
        self.assertEqual(
            set(report["cross_split_pair_counts"]),
            {"train_vs_val", "train_vs_test", "val_vs_test"},
        )

    def test_test_predictions_are_never_accessed(self):
        for index, split in enumerate(("train", "val", "test")):
            self.write(split, f"{split}.png", self.pattern(index * 13))
        self.assertFalse(audit_dataset(self.root)["test_predictions_accessed"])


if __name__ == "__main__":
    unittest.main()
