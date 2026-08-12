"""Build the controlled SYSTEM BEHAVIOR VALIDATION matrix (not model accuracy)."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from ai.runtime.risk_engine import assess_risk  # noqa: E402
from ai.runtime.sequence_locator import (  # noqa: E402
    locate_multisurface_first_abnormality,
)
from app.backend.services import MVPService  # noqa: E402

ROOT = Path("E:/JianZhengData/runtime/competition-validation-v1.0")
RUNTIME = Path("E:/JianZhengData/runtime/competition-rc-v1.0")
VIDEO = RUNTIME / "demo/competition-demo-assets-v1.0.json"
CONFIG = REPO / "configs/runtime/competition-rc-v1.0.json"


def locate(
    surfaces=("front",),
    *,
    damage_node: str | None = None,
    damage_class: str = "D02",
    damage_surface: str = "front",
    change_interval: str | None = None,
    change_surfaces=("front",),
    failed_interval: str | None = None,
    missing: set[tuple[str, str]] | None = None,
):
    missing = missing or set()
    nodes = []
    for node_id in ("N1", "N2", "N3"):
        for surface in surfaces:
            if (node_id, surface) not in missing:
                nodes.append(
                    {
                        "node_id": node_id,
                        "surface": surface,
                        "detections": (
                            [{"class_code": damage_class, "confidence": 0.9}]
                            if node_id == damage_node and surface == damage_surface
                            else []
                        ),
                    }
                )
    pairs = []
    for node_from, node_to in (("N1", "N2"), ("N2", "N3")):
        interval = f"{node_from}_TO_{node_to}"
        for surface in surfaces:
            unavailable = (node_from, surface) in missing or (
                node_to,
                surface,
            ) in missing
            pairs.append(
                {
                    "reference_node_id": node_from,
                    "current_node_id": node_to,
                    "surface": surface,
                    "pair_status": "PAIR_SURFACE_MISSING"
                    if unavailable
                    else "AVAILABLE",
                    "registration_status": "FAILED"
                    if interval == failed_interval
                    else "OK",
                    "is_significant": bool(
                        interval == change_interval
                        and surface in change_surfaces
                        and not unavailable
                    ),
                    "change_score": 0.8
                    if interval == change_interval and surface in change_surfaces
                    else 0.0,
                }
            )
    return locate_multisurface_first_abnormality(nodes, pairs), pairs, nodes


def add(scenarios, scenario_id, expected, actual, passed, evidence):
    scenarios.append(
        {
            "scenario_id": scenario_id,
            "source_type": "CONTROLLED_BUSINESS_RULE",
            "validation_label": "SYSTEM BEHAVIOR VALIDATION",
            "expected_behavior": expected,
            "actual_behavior": actual,
            "pass": bool(passed),
            "evidence": evidence,
        }
    )


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    scenarios = []
    normal, _, _ = locate()
    add(
        scenarios,
        "SBV-01-NORMAL",
        "single-surface normal => no abnormality",
        normal,
        normal["conclusion_code"] == "NO_ABNORMALITY_OBSERVED",
        "ai.runtime.sequence_locator",
    )
    d02, _, _ = locate(damage_node="N2", damage_class="D02", change_interval="N1_TO_N2")
    add(
        scenarios,
        "SBV-02-KNOWN-D02",
        "D02 at N2 => N1_TO_N2",
        {"input_class": "D02", **d02},
        d02["first_abnormal_interval"] == "N1_TO_N2",
        "controlled D02 machine detection fixture",
    )
    d03, _, _ = locate(damage_node="N2", damage_class="D03", change_interval="N1_TO_N2")
    add(
        scenarios,
        "SBV-03-KNOWN-D03",
        "D03 at N2 => N1_TO_N2",
        {"input_class": "D03", **d03},
        d03["first_abnormal_interval"] == "N1_TO_N2",
        "controlled D03 machine detection fixture",
    )
    unknown, _, _ = locate(change_interval="N1_TO_N2")
    add(
        scenarios,
        "SBV-04-UNKNOWN-CHANGE",
        "unclassified reliable change => UNKNOWN_VISUAL_CHANGE_INTERVAL",
        unknown,
        unknown["conclusion_code"] == "UNKNOWN_VISUAL_CHANGE_INTERVAL",
        "controlled open-set change fixture",
    )

    # Exercise the actual service review validation and append-only storage on an
    # already analyzed stability case, without invoking detector inference.
    service = MVPService(CONFIG)
    analyzed_cases = [
        case
        for case in service.database.list_cases()
        if service.database.get_case(case["case_id"]).get("analysis")
    ]
    if not analyzed_cases:
        raise RuntimeError(
            "run release stability verification before validation matrix"
        )
    review_case = analyzed_cases[0]["case_id"]
    existing = service.list_reviews(review_case)
    for review_class, alias, sid in (
        ("D01", "MEMBER-A", "SBV-05-D01-REVIEW"),
        ("D04", "MEMBER-B", "SBV-06-D04-REVIEW"),
        ("D05", "MEMBER-C", "SBV-07-D05-REVIEW"),
    ):
        match = next(
            (
                item
                for item in existing
                if item["review_class"] == review_class
                and item["review_status"] == "CONFIRMED"
            ),
            None,
        )
        if match is None:
            match = service.add_review(
                review_case,
                {
                    "node_from": "N1",
                    "node_to": "N2",
                    "surface": "left",
                    "review_class": review_class,
                    "review_status": "CONFIRMED",
                    "reviewer_alias": alias,
                    "review_note": "SYSTEM BEHAVIOR VALIDATION",
                    "supersedes_review_id": None,
                },
            )
            existing.append(match)
        add(
            scenarios,
            sid,
            f"{review_class} can be confirmed only as human review",
            {
                "review_id": match["review_id"],
                "review_class": match["review_class"],
                "review_status": match["review_status"],
            },
            match["review_class"] == review_class
            and match["review_status"] == "CONFIRMED",
            f"SQLite review_events:{match['review_id']}",
        )

    multi, _, _ = locate(
        ("front", "left", "right", "top"),
        change_interval="N1_TO_N2",
        change_surfaces=("left", "right"),
    )
    add(
        scenarios,
        "SBV-08-MULTISURFACE",
        "two changed surfaces are both triggers",
        multi,
        {x["surface"] for x in multi["trigger_surfaces"]} == {"left", "right"},
        "controlled four-surface fixture",
    )
    missing, _, _ = locate(("front", "left"), missing={("N2", "left")})
    add(
        scenarios,
        "SBV-09-MISSING-SURFACE",
        "missing same-surface pair is explicit",
        missing,
        missing["evidence_completeness"]["missing_pair_surface_count"] >= 1,
        "PAIR_SURFACE_MISSING fixture",
    )
    failed, failed_pairs, failed_nodes = locate(
        failed_interval="N1_TO_N2", change_interval="N1_TO_N2"
    )
    failed_risk = assess_risk(failed, failed_pairs, failed_nodes, [])
    add(
        scenarios,
        "SBV-10-REGISTRATION-FAILED",
        "failed registration requires review and never HIGH",
        {"locator": failed, "risk": failed_risk},
        failed["conclusion_code"] == "MANUAL_REVIEW_REQUIRED"
        and failed_risk["risk_level"] != "HIGH",
        "locator + risk engine",
    )
    n1, _, _ = locate(damage_node="N1")
    add(
        scenarios,
        "SBV-11-N1-ABNORMAL",
        "N1 abnormal cannot infer earlier interval",
        n1,
        n1["conclusion_code"] == "FIRST_OBSERVED_ABNORMAL_AT_N1"
        and n1["first_abnormal_interval"] is None,
        "controlled N1 fixture",
    )
    n12, _, _ = locate(change_interval="N1_TO_N2")
    add(
        scenarios,
        "SBV-12-N1-N2",
        "first change is N1_TO_N2",
        n12,
        n12["first_abnormal_interval"] == "N1_TO_N2",
        "controlled adjacent pair",
    )
    n23, _, _ = locate(change_interval="N2_TO_N3")
    add(
        scenarios,
        "SBV-13-N2-N3",
        "first change is N2_TO_N3",
        n23,
        n23["first_abnormal_interval"] == "N2_TO_N3",
        "controlled adjacent pair",
    )
    all_normal, _, _ = locate(("front", "left", "right", "top"))
    add(
        scenarios,
        "SBV-14-ALL-NORMAL",
        "all four surfaces normal",
        all_normal,
        all_normal["conclusion_code"] == "NO_ABNORMALITY_OBSERVED"
        and not all_normal["trigger_surfaces"],
        "controlled complete matrix",
    )
    incomplete, incomplete_pairs, incomplete_nodes = locate(
        ("front", "left", "right", "top"),
        change_interval="N1_TO_N2",
        change_surfaces=("front",),
        missing={("N2", "left"), ("N2", "right"), ("N2", "top")},
    )
    incomplete_risk = assess_risk(incomplete, incomplete_pairs, incomplete_nodes, [])
    add(
        scenarios,
        "SBV-15-INCOMPLETE-EVIDENCE",
        "missing matrix lowers evidence and requires review",
        {"locator": incomplete, "risk": incomplete_risk},
        incomplete_risk["manual_review_required"]
        and any(
            x["type"] == "CAPTURE_MATRIX" for x in incomplete_risk["missing_evidence"]
        ),
        "risk missing_evidence",
    )

    resolved_orders = [
        order
        for case in service.database.list_cases()
        for order in service.database.list_work_orders(case["case_id"])
        if order["current_state"] == "RESOLVED"
        and [e["current_state"] for e in order["events"]]
        == ["OPEN", "IN_REVIEW", "RESOLVED"]
    ]
    add(
        scenarios,
        "SBV-16-WORK-ORDER-LIFECYCLE",
        "OPEN→IN_REVIEW→RESOLVED with three immutable events",
        resolved_orders[0] if resolved_orders else {"status": "missing"},
        bool(resolved_orders),
        "SQLite work_orders/work_order_events from stability run",
    )
    video = json.loads(VIDEO.read_text(encoding="utf-8"))["video_validation"]
    add(
        scenarios,
        "SBV-17-VIDEO-KEYFRAME",
        "MP4 yields at least one D02/D03 abnormal keyframe",
        {
            "capability": video["capability"],
            "sampled_frame_count": video["sampled_frame_count"],
            "abnormal_frame_count": video["abnormal_frame_count"],
            "keyframes": video["top_abnormal_keyframes"],
        },
        video["capability"] == "VIDEO_DAMAGE_KEYFRAME_SCREENING"
        and video["abnormal_frame_count"] >= 1,
        str(VIDEO),
    )

    for scenario in scenarios:
        path = ROOT / f"{scenario['scenario_id'].lower()}.json"
        path.write_text(
            json.dumps(scenario, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        scenario["evidence_file"] = str(path)
    payload = {
        "report_version": "system-behavior-validation-v1.0",
        "validation_label": "SYSTEM BEHAVIOR VALIDATION",
        "not_model_accuracy": True,
        "generated_at": datetime.now().astimezone().isoformat(),
        "scenario_count": len(scenarios),
        "passed_count": sum(item["pass"] for item in scenarios),
        "scenarios": scenarios,
        "passed": all(item["pass"] for item in scenarios),
    }
    output = ROOT / "competition-validation-summary-v1.0.json"
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "passed": payload["passed"],
                "result": f"{payload['passed_count']}/{payload['scenario_count']}",
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
