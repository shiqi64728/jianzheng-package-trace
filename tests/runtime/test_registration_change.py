from __future__ import annotations

import unittest

import cv2
import numpy as np

from ai.runtime.change_detector import ChangeDetector, serializable_change
from ai.runtime.registration import ImageRegistrar, serializable_registration


def config():
    return {
        "orb_nfeatures": 1800,
        "orb_scale_factor": 1.2,
        "orb_nlevels": 8,
        "match_ratio": 0.8,
        "ransac_reprojection_threshold": 5.0,
        "minimum_good_matches": 8,
        "minimum_inlier_ratio": 0.15,
        "success_inlier_ratio": 0.35,
        "minimum_overlap_ratio": 0.35,
        "blur_kernel": 5,
        "pixel_difference_threshold": 30,
        "morphology_kernel": 3,
        "morphology_iterations": 1,
        "minimum_region_area": 80,
        "significant_change_ratio": 0.004,
        "known_damage_overlap_ratio": 0.1,
    }


def textured(seed=7):
    rng = np.random.default_rng(seed)
    image = np.full((420, 560, 3), 205, dtype=np.uint8)
    for index in range(100):
        point = tuple(int(value) for value in rng.integers([10, 10], [550, 410]))
        cv2.circle(image, point, int(rng.integers(2, 8)), (30 + index, 70, 130), -1)
    cv2.putText(
        image, "BOX-N1-TRACE", (80, 220), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (20, 20, 20), 3
    )
    return image


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.registrar = ImageRegistrar(config())
        self.base = textured()

    def test_identity_registration_succeeds(self):
        result = self.registrar.register(self.base, self.base.copy())
        self.assertEqual(result["registration_status"], "SUCCESS")
        self.assertGreater(result["inlier_ratio"], 0.9)

    def test_translation_registration(self):
        matrix = np.float32([[1, 0, 12], [0, 1, 8]])
        moved = cv2.warpAffine(
            self.base, matrix, (560, 420), borderValue=(205, 205, 205)
        )
        result = self.registrar.register(self.base, moved)
        self.assertIn(result["registration_status"], {"SUCCESS", "LOW_CONFIDENCE"})

    def test_rotation_registration(self):
        matrix = cv2.getRotationMatrix2D((280, 210), 3.5, 1.0)
        rotated = cv2.warpAffine(
            self.base, matrix, (560, 420), borderValue=(205, 205, 205)
        )
        result = self.registrar.register(self.base, rotated)
        self.assertNotEqual(result["registration_status"], "FAILED")

    def test_perspective_registration(self):
        source = np.float32([[0, 0], [559, 0], [559, 419], [0, 419]])
        target = np.float32([[8, 5], [550, 12], [555, 411], [3, 415]])
        matrix = cv2.getPerspectiveTransform(source, target)
        warped = cv2.warpPerspective(
            self.base, matrix, (560, 420), borderValue=(205, 205, 205)
        )
        result = self.registrar.register(self.base, warped)
        self.assertIsNotNone(result["homography"])

    def test_too_few_features_fails_with_fallback(self):
        blank = np.full((300, 400, 3), 128, dtype=np.uint8)
        result = self.registrar.register(blank, blank)
        self.assertEqual(result["registration_status"], "FAILED")
        self.assertTrue(result["fallback_visual_change"])

    def test_failed_registration_never_claims_homography(self):
        blank = np.zeros((200, 200, 3), dtype=np.uint8)
        result = self.registrar.register(blank, blank)
        self.assertIsNone(result["homography"])

    def test_serializable_registration_drops_arrays(self):
        result = serializable_registration(
            self.registrar.register(self.base, self.base)
        )
        self.assertNotIn("registered_image", result)
        self.assertNotIn("overlap_mask", result)


class ChangeDetectorTests(unittest.TestCase):
    def setUp(self):
        self.detector = ChangeDetector(ImageRegistrar(config()))
        self.base = textured()

    def test_no_change_is_low(self):
        result = self.detector.detect(self.base, self.base.copy())
        self.assertLess(result["changed_pixel_ratio"], 0.001)
        self.assertFalse(result["is_significant"])

    def test_small_change_region_is_detected(self):
        changed = self.base.copy()
        cv2.rectangle(changed, (300, 250), (360, 300), (0, 0, 0), -1)
        result = self.detector.detect(self.base, changed)
        self.assertGreaterEqual(result["changed_region_count"], 1)
        self.assertTrue(result["is_significant"])

    def test_large_change_scores_higher_than_small_change(self):
        small, large = self.base.copy(), self.base.copy()
        cv2.rectangle(small, (300, 250), (340, 290), (0, 0, 0), -1)
        cv2.rectangle(large, (240, 180), (440, 360), (0, 0, 0), -1)
        self.assertGreater(
            self.detector.detect(self.base, large)["changed_pixel_ratio"],
            self.detector.detect(self.base, small)["changed_pixel_ratio"],
        )

    def test_unknown_change_label_is_default(self):
        changed = self.base.copy()
        cv2.rectangle(changed, (300, 250), (380, 330), (0, 0, 0), -1)
        result = self.detector.detect(self.base, changed)
        self.assertEqual(result["regions"][0]["change_type"], "UNKNOWN_VISUAL_CHANGE")

    def test_known_overlap_uses_only_d02_or_d03(self):
        changed = self.base.copy()
        cv2.rectangle(changed, (300, 250), (380, 330), (0, 0, 0), -1)
        known = [{"class_code": "D02", "bbox_xyxy": [295, 245, 385, 335]}]
        result = self.detector.detect(self.base, changed, known_detections=known)
        self.assertEqual(result["regions"][0]["change_type"], "D02")

    def test_registration_failure_is_disclosed(self):
        blank = np.zeros((300, 400, 3), dtype=np.uint8)
        changed = blank.copy()
        cv2.rectangle(changed, (50, 50), (200, 200), (255, 255, 255), -1)
        result = self.detector.detect(blank, changed)
        self.assertEqual(result["registration_status"], "FAILED")
        self.assertLessEqual(result["registration_confidence"], 0.2)

    def test_serializable_change_drops_visual_arrays(self):
        result = serializable_change(self.detector.detect(self.base, self.base))
        self.assertNotIn("visualization", result)
        self.assertNotIn("change_mask", result)
