"""Generate auditable JSON and UTF-8 HTML evidence reports."""

from __future__ import annotations

import html
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

DISCLAIMER = (
    "本报告提供计算机视觉和结构化证据辅助分析，\n"
    "仅用于异常定位、证据整理和人工责任复核，\n"
    "不构成法律责任认定或赔偿结论。"
)

LIMITATIONS = [
    "本报告不能单独作为法律责任认定结论。",
    "当前主动检测器仅自动支持 D02 表面凹陷和 D03 纸箱破口。",
    "D01/D04/D05 由开放集变化发现后进入人工复核，不是 AI 自动分类。",
    "UNKNOWN_VISUAL_CHANGE 不会自动映射为 D01、D04 或 D05。",
    "缺失表面与配准失败会降低证据完整度，不能单独证明异常。",
    "外观数字指纹是工程证据记录，不是跨摄像机身份识别。",
    "风险分数来自可解释规则引擎，不是法律责任认定。",
]


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"无法序列化类型：{type(value).__name__}")


def _surface_evidence(
    nodes: list[dict[str, Any]],
    pair_changes: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "node_id": node["node_id"],
            "surface": node.get("surface", "front"),
            "image_path": node.get("image_path"),
            "image_sha256": node.get("fingerprint", {}).get("image_sha256"),
            "appearance_fingerprint": node.get("fingerprint", {}),
            "machine_detections": node.get("detections", []),
            "registration_evidence": [
                pair
                for pair in pair_changes
                if pair.get("surface", "front") == node.get("surface", "front")
                and node["node_id"]
                in {pair.get("reference_node_id"), pair.get("current_node_id")}
            ],
            "unknown_change_regions": [
                region
                for pair in pair_changes
                if pair.get("surface", "front") == node.get("surface", "front")
                and pair.get("current_node_id") == node["node_id"]
                for region in pair.get("regions", [])
            ],
            "human_reviews": [
                review
                for review in reviews
                if review.get("surface") == node.get("surface", "front")
                and review.get("node_to") == node["node_id"]
            ],
        }
        for node in nodes
    ]


def _matrix(nodes: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    matrix: dict[str, dict[str, str]] = {}
    for node in nodes:
        matrix.setdefault(node["node_id"], {})[node.get("surface", "front")] = (
            node.get("fingerprint", {}).get("image_sha256") or "MISSING_SHA"
        )
    return matrix


def _work_order_history(work_orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "work_order_id": order.get("work_order_id"),
            "title": order.get("title"),
            "current_state": order.get("current_state"),
            "assigned_alias": order.get("assigned_alias"),
            "events": order.get("events", []),
        }
        for order in work_orders
    ]


