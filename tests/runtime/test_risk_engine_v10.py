from __future__ import annotations

import copy
import unittest

from ai.runtime.risk_engine import RISK_ENGINE_VERSION, RiskEngine, assess_risk


def strong_analysis():
    return {
        "conclusion_code": "FIRST_ABNORMAL_INTERVAL",
        "first_abnormal_interval": "N1_TO_N2",
        "trigger_surfaces": [
            {"surface": "front", "reason": "KNOWN_DAMAGE_AND_CHANGE"},
            {"surface": "left", "reason": "KNOWN_DAMAGE"},
        ],
        "evidence_completeness": {
            "available_capture_count": 12,
            "expected_matrix_cells": 12,
        },
        "node_states": [
            {"node_id": "N2", "status": "KNOWN_DAMAGE_AND_CHANGE"},
            {"node_id": "N3", "status": "KNOWN_DAMAGE"},
        ],
    }


def pairs(status="OK"):
    return [
        {
            "reference_node_id": "N1",
            "current_node_id": "N2",
            "surface": surface,
            "pair_status": "AVAILABLE",
            "registration_status": status,
        }
        for surface in ("front", "left")
    ]


def confirmed():
    return [
        {
            "node_from": "N1",
            "node_to": "N2",
            "surface": "front",
            "review_class": "D02",
            "review_status": "CONFIRMED",
        }
    ]


class RiskEngineTests(unittest.TestCase):
    def test_version_is_explicit(self):
        self.assertEqual(RISK_ENGINE_VERSION, "responsibility-risk-rules-v1.0")

    def test_deterministic_for_identical_input(self):
        one = assess_risk(strong_analysis(), pairs(), [{}] * 12, confirmed())
        two = assess_risk(
            copy.deepcopy(strong_analysis()),
            copy.deepcopy(pairs()),
            [{}] * 12,
            copy.deepcopy(confirmed()),
        )
        self.assertEqual(one, two)

    def test_score_is_component_sum(self):
        result = assess_risk(strong_analysis(), pairs(), [{}] * 12, confirmed())
        self.assertEqual(
            result["risk_score"], sum(x["points"] for x in result["score_breakdown"])
        )

    def test_score_stays_in_range(self):
        result = assess_risk(strong_analysis(), pairs(), [{}] * 12, confirmed())
        self.assertGreaterEqual(result["risk_score"], 0)
        self.assertLessEqual(result["risk_score"], 100)

    def test_strong_consistent_evidence_is_high(self):
        self.assertEqual(
            assess_risk(strong_analysis(), pairs(), [{}] * 12, confirmed())[
                "risk_level"
            ],
            "HIGH",
        )

    def test_failed_registration_never_high(self):
        result = assess_risk(strong_analysis(), pairs("FAILED"), [{}] * 12, confirmed())
        self.assertNotEqual(result["risk_level"], "HIGH")
        self.assertLessEqual(result["risk_score"], 59)

    def test_failed_registration_is_conflicting_evidence(self):
        result = assess_risk(strong_analysis(), pairs("FAILED"), [{}] * 12, confirmed())
        self.assertIn(
            "REGISTRATION_FAILED", {x["type"] for x in result["conflicting_evidence"]}
        )

    def test_missing_matrix_lowers_score(self):
        incomplete = strong_analysis()
        incomplete["evidence_completeness"]["available_capture_count"] = 3
        full = assess_risk(strong_analysis(), pairs(), [{}] * 12, confirmed())
        partial = assess_risk(incomplete, pairs(), [{}] * 3, confirmed())
        self.assertLess(partial["risk_score"], full["risk_score"])

    def test_missing_matrix_is_explicit(self):
        analysis = strong_analysis()
        analysis["evidence_completeness"]["available_capture_count"] = 4
        result = assess_risk(analysis, pairs(), [{}] * 4, confirmed())
        self.assertIn("CAPTURE_MATRIX", {x["type"] for x in result["missing_evidence"]})

    def test_single_surface_has_lower_consistency(self):
        one = strong_analysis()
        one["trigger_surfaces"] = one["trigger_surfaces"][:1]
        result = assess_risk(one, pairs(), [{}] * 12, confirmed())
        component = next(
            x
            for x in result["score_breakdown"]
            if x["component"] == "multi_surface_consistency"
        )
        self.assertEqual(component["points"], 3)

    def test_unknown_change_contributes_separate_component(self):
        analysis = strong_analysis()
        analysis["trigger_surfaces"] = [
            {"surface": "left", "reason": "UNKNOWN_VISUAL_CHANGE"}
        ]
        result = assess_risk(analysis, pairs(), [{}] * 12, confirmed())
        component = next(
            x
            for x in result["score_breakdown"]
            if x["component"] == "unknown_change_evidence"
        )
        self.assertGreater(component["points"], 0)

    def test_no_review_requests_manual_review(self):
        result = assess_risk(strong_analysis(), pairs(), [{}] * 12, [])
        self.assertTrue(result["manual_review_required"])
        self.assertIn("HUMAN_REVIEW", {x["type"] for x in result["missing_evidence"]})

    def test_rejected_review_reduces_score(self):
        reject = confirmed()
        reject[0]["review_status"] = "REJECTED"
        accepted = assess_risk(strong_analysis(), pairs(), [{}] * 12, confirmed())
        rejected = assess_risk(strong_analysis(), pairs(), [{}] * 12, reject)
        self.assertLess(rejected["risk_score"], accepted["risk_score"])

    def test_no_abnormality_is_low(self):
        result = assess_risk({"conclusion_code": "NO_ABNORMALITY_OBSERVED"}, [], [], [])
        self.assertEqual((result["risk_score"], result["risk_level"]), (0, "LOW"))

    def test_missing_analysis_is_insufficient(self):
        result = assess_risk({"conclusion_code": "MANUAL_REVIEW_REQUIRED"}, [], [], [])
        self.assertEqual(result["risk_level"], "INSUFFICIENT_EVIDENCE")

    def test_n1_abnormal_records_missing_previous_reference(self):
        result = assess_risk(
            {
                "conclusion_code": "FIRST_OBSERVED_ABNORMAL_AT_N1",
                "trigger_surfaces": [{"surface": "front", "reason": "KNOWN_DAMAGE"}],
            },
            [],
            [{}],
            [],
        )
        self.assertIn(
            "PRE_N1_REFERENCE", {x["type"] for x in result["missing_evidence"]}
        )

    def test_oo_wrapper_matches_function(self):
        self.assertEqual(
            RiskEngine().assess(strong_analysis(), pairs(), [], confirmed()),
            assess_risk(strong_analysis(), pairs(), [], confirmed()),
        )

    def test_legal_conclusion_is_never_supported(self):
        result = assess_risk(strong_analysis(), pairs(), [{}] * 12, confirmed())
        self.assertEqual(result["legal_responsibility_conclusion"], "NOT_SUPPORTED")


if __name__ == "__main__":
    unittest.main()
