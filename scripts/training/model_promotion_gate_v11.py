"""Deterministic YOLO26s@640 promotion gate for Competition RC v1.1."""

from __future__ import annotations

from typing import Any


def relative_gain(candidate: float, baseline: float) -> float:
    if baseline <= 0:
        raise ValueError("baseline must be positive")
    return (candidate - baseline) / baseline


def evaluate_promotion_gate(
    active: dict[str, Any],
    candidate: dict[str, Any],
    *,
    active_latency_ms: float,
    candidate_latency_ms: float,
) -> dict[str, Any]:
    """Require two of three val gains plus the latency ceiling."""

    metrics = {
        "overall_mAP50_95_relative_gain": relative_gain(
            candidate["overall"]["mAP50-95"], active["overall"]["mAP50-95"]
        ),
        "D02_mAP50_95_relative_gain": relative_gain(
            candidate["D02"]["mAP50-95"], active["D02"]["mAP50-95"]
        ),
        "D02_recall_relative_gain": relative_gain(
            candidate["D02"]["recall"], active["D02"]["recall"]
        ),
    }
    conditions = {key: value + 1e-12 >= 0.10 for key, value in metrics.items()}
    latency_limit = active_latency_ms * 1.75
    latency_pass = candidate_latency_ms <= latency_limit
    gain_pass_count = sum(conditions.values())
    eligible = gain_pass_count >= 2 and latency_pass
    return {
        "gate_version": "detector-promotion-v1.1",
        "relative_gains": metrics,
        "gain_conditions": conditions,
        "gain_pass_count": gain_pass_count,
        "required_gain_pass_count": 2,
        "active_latency_ms": active_latency_ms,
        "candidate_latency_ms": candidate_latency_ms,
        "latency_limit_ms": latency_limit,
        "latency_pass": latency_pass,
        "decision": "PROMOTION_ELIGIBLE" if eligible else "KEEP_CURRENT_ACTIVE",
        "candidate_test_allowed": eligible,
    }
