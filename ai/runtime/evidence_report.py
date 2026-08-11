"""Generate JSON and standalone-link HTML evidence reports."""

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


def generate_evidence_report(
    case: dict[str, Any],
    nodes: list[dict[str, Any]],
    pair_changes: list[dict[str, Any]],
    analysis: dict[str, Any],
    model_info: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, str]:
    """Write auditable UTF-8 JSON and HTML files for one case."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().astimezone().isoformat()
    payload = {
        "report_version": "evidence-report-v0.1",
        "case_id": case["case_id"],
        "analysis_time": generated_at,
        "pipeline_version": case["pipeline_version"],
        "model": model_info,
        "nodes": nodes,
        "pair_changes": pair_changes,
        "analysis": analysis,
        "limitations": [
            "当前主动检测器仅支持D02表面凹陷与D03纸箱破口。",
            "UNKNOWN_VISUAL_CHANGE不自动分类为D01、D04或D05。",
            "外观数字指纹是工程记录，不是跨拍摄密码学视觉身份。",
        ],
        "disclaimer": DISCLAIMER,
    }
    json_path = output / "report.json"
    html_path = output / "report.html"
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
        node_cards.append(
            "<section class='card'>"
            f"<h3>{html.escape(node['node_id'])}</h3>"
            f"<img src='{html.escape(relative)}' alt='{html.escape(node['node_id'])}'>"
            f"<p><b>SHA-256：</b><code>{html.escape(fingerprint.get('image_sha256', ''))}</code></p>"
            f"<p><b>检测：</b>{html.escape(detection_text)}</p>"
            "</section>"
        )
    pair_rows = []
    for pair in pair_changes:
        pair_rows.append(
            "<tr>"
            f"<td>{html.escape(pair['reference_node_id'])} → {html.escape(pair['current_node_id'])}</td>"
            f"<td>{html.escape(pair['registration_status'])}</td>"
            f"<td>{float(pair['change_score']):.4f}</td>"
            f"<td>{float(pair['changed_pixel_ratio']):.4%}</td>"
            "</tr>"
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
main{{max-width:1080px;margin:auto;padding:32px}} h1{{color:#0b5e4d}} code{{word-break:break-all}}
.hero,.card,table,.notice{{background:white;border:1px solid #d9e5e0;border-radius:14px;padding:18px;margin:14px 0}}
.nodes{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}}
.card img{{width:100%;height:210px;object-fit:contain;background:#edf2ef;border-radius:8px}}
table{{width:100%;border-collapse:collapse}} td,th{{padding:10px;border-bottom:1px solid #e2ebe7;text-align:left}}
.result{{font-size:1.3rem;color:#9b3c10}} .notice{{border-left:5px solid #e19a21}}
</style></head><body><main>
<div class="hero"><h1>件证 · 连续外观异常证据报告</h1>
<p>Case ID：<code>{html.escape(case["case_id"])}</code></p>
<p>分析时间：{html.escape(generated_at)}</p>
<p>模型：{html.escape(str(model_info.get("model_version", "")))}</p></div>
<h2>节点证据</h2><div class="nodes">{"".join(node_cards)}</div>
<h2>相邻变化</h2><table><thead><tr><th>区间</th><th>配准</th><th>变化分数</th><th>变化面积比</th></tr></thead>
<tbody>{"".join(pair_rows)}</tbody></table>
<section class="hero"><h2>技术结论</h2><p class="result">首次异常：{html.escape(str(conclusion))}</p>
<p>技术证据等级：<b>{html.escape(str(analysis.get("evidence_level", "E0")))}</b></p>
<p>{html.escape(str(analysis.get("explanation", "")))}</p></section>
<section class="notice"><b>限制与免责声明</b><p>{html.escape(DISCLAIMER)}</p></section>
</main></body></html>"""
    html_path.write_text(document, encoding="utf-8")
    return {"json_path": str(json_path), "html_path": str(html_path)}
