from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from ai.runtime.fingerprint import (
    build_node_fingerprint_summary,
    build_surface_fingerprint,
)
from ai.runtime.sequence_locator import locate_multisurface_first_abnormality
from ai.runtime.surface_analyzer import SurfaceAnalyzer
from ai.runtime.surfaces import DEFAULT_SURFACES, SUPPORTED_SURFACES, normalize_surface


def capture(node: str, surface: str, known: bool = False) -> dict:
    return {
        "node_id": node,
        "surface": surface,
        "detections": [{"class_code": "D02"}] if known else [],
        "fingerprint": {"image_sha256": f"{node}-{surface}"},
    }


def pair(
    node_from: str,
    node_to: str,
    surface: str,
    *,
    significant: bool = False,
    registration: str = "SUCCESS",
    status: str = "AVAILABLE",
    score: float = 0.0,
) -> dict:
    return {
        "reference_node_id": node_from,
        "current_node_id": node_to,
        "surface": surface,
        "pair_status": status,
        "registration_status": registration,
        "is_significant": significant,
        "change_score": score,
    }


def complete_pairs(surfaces=("front",), overrides=None):
    overrides = overrides or {}
    rows = []
    for node_from, node_to in (("N1", "N2"), ("N2", "N3")):
        for surface in surfaces:
            rows.append(
                pair(
                    node_from,
                    node_to,
                    surface,
                    **overrides.get((node_from, node_to, surface), {}),
                )
            )
    return rows


class SurfaceVocabularyTests(unittest.TestCase):
    def test_supported_surface_vocabulary(self):
        self.assertEqual(
            SUPPORTED_SURFACES,
            ("front", "left", "right", "top", "back", "bottom", "unknown"),
        )

    def test_default_ui_surfaces(self):
        self.assertEqual(DEFAULT_SURFACES, ("front", "left", "right", "top"))

    def test_legacy_surface_defaults_to_front(self):
        self.assertEqual(normalize_surface("PACKAGE_EXTERIOR"), "front")
        self.assertEqual(normalize_surface(None), "front")

    def test_surface_is_case_normalized(self):
        self.assertEqual(normalize_surface(" Left "), "left")

    def test_unknown_surface_is_rejected(self):
        with self.assertRaises(ValueError):
            normalize_surface("inside")


class SurfaceFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.image = np.zeros((100, 140, 3), dtype=np.uint8)
        cv2.putText(
            self.image, "BOX", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2
        )

    def test_surface_fingerprint_has_required_fields(self):
        result = build_surface_fingerprint(self.image, [], "left")
        for key in (
            "image_sha256",
            "width",
            "height",
            "orb_keypoint_count",
            "descriptor_digest",
            "known_damage_summary",
        ):
            self.assertIn(key, result)
        self.assertEqual(result["surface"], "left")

    def test_node_summary_aggregates_without_merging_hashes(self):
        results = [capture("N1", "front"), capture("N1", "left", True)]
        summary = build_node_fingerprint_summary("N1", results, ["front"])
        self.assertEqual(summary["available_surfaces"], ["front", "left"])
        self.assertEqual(summary["surface_hashes"]["left"], "N1-left")
        self.assertEqual(summary["total_known_damage_count"], 1)
        self.assertEqual(summary["surfaces_with_damage"], ["left"])
        self.assertEqual(summary["surfaces_with_unknown_change"], ["front"])

    def test_missing_pair_factory_is_non_abnormal(self):
        result = SurfaceAnalyzer.missing_pair("N1", "N2", "top")
        self.assertEqual(result["pair_status"], "PAIR_SURFACE_MISSING")
        self.assertFalse(result["is_significant"])
        self.assertEqual(result["registration_status"], "NOT_RUN")

    def test_cross_surface_pair_is_forbidden(self):
        analyzer = object.__new__(SurfaceAnalyzer)
        with self.assertRaises(ValueError):
            analyzer.analyze_pair(
                capture("N1", "front"),
                capture("N2", "left"),
                self.image,
                self.image,
                Path(tempfile.gettempdir()),
            )


