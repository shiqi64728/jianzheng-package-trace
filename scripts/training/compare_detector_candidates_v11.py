"""Build the RC v1.1 three-model comparison and promotion decision."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.training.model_promotion_gate_v11 import evaluate_promotion_gate

ROOT = Path("E:/JianZhengData")
OUTPUT = ROOT / "runtime/competition-rc-v1.1/evidence/detector-comparison-v1.1.json"
DOC = Path("docs/training/d02-d03-detector-comparison-v1.1.md")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    baseline = load(Path("docs/training/d02-d03-yolo26n-baseline-v0.1.metrics.json"))
    n960 = load(Path("docs/training/d02-d03-yolo26n-imgsz960-v0.1.metrics.json"))
    s640 = load(ROOT / "runtime/competition-rc-v1.1/evidence/yolo26s-val-v1.1.json")
    s_train = load(
        ROOT / "runtime/competition-rc-v1.1/evidence/yolo26s-training-v1.1.json"
    )
    n640_val = baseline["validation"]
    n960_val = n960["candidate_val"]["best"]
    active = {
        "overall": n960_val["overall"],
        "D02": n960_val["per_class"]["D02_surface_dent"],
    }
    candidate = {
        "overall": s640["overall"],
        "D02": s640["per_class"]["D02_surface_dent"],
    }
    active_latency = n960_val["speed"]["inference_ms_per_image"]
    candidate_latency = s640["speed_ms_per_image"]["inference"]
    gate = evaluate_promotion_gate(
        active,
        candidate,
        active_latency_ms=active_latency,
        candidate_latency_ms=candidate_latency,
    )

    def row(name, imgsz, values, speed, vram, model_bytes):
        return {
            "model": name,
            "imgsz": imgsz,
            "precision": values["overall"]["precision"],
            "recall": values["overall"]["recall"],
            "mAP50": values["overall"]["mAP50"],
            "mAP50-95": values["overall"]["mAP50-95"],
            "D02": values["D02"],
            "D03": values["D03"],
            "inference_ms_per_image": speed,
            "peak_vram_bytes": vram,
            "model_bytes": model_bytes,
        }

    rows = [
        row(
            "YOLO26n",
            640,
            {
                "overall": {
                    key: n640_val[key]
                    for key in ("precision", "recall", "mAP50", "mAP50-95")
                },
                "D02": n640_val["D02_surface_dent"],
                "D03": n640_val["D03_carton_tear"],
            },
            n960["baseline_640_val"]["speed"]["inference_ms_per_image"],
            None,
            Path(
                baseline["validation"]
                and "E:/JianZhengData/models/releases/d02-d03-yolo26n-baseline-v0.1/best.pt"
            )
            .stat()
            .st_size,
        ),
        row(
            "YOLO26n",
            960,
            {
                "overall": n960_val["overall"],
                "D02": n960_val["per_class"]["D02_surface_dent"],
                "D03": n960_val["per_class"]["D03_carton_tear"],
            },
            active_latency,
            n960["training"]["peak_gpu_memory_bytes"],
            Path(n960_val["checkpoint"]).stat().st_size,
        ),
        row(
            "YOLO26s",
            640,
            {
                "overall": s640["overall"],
                "D02": s640["per_class"]["D02_surface_dent"],
                "D03": s640["per_class"]["D03_carton_tear"],
            },
            candidate_latency,
            s_train["peak_gpu_memory_bytes"],
            s640["model_bytes"],
        ),
    ]
    payload = {
        "report_version": "detector-comparison-v1.1",
        "split": "val",
        "test_predictions_accessed": False,
        "models": rows,
        "promotion_gate": gate,
        "candidate_test_executed": False,
        "candidate_test_metrics": None,
        "final_active_model": "d02-d03-yolo26n-imgsz960-v0.1",
        "final_active_sha256": "2dd857412b63df66d1273b326dc51afaed895da1d360c97e184762c882181a97",
        "active_model_changed": False,
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    lines = [
        "# D02/D03 Detector Comparison v1.1",
        "",
        "三者均使用冻结 `detect-d02-d03-v0.1`；表内为真实 val 结果。YOLO26s 未达到晋级闸门，因此没有执行 candidate test，active detector 不变。",
        "",
        "| Model | imgsz | P | R | mAP50 | mAP50-95 | D02 AP | D03 AP | latency ms/image | peak VRAM | model bytes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in rows:
        vram = (
            "NOT_AVAILABLE"
            if item["peak_vram_bytes"] is None
            else str(item["peak_vram_bytes"])
        )
        lines.append(
            f"| {item['model']} | {item['imgsz']} | {item['precision']:.6f} | {item['recall']:.6f} | {item['mAP50']:.6f} | {item['mAP50-95']:.6f} | {item['D02']['mAP50-95']:.6f} | {item['D03']['mAP50-95']:.6f} | {item['inference_ms_per_image']:.3f} | {vram} | {item['model_bytes']} |"
        )
    lines.extend(
        [
            "",
            "## Promotion gate",
            "",
            f"- overall mAP50-95 relative gain：{gate['relative_gains']['overall_mAP50_95_relative_gain']:.3%}",
            f"- D02 AP relative gain：{gate['relative_gains']['D02_mAP50_95_relative_gain']:.3%}",
            f"- D02 Recall relative gain：{gate['relative_gains']['D02_recall_relative_gain']:.3%}",
            f"- 通过提升项：{gate['gain_pass_count']}/3（要求至少 2）",
            f"- latency：{candidate_latency:.3f} ms，限制 {gate['latency_limit_ms']:.3f} ms，结果 {'PASS' if gate['latency_pass'] else 'FAIL'}",
            f"- 最终：`{gate['decision']}`；candidate test 未执行。",
        ]
    )
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(OUTPUT),
                "document": str(DOC),
                "decision": gate["decision"],
                "candidate_test_allowed": gate["candidate_test_allowed"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
