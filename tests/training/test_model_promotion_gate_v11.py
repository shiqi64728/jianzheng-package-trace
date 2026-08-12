from __future__ import annotations

import unittest

from scripts.training.model_promotion_gate_v11 import (
    evaluate_promotion_gate,
    relative_gain,
)


ACTIVE = {"overall": {"mAP50-95": 0.10}, "D02": {"mAP50-95": 0.04, "recall": 0.20}}


def candidate(overall=0.10, d02_ap=0.04, d02_recall=0.20):
    return {
        "overall": {"mAP50-95": overall},
        "D02": {"mAP50-95": d02_ap, "recall": d02_recall},
    }


class ModelPromotionGateTests(unittest.TestCase):
    def test_relative_gain(self):
        self.assertAlmostEqual(relative_gain(0.11, 0.10), 0.1)

    def test_nonpositive_baseline_is_rejected(self):
        with self.assertRaises(ValueError):
            relative_gain(1, 0)

    def test_two_gains_and_latency_pass_are_eligible(self):
        result = evaluate_promotion_gate(
            ACTIVE,
            candidate(0.11, 0.044, 0.20),
            active_latency_ms=10,
            candidate_latency_ms=17.5,
        )
        self.assertEqual(result["decision"], "PROMOTION_ELIGIBLE")

    def test_only_one_gain_is_not_eligible(self):
        result = evaluate_promotion_gate(
            ACTIVE,
            candidate(0.11, 0.04, 0.20),
            active_latency_ms=10,
            candidate_latency_ms=10,
        )
        self.assertEqual(result["decision"], "KEEP_CURRENT_ACTIVE")

    def test_latency_failure_blocks_three_gains(self):
        result = evaluate_promotion_gate(
            ACTIVE,
            candidate(0.12, 0.05, 0.25),
            active_latency_ms=10,
            candidate_latency_ms=17.6,
        )
        self.assertFalse(result["latency_pass"])
        self.assertEqual(result["decision"], "KEEP_CURRENT_ACTIVE")

    def test_exact_ten_percent_passes(self):
        result = evaluate_promotion_gate(
            ACTIVE,
            candidate(0.11, 0.044, 0.20),
            active_latency_ms=10,
            candidate_latency_ms=10,
        )
        self.assertEqual(result["gain_pass_count"], 2)

    def test_candidate_test_allowed_only_when_eligible(self):
        blocked = evaluate_promotion_gate(
            ACTIVE, candidate(), active_latency_ms=10, candidate_latency_ms=10
        )
        self.assertFalse(blocked["candidate_test_allowed"])

    def test_latency_limit_is_one_point_seven_five(self):
        result = evaluate_promotion_gate(
            ACTIVE, candidate(), active_latency_ms=8, candidate_latency_ms=8
        )
        self.assertEqual(result["latency_limit_ms"], 14)

    def test_all_relative_gains_are_exposed(self):
        result = evaluate_promotion_gate(
            ACTIVE, candidate(), active_latency_ms=10, candidate_latency_ms=10
        )
        self.assertEqual(len(result["relative_gains"]), 3)


if __name__ == "__main__":
    unittest.main()
