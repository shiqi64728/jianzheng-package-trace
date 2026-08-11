"""Rule-based first-abnormal-interval locator for N1...Nn captures."""

from __future__ import annotations

from typing import Any


def _known(node: dict[str, Any]) -> bool:
    return bool(node.get("detections"))


def locate_first_abnormality(
    nodes: list[dict[str, Any]], pair_changes: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(nodes) < 3:
        raise ValueError("MVP序列至少需要N1/N2/N3三个节点。")
    if len(pair_changes) != len(nodes) - 1:
        raise ValueError("相邻变化结果数量必须等于节点数减一。")
    pair_by_current = {pair["current_node_id"]: pair for pair in pair_changes}
    node_states: list[dict[str, str]] = []
    for index, node in enumerate(nodes):
        known = _known(node)
        changed = False
        if index:
            changed = bool(pair_by_current[node["node_id"]].get("is_significant"))
        if known and changed:
            status = "KNOWN_DAMAGE_AND_CHANGE"
        elif known:
            status = "KNOWN_DAMAGE"
        elif changed:
            status = "UNKNOWN_CHANGE"
        else:
            status = "NORMAL"
        node_states.append({"node_id": node["node_id"], "status": status})
    failed_pairs = [
        pair for pair in pair_changes if pair.get("registration_status") == "FAILED"
    ]
    if failed_pairs:
        for state in node_states[1:]:
            if pair_by_current[state["node_id"]].get("registration_status") == "FAILED":
                state["status"] = "INSUFFICIENT_EVIDENCE"
        return {
            "conclusion_code": "MANUAL_REVIEW_REQUIRED",
            "first_abnormal_interval": None,
            "first_abnormal_node": None,
            "evidence_level": "E0",
            "node_states": node_states,
            "explanation": "相邻节点配准失败，当前视觉序列证据不足，建议人工复核。",
            "warnings": ["存在registration_status=FAILED的相邻图像对。"],
        }
    if _known(nodes[0]):
        return {
            "conclusion_code": "FIRST_OBSERVED_ABNORMAL_AT_N1",
            "first_abnormal_interval": None,
            "first_abnormal_node": nodes[0]["node_id"],
            "evidence_level": "E2",
            "node_states": node_states,
            "explanation": "异常在首个可观察节点已经存在，无法利用当前序列继续向前定位。",
            "warnings": [],
        }
    for index, pair in enumerate(pair_changes):
        target = nodes[index + 1]
        known = _known(target)
        changed = bool(pair.get("is_significant"))
        if known or changed:
            interval = f"{nodes[index]['node_id']}_TO_{target['node_id']}"
            if changed and not known:
                code = "UNKNOWN_VISUAL_CHANGE_INTERVAL"
                level = "E3"
                explanation = f"在{interval}首次检测到未分类视觉变化，建议人工复核。"
            else:
                code = "FIRST_ABNORMAL_INTERVAL"
                level = "E1" if changed else "E2"
                explanation = f"首次观察到异常的相邻区间为{interval}。"
            return {
                "conclusion_code": code,
                "first_abnormal_interval": interval,
                "first_abnormal_node": target["node_id"],
                "evidence_level": level,
                "node_states": node_states,
                "explanation": explanation,
                "warnings": [],
            }
    return {
        "conclusion_code": "NO_ABNORMALITY_OBSERVED",
        "first_abnormal_interval": None,
        "first_abnormal_node": None,
        "evidence_level": "E0",
        "node_states": node_states,
        "explanation": "当前N1...Nn序列未观察到达到工程阈值的异常。",
        "warnings": [],
    }


def _node_number(node_id: str) -> int:
    if not node_id.startswith("N") or not node_id[1:].isdigit():
        raise ValueError(f"invalid node id: {node_id}")
    return int(node_id[1:])


def _surface_state(
    current: dict[str, Any] | None, pair: dict[str, Any]
) -> dict[str, Any]:
    surface = pair["surface"]
    if pair.get("pair_status") == "PAIR_SURFACE_MISSING":
        return {
            "surface": surface,
            "status": "MISSING",
            "reliable": False,
            "change_score": 0.0,
            "pair_status": "PAIR_SURFACE_MISSING",
        }
    known = bool((current or {}).get("detections"))
    changed = bool(pair.get("is_significant"))
    registration_ok = pair.get("registration_status") != "FAILED"
    if known and changed and registration_ok:
        status = "KNOWN_DAMAGE_AND_CHANGE"
    elif known:
        status = "KNOWN_DAMAGE"
    elif changed and registration_ok:
        status = "UNKNOWN_CHANGE"
    elif not registration_ok:
        status = "INSUFFICIENT_EVIDENCE"
    else:
        status = "NORMAL"
    return {
        "surface": surface,
        "status": status,
        "reliable": known or registration_ok,
        "change_score": float(pair.get("change_score", 0.0)),
        "pair_status": pair.get("pair_status", "AVAILABLE"),
        "registration_status": pair.get("registration_status", "NOT_RUN"),
    }


def locate_multisurface_first_abnormality(
    surface_nodes: list[dict[str, Any]],
    pair_changes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Fuse same-surface evidence into adjacent node interval conclusions."""
    node_ids = sorted({item["node_id"] for item in surface_nodes}, key=_node_number)
    if len(node_ids) < 3:
        raise ValueError("multisurface sequence requires at least N1/N2/N3")
    if node_ids != [f"N{index}" for index in range(1, len(node_ids) + 1)]:
        raise ValueError("node sequence must be contiguous from N1")
    captures = {(item["node_id"], item["surface"]): item for item in surface_nodes}
    pair_map = {
        (item["reference_node_id"], item["current_node_id"], item["surface"]): item
        for item in pair_changes
    }
    all_surfaces = sorted({item["surface"] for item in surface_nodes})
    node_states: list[dict[str, Any]] = []
    n1_surfaces = []
    for surface in all_surfaces:
        capture = captures.get((node_ids[0], surface))
        if capture is None:
            status = "MISSING"
        elif capture.get("detections"):
            status = "KNOWN_DAMAGE"
        else:
            status = "NORMAL"
        n1_surfaces.append({"surface": surface, "status": status})
    node_states.append(
        {
            "node_id": node_ids[0],
            "status": (
                "KNOWN_DAMAGE"
                if any(x["status"] == "KNOWN_DAMAGE" for x in n1_surfaces)
                else "NORMAL"
            ),
            "surface_states": n1_surfaces,
        }
    )

    intervals: list[dict[str, Any]] = []
    for index in range(len(node_ids) - 1):
        reference_id, current_id = node_ids[index], node_ids[index + 1]
        surface_states: list[dict[str, Any]] = []
        for surface in all_surfaces:
            pair = pair_map.get((reference_id, current_id, surface))
            if pair is None:
                raise ValueError(
                    f"missing explicit pair result for {reference_id}->{current_id}.{surface}"
                )
            surface_states.append(
                _surface_state(captures.get((current_id, surface)), pair)
            )
        trigger_surfaces = []
        for state in surface_states:
            if state["status"] == "KNOWN_DAMAGE_AND_CHANGE":
                reason = "KNOWN_DAMAGE_AND_CHANGE"
            elif state["status"] == "KNOWN_DAMAGE":
                reason = "KNOWN_DAMAGE"
            elif state["status"] == "UNKNOWN_CHANGE" and state["reliable"]:
                reason = "UNKNOWN_VISUAL_CHANGE"
            else:
                continue
            trigger_surfaces.append(
                {
                    "surface": state["surface"],
                    "reason": reason,
                    "change_score": state["change_score"],
                }
            )
        statuses = {item["status"] for item in surface_states}
        if "KNOWN_DAMAGE_AND_CHANGE" in statuses:
            aggregate = "FIRST_ABNORMAL_INTERVAL"
            level = "E1"
        elif "KNOWN_DAMAGE" in statuses:
            aggregate = "FIRST_ABNORMAL_INTERVAL"
            level = "E2"
        elif "UNKNOWN_CHANGE" in statuses:
            aggregate = "UNKNOWN_VISUAL_CHANGE_INTERVAL"
            level = "E3"
        elif statuses <= {"MISSING", "INSUFFICIENT_EVIDENCE"}:
            aggregate = "INSUFFICIENT_EVIDENCE"
            level = "E0"
        else:
            aggregate = "NORMAL"
            level = "E0"
        interval = {
            "interval": f"{reference_id}_TO_{current_id}",
            "reference_node_id": reference_id,
            "current_node_id": current_id,
            "conclusion_code": aggregate,
            "evidence_level": level,
            "surface_states": surface_states,
            "trigger_surfaces": trigger_surfaces,
        }
        intervals.append(interval)
        node_status = (
            "KNOWN_DAMAGE_AND_CHANGE"
            if "KNOWN_DAMAGE_AND_CHANGE" in statuses
            else "KNOWN_DAMAGE"
            if "KNOWN_DAMAGE" in statuses
            else "UNKNOWN_CHANGE"
            if "UNKNOWN_CHANGE" in statuses
            else "INSUFFICIENT_EVIDENCE"
            if statuses <= {"MISSING", "INSUFFICIENT_EVIDENCE"}
            else "NORMAL"
        )
        node_states.append(
            {
                "node_id": current_id,
                "status": node_status,
                "surface_states": surface_states,
            }
        )

    n1_trigger = [
        {"surface": item["surface"], "reason": "KNOWN_DAMAGE", "change_score": 0.0}
        for item in n1_surfaces
        if item["status"] == "KNOWN_DAMAGE"
    ]
    if n1_trigger:
        conclusion = "FIRST_OBSERVED_ABNORMAL_AT_N1"
        first_interval = None
        first_node = node_ids[0]
        evidence_level = "E2"
        trigger_surfaces = n1_trigger
    else:
        first = next(
            (
                interval
                for interval in intervals
                if interval["conclusion_code"]
                in {"FIRST_ABNORMAL_INTERVAL", "UNKNOWN_VISUAL_CHANGE_INTERVAL"}
            ),
            None,
        )
        if first:
            conclusion = first["conclusion_code"]
            first_interval = first["interval"]
            first_node = first["current_node_id"]
            evidence_level = first["evidence_level"]
            trigger_surfaces = first["trigger_surfaces"]
        else:
            conclusion = (
                "MANUAL_REVIEW_REQUIRED"
                if any(
                    interval["conclusion_code"] == "INSUFFICIENT_EVIDENCE"
                    for interval in intervals
                )
                else "NO_ABNORMALITY_OBSERVED"
            )
            first_interval = None
            first_node = None
            evidence_level = "E0"
            trigger_surfaces = []
    missing_count = sum(
        state["status"] == "MISSING"
        for interval in intervals
        for state in interval["surface_states"]
    )
    return {
        "conclusion_code": conclusion,
        "first_abnormal_interval": first_interval,
        "first_abnormal_node": first_node,
        "evidence_level": evidence_level,
        "trigger_surfaces": trigger_surfaces,
        "intervals": intervals,
        "node_states": node_states,
        "evidence_completeness": {
            "available_capture_count": len(surface_nodes),
            "expected_matrix_cells": len(node_ids) * len(all_surfaces),
            "missing_pair_surface_count": missing_count,
        },
        "explanation": (
            "Only same-surface adjacent captures were compared; missing or failed pairs do not independently prove abnormality."
        ),
        "warnings": (
            [f"{missing_count} same-surface adjacent comparisons were unavailable"]
            if missing_count
            else []
        ),
    }