def generate_evidence_report(
    case: dict[str, Any],
    nodes: list[dict[str, Any]],
    pair_changes: list[dict[str, Any]],
    analysis: dict[str, Any],
    model_info: dict[str, Any],
    output_dir: str | Path,
    *,
    node_summaries: list[dict[str, Any]] | None = None,
    reviews: list[dict[str, Any]] | None = None,
    report_revision: int | None = None,
    logistics_nodes: list[dict[str, Any]] | None = None,
    risk: dict[str, Any] | None = None,
    work_orders: list[dict[str, Any]] | None = None,
    report_version: str | None = None,
) -> dict[str, str]:
    """Write one immutable report revision and return its two absolute paths."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().astimezone().isoformat()
    reviews = reviews or []
    node_summaries = node_summaries or []
    logistics_nodes = logistics_nodes or []
    work_orders = work_orders or []
    if report_version is None:
        report_version = (
            "evidence-report-v1.0"
            if "rc-v1.0" in str(case.get("pipeline_version", ""))
            else "evidence-report-v0.2"
            if report_revision is not None
            else "evidence-report-v0.1"
        )
    is_revisioned = report_revision is not None
    missing_evidence = list((risk or {}).get("missing_evidence", []))
    expected = analysis.get("evidence_completeness", {}).get("expected_matrix_cells")
    available = analysis.get("evidence_completeness", {}).get("available_capture_count")
    if expected and available is not None and available < expected:
        missing_evidence.append(
            {"type": "CAPTURE_MATRIX", "available": available, "expected": expected}
        )

    payload = {
        "report_version": report_version,
        "report_revision": report_revision,
        "generated_at": generated_at,
        "case_summary": {
            "case_id": case["case_id"],
            "case_name": case.get("case_name"),
            "status": case.get("status"),
            "notes": case.get("notes", ""),
        },
        "case_id": case["case_id"],
        "pipeline_version": case["pipeline_version"],
        "model": model_info,
        "model_version": model_info.get("model_version"),
        "model_sha256": model_info.get("sha256"),
        "node_surface_matrix": _matrix(nodes),
        "timeline": logistics_nodes,
        "nodes": nodes,
        "image_sha256_records": [
            {
                "node_id": node.get("node_id"),
                "surface": node.get("surface", "front"),
                "sha256": node.get("fingerprint", {}).get("image_sha256"),
            }
            for node in nodes
        ],
        "appearance_fingerprints": node_summaries,
        "pair_changes": pair_changes,
        "machine_detections": [
            detection for node in nodes for detection in node.get("detections", [])
        ],
        "unknown_changes": [
            pair
            for pair in pair_changes
            if pair.get("is_significant") and not pair.get("known_damage_detected")
        ],
        "registration_evidence": [
            {
                "reference_node_id": pair.get("reference_node_id"),
                "current_node_id": pair.get("current_node_id"),
                "surface": pair.get("surface", "front"),
                "pair_status": pair.get("pair_status", "AVAILABLE"),
                "registration_status": pair.get("registration_status"),
                "registration": pair.get("registration", {}),
            }
            for pair in pair_changes
        ],
        "first_abnormal_interval": analysis.get("first_abnormal_interval"),
        "trigger_surfaces": analysis.get("trigger_surfaces", []),
        "machine_analysis": analysis,
        "analysis": analysis,
        "risk_assessment": risk or {"status": "MISSING"},
        "risk_score": (risk or {}).get("risk_score"),
        "risk_score_breakdown": (risk or {}).get("score_breakdown", []),
        "human_reviews": reviews,
        "work_order_history": _work_order_history(work_orders),
        "missing_evidence": missing_evidence or [],
        "surface_evidence": _surface_evidence(nodes, pair_changes, reviews),
        "limitations": LIMITATIONS,
        "disclaimer": DISCLAIMER,
    }
    suffix = f"-r{report_revision:03d}" if is_revisioned else ""
    json_path = output / f"report{suffix}.json"
    html_path = output / f"report{suffix}.html"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default) + "\n",
        encoding="utf-8",
    )

    node_cards = []
    for node in nodes:
        image_path = Path(node["image_path"])
        relative = Path(os.path.relpath(image_path, html_path.parent)).as_posix()
        label = f"{node['node_id']}.{node.get('surface', 'front')}"
        detections = node.get("detections", [])
        detection_text = (
            "；".join(
                f"{item['class_code']} {item['class_name']} {float(item['confidence']):.3f}"
                for item in detections
            )
            or "无 D02/D03 检测"
        )
        sha = node.get("fingerprint", {}).get("image_sha256", "MISSING")
        node_cards.append(
            "<article class='card'>"
            f"<h3>{html.escape(label)}</h3>"
            f"<img src='{html.escape(relative)}' alt='{html.escape(label)}'>"
            f"<p><b>Image SHA-256</b><code>{html.escape(str(sha))}</code></p>"
            f"<p><b>机器检测</b>{html.escape(detection_text)}</p>"
            "</article>"
        )

    def rows(items: list[dict[str, Any]], keys: list[str], empty: str) -> str:
        if not items:
            return f"<tr><td colspan='{len(keys)}'>{html.escape(empty)}</td></tr>"
        return "".join(
            "<tr>"
            + "".join(f"<td>{html.escape(str(item.get(key, '')))}</td>" for key in keys)
            + "</tr>"
            for item in items
        )

    risk = risk or {}
    risk_rows = rows(
        risk.get("score_breakdown", []),
        ["component", "points", "max_points", "reason"],
        "尚无风险评分",
    )
    timeline_rows = rows(
        logistics_nodes,
        [
            "package_alias",
            "node_id",
            "node_type",
            "event_time",
            "location_alias",
            "device_alias",
            "status",
            "notes",
        ],
        "尚未导入结构化物流节点",
    )
    flat_events = [
        {"work_order_id": order.get("work_order_id"), **event}
        for order in work_orders
        for event in order.get("events", [])
    ]
    work_rows = rows(
        flat_events,
        [
            "work_order_id",
            "event_type",
            "previous_state",
            "current_state",
            "actor_alias",
            "created_at",
            "note",
        ],
        "尚无工单历史",
    )
    review_rows = rows(
        reviews,
        [
            "node_from",
            "node_to",
            "surface",
            "machine_result",
            "review_class",
            "review_status",
            "reviewer_alias",
            "created_at",
        ],
        "尚无人工复核",
    )
    conclusion = analysis.get("first_abnormal_interval") or analysis.get(
        "conclusion_code", "MISSING"
    )
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>件证 Evidence Report v1.0 {html.escape(case["case_id"])}</title>
<style>
body{{font-family:"Microsoft YaHei",sans-serif;margin:0;background:#f3f6f4;color:#17352d}}main{{max-width:1200px;margin:auto;padding:30px}}
h1,h2{{color:#075b4a}}code{{display:block;word-break:break-all;font-size:.75rem}}.hero,.card,.notice,table{{background:#fff;border:1px solid #d5e3dd;border-radius:12px;padding:16px;margin:12px 0}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}}.card img{{width:100%;height:180px;object-fit:contain;background:#edf2ef}}table{{width:100%;border-collapse:collapse;padding:0}}th,td{{padding:8px;border-bottom:1px solid #e0e9e5;text-align:left;font-size:.88rem}}.score{{font-size:2rem;color:#9b3c10}}.notice{{white-space:pre-line;border-left:5px solid #e19a21}}
</style></head><body><main>
<section class="hero"><p>JIANZHENG · {html.escape(report_version)}</p><h1>件证结构化证据辅助分析报告</h1>
<p>Case ID：<code>{html.escape(case["case_id"])}</code></p><p>生成时间：{html.escape(generated_at)}</p>
<p>Pipeline：{html.escape(str(case.get("pipeline_version")))} · Model：{html.escape(str(model_info.get("model_version")))}</p></section>
<h2>案件摘要与机器结论</h2><section class="hero"><p>首次异常区间：<b>{html.escape(str(conclusion))}</b></p><p>技术证据等级：{html.escape(str(analysis.get("evidence_level", "E0")))}</p><p>{html.escape(str(analysis.get("explanation", "")))}</p></section>
<h2>Node × Surface 证据矩阵</h2><div class="grid">{"".join(node_cards)}</div>
<h2>结构化节点时间线</h2><table><thead><tr><th>包裹别名</th><th>节点</th><th>类型</th><th>时间</th><th>位置别名</th><th>设备别名</th><th>状态</th><th>备注</th></tr></thead><tbody>{timeline_rows}</tbody></table>
<h2>风险辅助评分</h2><section class="hero"><div class="score">{html.escape(str(risk.get("risk_score", "MISSING")))} / 100</div><p>等级：{html.escape(str(risk.get("risk_level", "MISSING")))} · 人工复核：{html.escape(str(risk.get("manual_review_required", "MISSING")))}</p></section>
<table><thead><tr><th>组成项</th><th>得分</th><th>满分</th><th>解释</th></tr></thead><tbody>{risk_rows}</tbody></table>
<h2>人工复核</h2><table><thead><tr><th>起点</th><th>终点</th><th>表面</th><th>机器结果</th><th>人工类别</th><th>状态</th><th>复核别名</th><th>时间</th></tr></thead><tbody>{review_rows}</tbody></table>
<h2>工单事件历史（append-only）</h2><table><thead><tr><th>工单</th><th>事件</th><th>原状态</th><th>新状态</th><th>操作者</th><th>时间</th><th>备注</th></tr></thead><tbody>{work_rows}</tbody></table>
<h2>缺失证据</h2><pre>{html.escape(json.dumps(missing_evidence or [], ensure_ascii=False, indent=2))}</pre>
<section class="notice"><b>限制与固定声明</b>\n{html.escape(DISCLAIMER)}\n\n{html.escape("；".join(LIMITATIONS))}</section>
</main></body></html>"""
    html_path.write_text(document, encoding="utf-8")
    return {"json_path": str(json_path), "html_path": str(html_path)}
