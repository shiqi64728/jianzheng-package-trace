"""Deterministic, explainable responsibility-risk assistance rules.

This module does not decide legal responsibility.  It only scores the strength
and consistency of the structured evidence already produced by the vision and
human-review pipeline.
"""

from __future__ import annotations

from typing import Any, Iterable

RISK_ENGINE_VERSION = "responsibility-risk-rules-v1.0"
RISK_LEVELS = ("LOW", "MEDIUM", "HIGH", "INSUFFICIENT_EVIDENCE")


def _component(name: str, points: int, maximum: int, reason: str) -> dict[str, Any]:
    return {
        "component": name,
        "points": int(max(0, min(points, maximum))),
        "max_points": maximum,
        "reason": reason,
    }


def _latest_reviews(reviews: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[tuple[str, str, str], dict[str, Any]] = {}
    for review in reviews:
        key = (
            str(review.get("node_from", "")),
            str(review.get("node_to", "")),
            str(review.get("surface", "front")),
        )
        latest[key] = review
    return list(latest.values())


def assess_risk(
    analysis: dict[str, Any] | None,
    pair_changes: Iterable[dict[str, Any]] | None = None,
    nodes: Iterable[dict[str, Any]] | None = None,
    reviews: Iterable[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return a reproducible 0-100 evidence-risk assessment.

    The score is the exact sum of the nine returned components.  A failed
    registration on the relevant interval caps the score at 59, preventing a
    HIGH result.  Missing evidence is represented explicitly rather than being
    silently interpreted as normality.
    """

    analysis = analysis or {}
    pairs = list(pair_changes or [])
    captures = list(nodes or [])
    latest_reviews = _latest_reviews(reviews or [])
    interval = analysis.get("first_abnormal_interval")
    conclusion = str(analysis.get("conclusion_code", ""))
    trigger_surfaces = list(analysis.get("trigger_surfaces") or [])
    completeness = analysis.get("evidence_completeness") or {}
    abnormal_signal = bool(
        interval or conclusion == "FIRST_OBSERVED_ABNORMAL_AT_N1" or trigger_surfaces
    )

    supporting: list[dict[str, Any]] = []
    conflicting: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    factors: list[dict[str, Any]] = []

    if interval:
        first_points = 18
        first_reason = f"首次异常区间已定位为 {interval}"
        supporting.append({"type": "FIRST_ABNORMAL_INTERVAL", "value": interval})
    elif conclusion == "FIRST_OBSERVED_ABNORMAL_AT_N1":
        first_points = 10
        first_reason = "首个观测节点已异常，缺少更早参考节点"
        missing.append({"type": "PRE_N1_REFERENCE", "reason": "无法定位 N1 之前区间"})
    else:
        first_points = 0
        first_reason = "未定位首次异常区间"
        if conclusion not in {"NO_ABNORMALITY_OBSERVED", ""}:
            missing.append({"type": "FIRST_ABNORMAL_INTERVAL", "reason": conclusion})

    reasons = [str(item.get("reason", "")) for item in trigger_surfaces]
    known_count = sum("KNOWN_DAMAGE" in reason for reason in reasons)
    unknown_count = sum("UNKNOWN_VISUAL_CHANGE" in reason for reason in reasons)
    known_points = min(18, known_count * 9) if abnormal_signal else 0
    unknown_points = min(10, unknown_count * 5) if abnormal_signal else 0
    if known_count:
        supporting.append({"type": "KNOWN_DETECTOR_EVIDENCE", "count": known_count})
    if unknown_count:
        supporting.append({"type": "OPEN_SET_CHANGE_EVIDENCE", "count": unknown_count})
    if abnormal_signal and not known_count:
        missing.append(
            {"type": "KNOWN_DETECTOR_EVIDENCE", "reason": "无 D02/D03 触发证据"}
        )

    relevant_pairs = pairs
    if interval and "_TO_" in interval:
        node_from, node_to = interval.split("_TO_", 1)
        relevant_pairs = [
            pair
            for pair in pairs
            if pair.get("reference_node_id") == node_from
            and pair.get("current_node_id") == node_to
        ]
    available_pairs = [
        pair
        for pair in relevant_pairs
        if pair.get("pair_status", "AVAILABLE") == "AVAILABLE"
    ]
    failed_pairs = [
        pair
        for pair in available_pairs
        if str(pair.get("registration_status", "")).upper() not in {"OK", "SUCCESS"}
    ]
    successful_pairs = [pair for pair in available_pairs if pair not in failed_pairs]
    if abnormal_signal and successful_pairs:
        ratio = len(successful_pairs) / max(1, len(available_pairs))
        registration_points = round(12 * ratio)
        supporting.append(
            {
                "type": "REGISTRATION",
                "successful": len(successful_pairs),
                "available": len(available_pairs),
            }
        )
    else:
        registration_points = 0
    if failed_pairs:
        conflicting.append(
            {
                "type": "REGISTRATION_FAILED",
                "count": len(failed_pairs),
                "effect": "HIGH capped",
            }
        )
    if (
        abnormal_signal
        and not available_pairs
        and conclusion != "FIRST_OBSERVED_ABNORMAL_AT_N1"
    ):
        missing.append({"type": "REGISTRATION", "reason": "相关区间没有可用配准对"})

    expected = int(completeness.get("expected_matrix_cells") or 0)
    available = int(completeness.get("available_capture_count") or len(captures))
    coverage_ratio = (
        min(1.0, available / expected) if expected else (1.0 if captures else 0.0)
    )
    coverage_points = round(10 * coverage_ratio) if abnormal_signal else 0
    completeness_points = round(8 * coverage_ratio) if abnormal_signal else 0
    if expected and available < expected:
        missing.append(
            {"type": "CAPTURE_MATRIX", "available": available, "expected": expected}
        )

    unique_trigger_surfaces = {
        str(item.get("surface", "")) for item in trigger_surfaces
    }
    multi_points = 0
    if abnormal_signal:
        if len(unique_trigger_surfaces) >= 2:
            multi_points = 8
            supporting.append(
                {
                    "type": "MULTI_SURFACE_CONSISTENCY",
                    "surfaces": sorted(unique_trigger_surfaces),
                }
            )
        elif len(unique_trigger_surfaces) == 1:
            multi_points = 3
            missing.append(
                {"type": "MULTI_SURFACE_CORROBORATION", "reason": "仅一个表面触发"}
            )

    confirmed = [r for r in latest_reviews if r.get("review_status") == "CONFIRMED"]
    rejected = [r for r in latest_reviews if r.get("review_status") == "REJECTED"]
    unsure = [r for r in latest_reviews if r.get("review_status") == "UNSURE"]
    human_points = min(10, len(confirmed) * 5) if abnormal_signal else 0
    if confirmed:
        supporting.append(
            {
                "type": "HUMAN_REVIEW_CONFIRMED",
                "classes": sorted({str(r.get("review_class")) for r in confirmed}),
            }
        )
    if rejected:
        conflicting.append({"type": "HUMAN_REVIEW_REJECTED", "count": len(rejected)})
    if unsure:
        missing.append({"type": "HUMAN_REVIEW_UNSURE", "count": len(unsure)})
    if abnormal_signal and not latest_reviews:
        missing.append({"type": "HUMAN_REVIEW", "reason": "尚未人工复核"})

    temporal_points = 0
    if abnormal_signal:
        states = list(analysis.get("node_states") or [])
        abnormal_states = [
            state
            for state in states
            if state.get("status")
            in {"KNOWN_DAMAGE", "KNOWN_DAMAGE_AND_CHANGE", "UNKNOWN_CHANGE"}
        ]
        if len(abnormal_states) >= 2:
            temporal_points = 6
            supporting.append(
                {"type": "TEMPORAL_PERSISTENCE", "node_count": len(abnormal_states)}
            )
        elif abnormal_states:
            temporal_points = 3
        else:
            missing.append(
                {"type": "TEMPORAL_CONSISTENCY", "reason": "无后续持久性证据"}
            )

    breakdown = [
        _component("first_abnormal_interval", first_points, 18, first_reason),
        _component(
            "known_detector_evidence",
            known_points,
            18,
            f"D02/D03 触发表面数={known_count}",
        ),
        _component(
            "unknown_change_evidence",
            unknown_points,
            10,
            f"开放集变化触发表面数={unknown_count}",
        ),
        _component(
            "registration_confidence",
            registration_points,
            12,
            f"成功={len(successful_pairs)}，失败={len(failed_pairs)}",
        ),
        _component(
            "surface_coverage", coverage_points, 10, f"采集覆盖率={coverage_ratio:.3f}"
        ),
        _component(
            "multi_surface_consistency",
            multi_points,
            8,
            f"触发表面数={len(unique_trigger_surfaces)}",
        ),
        _component(
            "evidence_completeness",
            completeness_points,
            8,
            f"可用={available}，期望={expected or 'unknown'}",
        ),
        _component(
            "human_review_status",
            human_points,
            10,
            f"确认={len(confirmed)}，驳回={len(rejected)}，不确定={len(unsure)}",
        ),
        _component(
            "temporal_consistency", temporal_points, 6, "异常在后续节点的持续一致性"
        ),
    ]
    score = sum(item["points"] for item in breakdown)

    # A rejecting review is contradictory evidence and must lower the score.
    if rejected and score:
        reduction = min(score, min(15, len(rejected) * 8))
        score -= reduction
        breakdown[7]["points"] = max(0, breakdown[7]["points"] - reduction)
        # If the reduction is larger than the human component, deduct the rest
        # from the first-interval component so sum(breakdown) remains exact.
        remainder = reduction - human_points
        if remainder > 0:
            breakdown[0]["points"] = max(0, breakdown[0]["points"] - remainder)
        score = sum(item["points"] for item in breakdown)

    score_cap: int | None = None
    if failed_pairs and score > 59:
        score_cap = 59
        overflow = score - score_cap
        # Apply the cap transparently to registration first, then first interval.
        take = min(overflow, breakdown[3]["points"])
        breakdown[3]["points"] -= take
        overflow -= take
        if overflow:
            breakdown[0]["points"] = max(0, breakdown[0]["points"] - overflow)
        score = sum(item["points"] for item in breakdown)

    if not abnormal_signal and (missing or conclusion == "MANUAL_REVIEW_REQUIRED"):
        level = "INSUFFICIENT_EVIDENCE"
    elif not abnormal_signal:
        level = "LOW"
    elif score >= 70 and not failed_pairs:
        level = "HIGH"
    elif score >= 40:
        level = "MEDIUM"
    elif missing:
        level = "INSUFFICIENT_EVIDENCE"
    else:
        level = "LOW"

    for item in breakdown:
        if item["points"]:
            factors.append(
                {
                    "factor": item["component"],
                    "points": item["points"],
                    "reason": item["reason"],
                }
            )

    return {
        "engine_version": RISK_ENGINE_VERSION,
        "risk_score": score,
        "risk_level": level,
        "risk_factors": factors,
        "supporting_evidence": supporting,
        "conflicting_evidence": conflicting,
        "missing_evidence": missing,
        "manual_review_required": bool(
            abnormal_signal
            and (not confirmed or level in {"HIGH", "MEDIUM", "INSUFFICIENT_EVIDENCE"})
        ),
        "score_breakdown": breakdown,
        "score_cap": score_cap,
        "legal_responsibility_conclusion": "NOT_SUPPORTED",
    }


class RiskEngine:
    """Small OO wrapper used by the service layer and integration tests."""

    version = RISK_ENGINE_VERSION

    def assess(
        self,
        analysis: dict[str, Any] | None,
        pair_changes: Iterable[dict[str, Any]] | None = None,
        nodes: Iterable[dict[str, Any]] | None = None,
        reviews: Iterable[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return assess_risk(analysis, pair_changes, nodes, reviews)
