"""Generate auditable JSON and local HTML evidence reports."""

from __future__ import annotations

import html
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

DISCLAIMER = "本报告用于视觉异常定位与责任辅助分析，不能单独作为法律责任认定结论。"


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"无法序列化类型：{type(value).__name__}")


def _surface_evidence(
    nodes: list[dict[str, Any]],
    pair_changes: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    evidence = []
    for node in nodes:
        evidence.append(
            {
                "node_id": node["node_id"],
                "surface": node.get("surface", "front"),
                "image_sha256": node.get("fingerprint", {}).get("image_sha256"),
                "fingerprint": node.get("fingerprint", {}),
                "detections": node.get("detections", []),
                "registration_pairs": [
                    pair
                    for pair in pair_changes
                    if pair.get("surface", "front") == node.get("surface", "front")
                    and node["node_id"]
                    in {
                        pair["reference_node_id"],
                        pair["current_node_id"],
                    }
                ],
                "change_regions": [
                    region
                    for pair in pair_changes
                    if pair.get("surface", "front") == node.get("surface", "front")
                    and pair["current_node_id"] == node["node_id"]
                    for region in pair.get("regions", [])
                ],
                "human_review": [
                    review
                    for review in reviews
                    if review["surface"] == node.get("surface", "front")
                    and review["node_to"] == node["node_id"]
                ],
            }
        )
    return evidence


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
) -> dict[str, str]:
    """Write a report; v0.2 revisions never overwrite earlier report files."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().astimezone().isoformat()
    reviews = reviews or []
    node_summaries = node_summaries or []
    v02 = report_revision is not None
    payload = {
        "report_version": "evidence-report-v0.2" if v02 else "evidence-report-v0.1",
        "report_revision": report_revision,
        "case_id": case["case_id"],
        "analysis_time": generated_at,
        "pipeline_version": case["pipeline_version"],
        "model": model_info,
        "nodes": nodes,
        "node_fingerprint_summaries": node_summaries,
        "pair_changes": pair_changes,
        "machine_analysis": analysis,
        "human_reviews": reviews,
        "surface_evidence": _surface_evidence(nodes, pair_changes, reviews),
        "limitations": [
            "当前主动检测器仅支持D02表面凹陷与D03纸箱破口。",
            "D01/D04/D05由开放集变化发现后进入人工复核，不是AI自动分类。",
            "UNKNOWN_VISUAL_CHANGE不自动分类为D01、D04或D05。",
            "缺失表面与配准失败会降低证据完整度，不单独判为异常。",
            "外观数字指纹是工程记录，不是跨拍摄密码学视觉身份。",
        ],
        "disclaimer": DISCLAIMER,
    }
    # Preserve the v0.1 JSON key for old clients while v0.2 exposes the clearer key.
    payload["analysis"] = analysis
    suffix = f"-r{report_revision:03d}" if v02 else ""
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
        detections = node.get("detections", [])
        detection_text = (
            "、".join(
                f"{item['class_code']} {item['class_name']} {item['confidence']:.3f}"
                for item in detections
            )
            or "无D02/D03检测"
        )
        fingerprint = node.get("fingerprint", {})
        label = f"{node['node_id']}.{node.get('surface', 'front')}"
        node_cards.append(
            "<section class='card'>"
            f"<h3>{html.escape(label)}</h3>"
            f"<img src='{html.escape(relative)}' alt='{html.escape(label)}'>"
            f"<p><b>SHA-256：</b><code>{html.escape(fingerprint.get('image_sha256', ''))}</code></p>"
            f"<p><b>ORB：</b>{int(fingerprint.get('orb_keypoint_count', 0))}</p>"
            f"<p><b>检测：</b>{html.escape(detection_text)}</p>"
            "</section>"
        )
    pair_rows = []
    for pair in pair_changes:
        pair_rows.append(
            "<tr>"
            f"<td>{html.escape(pair['reference_node_id'])} → {html.escape(pair['current_node_id'])}</td>"
            f"<td>{html.escape(pair.get('surface', 'front'))}</td>"
            f"<td>{html.escape(pair.get('pair_status', 'AVAILABLE'))}</td>"
            f"<td>{html.escape(pair['registration_status'])}</td>"
            f"<td>{float(pair.get('change_score', 0.0)):.4f}</td>"
            f"<td>{float(pair.get('changed_pixel_ratio', 0.0)):.4%}</td>"
            "</tr>"
        )
    review_rows = []
    for review in reviews:
        review_rows.append(
            "<tr>"
            f"<td>{html.escape(review['node_from'])} → {html.escape(review['node_to'])}</td>"
            f"<td>{html.escape(review['surface'])}</td>"
            f"<td>{html.escape(review['machine_result'])}</td>"
            f"<td>{html.escape(review['review_class'])}</td>"
            f"<td>{html.escape(review['review_status'])}</td>"
            f"<td>{html.escape(review['reviewer_alias'])}</td>"
            f"<td>{html.escape(review.get('review_note', ''))}</td>"
            "</tr>"
        )
    trigger_text = (
        "、".join(
            f"{item['surface']} ({item['reason']}, {float(item.get('change_score', 0)):.3f})"
            for item in analysis.get("trigger_surfaces", [])
        )
        or "无"
    )
    conclusion = analysis.get("first_abnormal_interval") or analysis.get(
        "conclusion_code", ""
    )
    document = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>件证证据报告 {html.escape(case["case_id"])}</title>
<style>
body{{font-family:"Microsoft YaHei",sans-serif;margin:0;background:#f4f7f5;color:#17352d}}
main{{max-width:1180px;margin:auto;padding:32px}} h1{{color:#0b5e4d}} code{{word-break:break-all}}
.hero,.card,table,.notice{{background:white;border:1px solid #d9e5e0;border-radius:14px;padding:18px;margin:14px 0}}
.nodes{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px}}
.card img{{width:100%;height:190px;object-fit:contain;background:#edf2ef;border-radius:8px}}
table{{width:100%;border-collapse:collapse}} td,th{{padding:9px;border-bottom:1px solid #e2ebe7;text-align:left}}
.result{{font-size:1.3rem;color:#9b3c10}} .notice{{border-left:5px solid #e19a21}}
.badge{{display:inline-block;background:#d9eee7;border-radius:20px;padding:5px 10px}}
</style></head><body><main>
<div class="hero"><h1>件证 · 多表面连续外观证据报告 v0.2</h1>
<p>Case ID：<code>{html.escape(case["case_id"])}</code></p>
<p>分析时间：{html.escape(generated_at)} · 修订：{html.escape(str(report_revision))}</p>
<p>模型：{html.escape(str(model_info.get("model_version", "")))}</p></div>
<h2>节点 × 表面矩阵</h2><div class="nodes">{"".join(node_cards)}</div>
<h2>同表面相邻变化</h2><table><thead><tr><th>区间</th><th>表面</th><th>配对</th><th>配准</th><th>变化分数</th><th>面积比</th></tr></thead>
<tbody>{"".join(pair_rows)}</tbody></table>
<section class="hero"><h2>机器分析</h2><p class="result">首次异常：{html.escape(str(conclusion))}</p>
<p>触发表面：<span class="badge">{html.escape(trigger_text)}</span></p>
<p>技术证据等级：<b>{html.escape(str(analysis.get("evidence_level", "E0")))}</b></p>
<p>{html.escape(str(analysis.get("explanation", "")))}</p></section>
<h2>人工复核（与机器结论分开保存）</h2><table><thead><tr><th>区间</th><th>表面</th><th>机器结果</th><th>人工类别</th><th>状态</th><th>匿名复核人</th><th>备注</th></tr></thead>
<tbody>{"".join(review_rows) if review_rows else '<tr><td colspan="7">尚无人工复核事件</td></tr>'}</tbody></table>
<section class="notice"><b>限制与免责声明</b><p>{html.escape(DISCLAIMER)}</p>
<p>D01/D04/D05 是人工复核类别；报告不会写成“模型识别出 D01/D04/D05”。</p></section>
</main></body></html>"""
    html_path.write_text(document, encoding="utf-8")
    return {"json_path": str(json_path), "html_path": str(html_path)}
