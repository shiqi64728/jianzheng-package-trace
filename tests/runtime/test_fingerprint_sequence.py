from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from ai.runtime.fingerprint import FINGERPRINT_LIMITATION, build_appearance_fingerprint
from ai.runtime.sequence_locator import locate_first_abnormality


def node(node_id, damaged=False):
    detections = []
    if damaged:
        detections = [{"class_code": "D03", "confidence": 0.8}]
    return {"node_id": node_id, "detections": detections}


def pair(reference, current, changed=False, status="SUCCESS"):
    return {
        "reference_node_id": reference,
        "current_node_id": current,
        "is_significant": changed,
        "registration_status": status,
    }


class FingerprintTests(unittest.TestCase):
    def setUp(self):
        self.image = np.zeros((180, 240, 3), dtype=np.uint8)
        cv2.putText(
            self.image,
            "TRACE",
            (30, 100),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.4,
            (255, 255, 255),
            3,
        )

    def test_same_array_has_same_image_sha(self):
        first = build_appearance_fingerprint(self.image)
        second = build_appearance_fingerprint(self.image.copy())
        self.assertEqual(first["image_sha256"], second["image_sha256"])

    def test_file_sha_uses_original_bytes(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "image.png"
            cv2.imwrite(str(path), self.image)
            self.assertEqual(
                build_appearance_fingerprint(path)["image_sha256"],
                __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
            )

    def test_descriptor_digest_is_deterministic(self):
        first = build_appearance_fingerprint(self.image)
        second = build_appearance_fingerprint(self.image)
        self.assertEqual(first["descriptor_digest"], second["descriptor_digest"])

    def test_known_damage_summary_counts_d02_d03(self):
        detections = [
            {"class_code": "D02", "confidence": 0.4},
            {"class_code": "D02", "confidence": 0.8},
            {"class_code": "D03", "confidence": 0.7},
        ]
        summary = build_appearance_fingerprint(self.image, detections)[
            "known_damage_summary"
        ]
        self.assertEqual(summary["counts"], {"D02": 2, "D03": 1})
        self.assertEqual(summary["max_confidence"]["D02"], 0.8)

    def test_dimensions_and_keypoints_are_present(self):
        result = build_appearance_fingerprint(self.image)
        self.assertEqual((result["width"], result["height"]), (240, 180))
        self.assertGreaterEqual(result["orb_keypoint_count"], 0)

    def test_limitation_is_explicit(self):
        self.assertEqual(
            build_appearance_fingerprint(self.image)["limitation"],
            FINGERPRINT_LIMITATION,
        )


class SequenceLocatorTests(unittest.TestCase):
    def test_n1_abnormal(self):
        result = locate_first_abnormality(
            [node("N1", True), node("N2"), node("N3")],
            [pair("N1", "N2"), pair("N2", "N3")],
        )
        self.assertEqual(result["conclusion_code"], "FIRST_OBSERVED_ABNORMAL_AT_N1")
        self.assertEqual(result["evidence_level"], "E2")

    def test_n1_to_n2_known_and_changed_is_e1(self):
        result = locate_first_abnormality(
            [node("N1"), node("N2", True), node("N3", True)],
            [pair("N1", "N2", True), pair("N2", "N3")],
        )
        self.assertEqual(result["first_abnormal_interval"], "N1_TO_N2")
        self.assertEqual(result["evidence_level"], "E1")

    def test_n2_to_n3_known_only(self):
        result = locate_first_abnormality(
            [node("N1"), node("N2"), node("N3", True)],
            [pair("N1", "N2"), pair("N2", "N3")],
        )
        self.assertEqual(result["first_abnormal_interval"], "N2_TO_N3")
        self.assertEqual(result["evidence_level"], "E2")

    def test_all_normal(self):
        result = locate_first_abnormality(
            [node("N1"), node("N2"), node("N3")],
            [pair("N1", "N2"), pair("N2", "N3")],
        )
        self.assertEqual(result["conclusion_code"], "NO_ABNORMALITY_OBSERVED")

    def test_unknown_change_only(self):
        result = locate_first_abnormality(
            [node("N1"), node("N2"), node("N3")],
            [pair("N1", "N2", True), pair("N2", "N3")],
        )
        self.assertEqual(result["conclusion_code"], "UNKNOWN_VISUAL_CHANGE_INTERVAL")
        self.assertEqual(result["evidence_level"], "E3")

    def test_registration_failure_requires_manual_review(self):
        result = locate_first_abnormality(
            [node("N1"), node("N2"), node("N3")],
            [pair("N1", "N2", status="FAILED"), pair("N2", "N3")],
        )
        self.assertEqual(result["conclusion_code"], "MANUAL_REVIEW_REQUIRED")
        self.assertEqual(result["evidence_level"], "E0")

    def test_known_and_changed_node_state(self):
        result = locate_first_abnormality(
            [node("N1"), node("N2", True), node("N3")],
            [pair("N1", "N2", True), pair("N2", "N3")],
        )
        self.assertEqual(result["node_states"][1]["status"], "KNOWN_DAMAGE_AND_CHANGE")

    def test_unknown_change_node_state(self):
        result = locate_first_abnormality(
            [node("N1"), node("N2"), node("N3")],
            [pair("N1", "N2", True), pair("N2", "N3")],
        )
        self.assertEqual(result["node_states"][1]["status"], "UNKNOWN_CHANGE")

    def test_requires_three_nodes(self):
        with self.assertRaises(ValueError):
            locate_first_abnormality([node("N1"), node("N2")], [pair("N1", "N2")])

    def test_requires_all_adjacent_pairs(self):
        with self.assertRaises(ValueError):
            locate_first_abnormality(
                [node("N1"), node("N2"), node("N3")], [pair("N1", "N2")]
            )
