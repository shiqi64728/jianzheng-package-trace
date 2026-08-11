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