class MultiSurfaceSequenceTests(unittest.TestCase):
    def nodes(self, surfaces=("front",), known=None):
        known = known or set()
        return [
            capture(node, surface, (node, surface) in known)
            for node in ("N1", "N2", "N3")
            for surface in surfaces
        ]

    def test_requires_three_nodes(self):
        with self.assertRaises(ValueError):
            locate_multisurface_first_abnormality(
                [capture("N1", "front"), capture("N2", "front")],
                [pair("N1", "N2", "front")],
            )

    def test_rejects_gapped_nodes(self):
        with self.assertRaises(ValueError):
            locate_multisurface_first_abnormality(
                [
                    capture("N1", "front"),
                    capture("N3", "front"),
                    capture("N4", "front"),
                ],
                [],
            )

    def test_requires_explicit_same_surface_pair(self):
        with self.assertRaises(ValueError):
            locate_multisurface_first_abnormality(self.nodes(), [])

    def test_all_surfaces_normal(self):
        result = locate_multisurface_first_abnormality(
            self.nodes(("front", "left")), complete_pairs(("front", "left"))
        )
        self.assertEqual(result["conclusion_code"], "NO_ABNORMALITY_OBSERVED")
        self.assertEqual(result["evidence_level"], "E0")

    def test_one_unknown_surface_triggers_interval(self):
        pairs = complete_pairs(
            ("front", "left"),
            {("N1", "N2", "left"): {"significant": True, "score": 0.042}},
        )
        result = locate_multisurface_first_abnormality(
            self.nodes(("front", "left")), pairs
        )
        self.assertEqual(result["first_abnormal_interval"], "N1_TO_N2")
        self.assertEqual(result["evidence_level"], "E3")
        self.assertEqual(result["trigger_surfaces"][0]["surface"], "left")
        self.assertEqual(
            result["trigger_surfaces"][0]["reason"], "UNKNOWN_VISUAL_CHANGE"
        )

    def test_known_damage_and_change_is_e1(self):
        nodes = self.nodes(("front",), {("N2", "front")})
        pairs = complete_pairs(
            ("front",),
            {("N1", "N2", "front"): {"significant": True, "score": 0.5}},
        )
        result = locate_multisurface_first_abnormality(nodes, pairs)
        self.assertEqual(result["evidence_level"], "E1")

    def test_known_damage_only_is_e2(self):
        result = locate_multisurface_first_abnormality(
            self.nodes(("front",), {("N2", "front")}), complete_pairs()
        )
        self.assertEqual(result["evidence_level"], "E2")

    def test_n1_known_damage_is_first_observed(self):
        result = locate_multisurface_first_abnormality(
            self.nodes(("front",), {("N1", "front")}), complete_pairs()
        )
        self.assertEqual(result["conclusion_code"], "FIRST_OBSERVED_ABNORMAL_AT_N1")
        self.assertIsNone(result["first_abnormal_interval"])

    def test_missing_surface_does_not_trigger_abnormality(self):
        nodes = [
            capture("N1", "front"),
            capture("N1", "left"),
            capture("N2", "front"),
            capture("N3", "front"),
            capture("N3", "left"),
        ]
        pairs = complete_pairs(("front", "left"))
        for item in pairs:
            if item["surface"] == "left":
                item.update(
                    SurfaceAnalyzer.missing_pair(
                        item["reference_node_id"], item["current_node_id"], "left"
                    )
                )
        result = locate_multisurface_first_abnormality(nodes, pairs)
        self.assertEqual(result["conclusion_code"], "NO_ABNORMALITY_OBSERVED")
        self.assertEqual(
            result["evidence_completeness"]["missing_pair_surface_count"], 2
        )

    def test_only_failed_and_missing_requires_review(self):
        nodes = self.nodes(("front", "left"))
        pairs = complete_pairs(
            ("front", "left"),
            {
                ("N1", "N2", "front"): {"registration": "FAILED"},
                ("N1", "N2", "left"): {
                    "status": "PAIR_SURFACE_MISSING",
                    "registration": "NOT_RUN",
                },
                ("N2", "N3", "front"): {"registration": "FAILED"},
                ("N2", "N3", "left"): {
                    "status": "PAIR_SURFACE_MISSING",
                    "registration": "NOT_RUN",
                },
            },
        )
        result = locate_multisurface_first_abnormality(nodes, pairs)
        self.assertEqual(result["conclusion_code"], "MANUAL_REVIEW_REQUIRED")
        self.assertEqual(result["evidence_level"], "E0")

    def test_failed_surface_with_other_normal_surface_is_not_abnormal(self):
        pairs = complete_pairs(
            ("front", "left"),
            {("N1", "N2", "left"): {"registration": "FAILED", "significant": True}},
        )
        result = locate_multisurface_first_abnormality(
            self.nodes(("front", "left")), pairs
        )
        self.assertEqual(result["conclusion_code"], "NO_ABNORMALITY_OBSERVED")

    def test_multiple_trigger_surfaces_are_preserved(self):
        pairs = complete_pairs(
            ("front", "left"),
            {
                ("N1", "N2", "front"): {"significant": True, "score": 0.1},
                ("N1", "N2", "left"): {"significant": True, "score": 0.2},
            },
        )
        result = locate_multisurface_first_abnormality(
            self.nodes(("front", "left")), pairs
        )
        self.assertEqual(
            [x["surface"] for x in result["trigger_surfaces"]], ["front", "left"]
        )

    def test_second_interval_can_be_first_abnormal(self):
        pairs = complete_pairs(
            ("front",),
            {("N2", "N3", "front"): {"significant": True, "score": 0.2}},
        )
        result = locate_multisurface_first_abnormality(self.nodes(), pairs)
        self.assertEqual(result["first_abnormal_interval"], "N2_TO_N3")


if __name__ == "__main__":
    unittest.main()
